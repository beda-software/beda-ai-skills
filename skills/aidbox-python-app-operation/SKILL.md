---
name: aidbox-python-app-operation
description: Add or debug a server-side operation on an Aidbox App built with aidbox-python-sdk — the @sdk.operation decorator, the (operation, request) dict envelope, two-client rooting (root vs /fhir), public=/access_policy= manifest gates, standalone seeded AccessPolicy gates, and the HTTP-RPC "no public URL" proxy model. Use when adding custom server logic Aidbox proxies to a Python app, wiring an operation into main.py, choosing which FHIR client to use, gating an op with public=, access_policy=, or a seeded AccessPolicy, reading a flat-JSON-or-Parameters body, or debugging a 403/404/422 from a proxied operation, an ignored access_policy, or a Session/custom-resource write.
---

# Aidbox Python App operations

An **Aidbox App** (built on [aidbox-python-sdk](https://github.com/Aidbox/aidbox-python-sdk)) is a separate HTTP service. Aidbox holds the manifest and **proxies** matching requests to it over HTTP-RPC. You add server-side logic as `@sdk.operation` handlers; callers reach them through Aidbox, never the app directly.

## Quick start

```python
# operations.py
from aiohttp import web
from sdk import sdk  # the SDK singleton (see below)

@sdk.operation(methods=["GET"], path=["healthcheck"], public=True)
async def healthcheck(operation, request):
    client = request["app"]["client"]            # root-rooted Aidbox client
    meta = await client.execute("/fhir/metadata", method="GET")
    return web.json_response({"ok": True, "fhirVersion": meta.get("fhirVersion")})
```

`path=["healthcheck"]` is reachable at `Aidbox-base/healthcheck`. Path segments join with `/`; put an op under FHIR by prefixing `path=["fhir", "Practitioner", "$do-thing"]`.

## The five things to internalize

1. **Handler signature is `(operation, request)` and `request` is a dict** — the Aidbox envelope, NOT an `aiohttp.Request`. The SDK injects the aiohttp app at `request["app"]`; original-caller headers at `request["headers"]`; the request body at `request["resource"]` (or `request["body"]`). For caller identity, normalize both shapes behind a helper (`get_caller_user(request)`) because Aidbox may send `oauth/user` or `user`. See [REFERENCE.md](REFERENCE.md#the-request-envelope).

2. **Two FHIR clients, distinct roots** — `request["app"]["client"]` is rooted at the Aidbox root (use for `$psql`, `/App/...`, `POST /fhir` transaction bundles, Aidbox-native `/Session`). `request["app"]["fhir_client"]` is rooted at `.../fhir` (the default for FHIR resource work; prefer fhirpy idioms). Same credentials — path-root convenience, not a second identity. See [REFERENCE.md](REFERENCE.md#two-clients).

3. **Choose one gate owner** — `public=True` OR `access_policy={...}` writes a generated gate into the App manifest. Omitting both means the manifest creates no operation-specific gate; use that only when a standalone seeded `AccessPolicy` is the intended gate, or when the op is deliberately root/privileged only. See [REFERENCE.md](REFERENCE.md#gating).

4. **`access_policy=` must use the `json-schema` engine** — the SDK always writes the rule under a `schema` key, and only `json-schema` consumes `schema`. A `matcho` rule there is silently ignored and fails closed (403). See [REFERENCE.md](REFERENCE.md#access-policy-engine-trap).

5. **Register by side-effect import** — the SDK singleton lives in `sdk.py`; `main.py` imports each operations module for its decorator side effects before building the app. New module ⇒ add `import your_module` to `main.py`. No `register()` wrapper. See [REFERENCE.md](REFERENCE.md#registration).

## Reading the body and envelope

Aidbox operations often accept **both** a flat JSON body and a FHIR `Parameters` resource. Factor the envelope readers into small helpers (`get_param`, `ref_id`, `caller_ip`, `get_caller_user`) and reuse them instead of retyping them. The core body helper is:

```python
def get_param(body: dict, name: str) -> str:
    if body.get("resourceType") == "Parameters":
        for p in body.get("parameter") or []:
            if p.get("name") == name:
                for k in ("valueString", "valueCode", "valueUri", "valueId"):
                    if k in p:
                        return p[k]
        return ""
    return body.get(name) or ""
```

If an endpoint accepts only one shape with required fields, prefer `@sdk.operation(request_schema=...)` (jsonschema validation of the envelope) over hand-rolled `web.HTTPBadRequest`. See [REFERENCE.md](REFERENCE.md#request-schema).

## Storage gotchas that bite

- **`Session` can't be materialised through fhirpy** (its `client` field collides with fhirpy's reserved `client` kwarg) — use `client.execute(...)` and raw dicts. `Session` also rejects unknown top-level keys (422) — stash metadata in `Session.meta.extension`.
- **Custom-resource references are existence-checked** — Aidbox rejects a custom resource whose references point at not-yet-created resources (`non-existent-resource`). Create referents first (matters for hand-seeded test fixtures).
- **OrgBAC subject resolution needs `/fhir`-created resources** — a resource PUT to the Aidbox-format endpoint (`/Patient/{id}`) reads as non-existent to a tenant-scoped create; PUT via `/fhir/Patient/{id}`. See [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md).

Full list: [REFERENCE.md](REFERENCE.md#storage-gotchas).

## Testing

Tests are **integration-style** against a dedicated test Aidbox. `aidbox-python-sdk`'s `pytest_plugin` provides `app`, `aidbox_client`, `sdk`, and `safe_db` fixtures; call the op through `aidbox_client.execute("/your-op", ...)`. A seeded `SearchParameter` only reaches the test box after it reloads its init bundle (`docker compose --profile test down -v`). See [REFERENCE.md](REFERENCE.md#testing).
