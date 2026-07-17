# Reference — Aidbox Python App operations

Deep detail for [SKILL.md](SKILL.md). Identifiers are genericized: `example-app` (App id / compose service), `org-example` (tenant), `example.org` (domain).

## The HTTP-RPC "no public URL" model {#no-public-url}

The app is a plain HTTP service, but it is **not** exposed to callers directly. Aidbox holds the App manifest (registered by the SDK at boot via `PUT /App/example-app` — do **not** seed it) and proxies each matching request to the app over HTTP-RPC. So:

- Callers hit `Aidbox-base/<your-op-path>`; Aidbox forwards to the app; the app's response goes back through Aidbox.
- The app's own base URL (`APP_URL`, the app's Docker-DNS name) is an **internal** address Aidbox uses to reach it — it is not a public ingress. Keep it internal.
- **`APP_URL` must point at the service's Docker DNS name**; **`APP_ID`** is the manifest id (`PUT /App/example-app`). Compose service name and `APP_ID` are typically the same string.

**The one exception** — routes you add directly on the aiohttp app (not `@sdk.operation`) *are* served at `APP_URL` directly, bypassing the Aidbox proxy. This is only correct for things a third party must fetch straight from the app, e.g. a JWKS document Aidbox's token introspector pulls via `jwks_uri`:

```python
def create_app() -> web.Application:
    app = _create_app(sdk)
    app.router.add_get("/auth/jwks", jwks_handler)  # direct route, not proxied
    return app
```

## The request envelope {#the-request-envelope}

The handler is `async def handler(operation, request)`. `request` is a **dict** (the Aidbox envelope), not an `aiohttp.Request`:

| Access | Contents |
| --- | --- |
| `request["app"]` | the aiohttp `web.Application` (holds the clients, settings) |
| `request["app"]["client"]` | root-rooted Aidbox client |
| `request["app"]["fhir_client"]` | `/fhir`-rooted client |
| `request["app"]["settings"]` | SDK `Settings` (`APP_INIT_URL`, `APP_INIT_CLIENT_ID/SECRET`, …) |
| `request.get("resource")` | the request **body** (flat JSON or a FHIR `Parameters`) |
| `request["headers"]` | original-caller headers (e.g. `x-forwarded-for` for the caller IP) |
| `request["params"]` | route/query params (e.g. `params.organization/id` on org-scoped FHIR routes) |
| `request` — the caller identity | `request["oauth/user"]` or `request["user"]`, depending on the route/token path |

Canonical body read: `body = request.get("resource") or {}`.

Don't read caller identity straight off the envelope; prefer a `get_caller_user(request)` helper, which handles both envelope shapes and returns `{}` for client-only auth.

## Two clients {#two-clients}

`sdk.py` builds the SDK and its root client. `main.py` attaches a second client rooted at `.../fhir` in a cleanup-ctx hook:

```python
# main.py
async def _init_fhir_client(app: web.Application):
    s = app["settings"]
    auth = BasicAuth(login=s.APP_INIT_CLIENT_ID, password=s.APP_INIT_CLIENT_SECRET)
    app["fhir_client"] = AsyncAidboxClient(
        f"{s.APP_INIT_URL.rstrip('/')}/fhir", authorization=auth.encode()
    )
    yield

def create_app() -> web.Application:
    app = _create_app(sdk)
    app.cleanup_ctx.append(_init_fhir_client)
    return app
```

**Which to use:**

- `request["app"]["fhir_client"]` (rooted at `/fhir`) — **default** for FHIR resource work. Prefer fhirpy idioms:
  ```python
  await fhir_client.resources("Patient").search(active=True).fetch()
  await fhir_client.reference("Organization", org_id).to_resource()
  await fhir_client.resource("Observation", **payload).save()
  ```
- `request["app"]["client"]` (root) — for endpoints that are **not** under `/fhir`: `$psql`, `/App/...`, `$send`, and the FHIR **transaction bundle** (`POST /fhir`, which posts to the root, not `/fhir/`). Also for Aidbox-native `/Session` (see gotchas).

Both clients share the same credentials (`APP_INIT_CLIENT_ID/SECRET`) — the second is purely a path-root convenience, not a distinct identity.

**Known keep-raw sites** (do not rewrite into fhirpy): `/fhir/metadata`, a transaction bundle carrying `ifMatch`, `$send`, a `meta.extension` PATCH, and all `Session` calls.

## Gating {#gating}

Choose exactly one operation gate owner. The decorator can write a generated manifest gate, or a standalone seeded `AccessPolicy` can authorize the proxied URI.

```python
@sdk.operation(methods=["GET"], path=["healthcheck"], public=True)      # unauthenticated, anyone
@sdk.operation(methods=["GET"], path=[...], access_policy=_POLICY)      # authenticated + policy match
@sdk.operation(methods=["POST"], path=[...])                            # no generated gate
```

- **`public=True`** — no auth required. Use for healthchecks, webhooks with their own signature check, and anonymous flows (password-reset request, etc.).
- **`access_policy={...}`** — an inline policy the SDK writes into the manifest. Use this only for simple json-schema gates; see the engine trap below.
- **Neither** — the manifest creates no operation-specific gate. Use this when:
  - a standalone seeded `AccessPolicy` with `uri` / `operation` / tenant matching is the intended gate (the common choice for role/org-scoped operations), or
  - the op is deliberately root/privileged only (e.g. scheduler-only). Document scheduler-only intent in a comment so nobody "fixes" it by adding a broad policy.

For **org-scoped** ops (`path=["fhir", "...", "$op"]` reached at `/Organization/{id}/fhir/...`), the policy matches the tenant marker on the caller; that machinery lives in [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md) (note org-scoped SDC ops expose `params.org_id`, org-scoped FHIR resources expose `params.organization/id`).

Double decorators handle operations that need both root-FHIR and org-scoped-FHIR paths:

```python
@sdk.operation(methods=["POST"], path=["fhir", "Practitioner", "$invite-practitioner"])
@sdk.operation(
    methods=["POST"],
    path=["Organization", {"name": "org-id"}, "fhir", "Practitioner", "$invite-practitioner"],
)
async def invite_practitioner(operation, request): ...
```

Seed separate `AccessPolicy` resources for each route family that should be reachable by non-root callers.

## The access_policy engine trap {#access-policy-engine-trap}

`@sdk.operation(access_policy=...)` **always writes the rule under a `schema` key** in the generated policy. Only the `json-schema` engine consumes `schema`. A `matcho` rule placed there is ignored and the policy **fails closed (403)**.

So an inline `access_policy` must be `json-schema`:

```python
# Gate: any authenticated caller (request carries a user with an id).
_AUTHENTICATED_CALLER = {
    "engine": "json-schema",
    "schema": {
        "type": "object",
        "required": ["user"],
        "properties": {"user": {"type": "object", "required": ["id"]}},
    },
}

@sdk.operation(methods=["GET"], path=[...], access_policy=_AUTHENTICATED_CALLER)
async def my_op(operation, request): ...
```

If you need `matcho` (or richer tenant/role matching), **seed a standalone `AccessPolicy`** resource instead of inlining it, and leave the decorator without `public` or `access_policy` so the seeded policy is the non-root gate.

**Fail-closed handlers.** A coarse gate (e.g. "any authenticated user") can still be safe if the handler fails closed: if a `$session-context`-style op only returns data for callers with a live patient session, a clinician token that passes the gate still gets 404 — no cross-population leak. Prefer this belt-and-suspenders shape over a gate that tries to encode everything.

## Registration {#registration}

```python
# sdk.py — the singleton every module imports
from aidbox_python_sdk.sdk import SDK
from aidbox_python_sdk.settings import Settings
settings = Settings(**{})
sdk = SDK(settings, resources={}, seeds={})
```

```python
# main.py — side-effect imports register the decorated handlers
import operations           # noqa: F401 — registers @sdk.operation handlers
import auth.admin_operations
# ... one import per operations module ...
from sdk import sdk
app = _create_app(sdk)
```

Adding an op:
1. Write the handler in an existing module, or create a new module next to them.
2. If new, add `import your_module` to `main.py` (order-independent; the import runs the decorators).
3. No `register(sdk)` wrapper exists or is needed — the module-level `@sdk.operation` decorator is the registration.

`gunicorn --reload` picks up handler edits in the running container; dependency/env changes need a rebuild.

## request_schema {#request-schema}

`@sdk.operation(request_schema=...)` validates the envelope against a jsonschema before your handler runs. Prefer it over hand-rolled `web.HTTPBadRequest` **when** an endpoint accepts a single body shape with required fields. It does not fit endpoints that accept **both** a flat body and a `Parameters` resource (one schema can't cleanly express both) — those read fields via a `get_param`-style helper instead.

## Storage gotchas {#storage-gotchas}

- **`Session` rejects unknown top-level keys** (422 `unknown-key`). Per-session metadata goes in `Session.meta.extension` (e.g. a `valueInstant`).
- **`Session` cannot be materialised through fhirpy.** Its own `client` field collides with fhirpy's reserved `client` kwarg (`BaseResource.__init__() got multiple values for 'client'`). Search/read it via `client.execute(...)` and work with raw dicts.
- **Read/write `Session` through the same root** — it's an Aidbox-native resource at `/Session`. `meta.extension` written at `/Session` won't read back from `/fhir/Session`. Use the root client for it.
- **No default `Session` search by user** — Aidbox ships no `user` search param for `Session`; seed one. Sort session lists on `-createdAt`, not `-_lastUpdated` (a heartbeat write bumps `lastUpdated`).
- **Custom-resource references are existence-checked** — Aidbox rejects a custom resource whose `user`/`patient`/`organization` references point at resources that don't exist yet (`non-existent-resource` OperationOutcome). Create referents first. This mostly bites **hand-seeded test fixtures**; real resources created through `/fhir` already exist.
- **OrgBAC subject resolution needs `/fhir`-created resources** — a resource PUT to the Aidbox-format endpoint (`/Patient/{id}`, what the SDK root `client.execute` hits) is treated as **non-existent** by a tenant-scoped create (422 `non-existent-resource`) even with the tenant extension. PUT it via **`/fhir/Patient/{id}`**. Real resources arrive through `/fhir` OrgBAC paths, so this is a test-fixture concern. See [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md).

## Reading the Aidbox envelope — helpers {#envelope-helpers}

```python
def caller_ip(request: dict) -> str:
    headers = request.get("headers") or {}
    return (headers.get("x-forwarded-for", "").split(",")[0].strip()
            or headers.get("x-real-ip", "") or "unknown")

def get_caller_user(request: dict) -> dict:
    return request.get("oauth/user") or request.get("user") or {}

def ref_id(ref: dict | None) -> str:
    """ID from Aidbox-shape {"id":...} or FHIR-shape {"reference":"Type/id"}."""
    if not ref:
        return ""
    return ref["id"] if "id" in ref else (ref.get("reference") or "").split("/")[-1]
```

References cross the proxy in **two shapes** depending on the endpoint that produced them — Aidbox-shape (`{"id": "...", "resourceType": "..."}`) and FHIR-shape (`{"reference": "Type/id"}`). A `ref_id` helper that handles both keeps handlers shape-agnostic.

## Testing {#testing}

Integration-style, against a dedicated **test Aidbox** (a `test` compose profile). `aidbox-python-sdk`'s `pytest_plugin` provides fixtures:

```python
# conftest.py
pytest_plugins = ["aidbox_python_sdk.pytest_plugin"]
```

- `app`, `aidbox_client`, `sdk` — the app, a root client, the SDK.
- `safe_db` — snapshots Aidbox's txid at fixture init and calls `drop_before_all(txid)` on teardown. Tests therefore run **serially**, and seeds loaded **before** the snapshot are preserved. (Some Aidbox builds reject `?execute=true` on `/$psql`; a project override of `safe_db` that reads the txid from the body-level `/$psql` call sidesteps it.)

Call an op through the proxy, exactly as a client would:

```python
async def test_healthcheck_via_aidbox_proxy(aidbox_client, safe_db):
    result = await aidbox_client.execute("/healthcheck", method="GET")
    assert result["ok"] is True
```

- A **seeded `SearchParameter`** only reaches the test box after it reloads its init bundle — recreate it (`docker compose --profile test down -v`) when you add a seed; a plain `up` reuses the already-seeded box.
- `Session.user` / `Session.client` must reference existing resources — seed the `User` before the `Session`.
- For time-dependent logic (reapers, TTLs), make `now` an injectable parameter so tests can time-travel instead of sleeping.

## Reference

- [aidbox-python-sdk](https://github.com/Aidbox/aidbox-python-sdk) — App framework, `pytest_plugin`
- [fhir-py](https://github.com/beda-software/fhir-py) — `AsyncAidboxClient` / fhirpy idioms
- [Aidbox Apps](https://www.health-samurai.io/docs/aidbox/developer-experience/apps) — App resource, HTTP-RPC protocol
