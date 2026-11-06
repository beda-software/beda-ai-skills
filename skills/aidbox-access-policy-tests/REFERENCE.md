# Aidbox AccessPolicy Hurl tests — reference

Deep detail behind [SKILL.md](SKILL.md). Examples use placeholder role names
(`clinician`, `guardian`, `no-role`) and placeholder resource ids; substitute your
own role model. Requires a local/dev Aidbox with `BOX_SECURITY_DEV_MODE=true` and the
[hurl](https://hurl.dev) CLI.

## How Aidbox evaluates policies

Policy evaluation for a request is an **allowlist**: Aidbox tries every candidate policy
(matched by `roleName`, resource type, method, etc.) until one returns `eval-result: true`
→ request allowed. If every candidate is `false` → `403`.

A `sql` or `complex`-engine policy whose query **throws** (bad template syntax, wrong
column, type mismatch) is a **policy evaluation error**, not an HTTP-level failure:

- Logged server-side as `:auth/policy-error`
- In the `?__debug=policy` JSON, that policy entry carries `"error": "ERROR: …"` and
  usually `eval-result: null`
- The errored policy is treated as **failed**, and evaluation **continues** to the next
  candidate
- If any other valid policy allows the same request, the caller sees **HTTP 200** —
  the broken policy is invisible unless you inspect the debug dump

`engine: complex` with an `and: [matcho, sql]` shape still evaluates the SQL branch even
when the `matcho` half already failed on an unrelated dimension (wrong HTTP method, wrong
resource type). A syntax error in the by-id SQL clause therefore also fires — and pollutes
— every other operation candidate-matched for the same role, including search. This is why
a single "does search still return 200" test is not sufficient coverage for a by-id policy.

## Why project `.id` / `.error`

Assert shapes live in [SKILL.md](SKILL.md#steps) step 5. What each reports on failure:

| Assert | On failure, Hurl reports |
|---|---|
| `$.policies[?(@.error)]` not exists | `object <Object()>`, no information |
| `$.policies[?(@.error)][0].id` | Often **silently passes**: the chain can select nothing |
| `$.policies[?(@.error)].id` not exists | `string <as-guardian-patch-patient>`: which policy broke |
| `$.policies[?(@.error)].error` not exists | `string <ERROR: syntax error at or near "{">`: why |

`?__debug=policy` intercepts before the deny short-circuit, so it returns HTTP 200 for
denied requests too. A single erroring policy exposes `error`; a policy whose `matcho`
clause didn't match exposes `errors` (a list of mismatched keys).

## Fixtures that need a real write

FHIR resources with constraint invariants (e.g. a `Consent` needing `policyRule`) need a
real `PUT`/create, because `__debug=policy` create requests often don't persist the resource.

## Conditional PATCH checks the URL, not the body

A conditional PATCH's search params (`?patient=…&_id=…`) match the **stored** resource; the
body can still rewrite the reference (e.g. move an Appointment to another patient). Pin
that behaviour with a test either way, and where the body must not change ownership, only
the policy can guard it.

## Suite shape and teardown

A convention that scales to many role × feature combinations:

| Piece | Role |
|---|---|
| Policy seeds | Wherever your `AccessPolicy` resources live (e.g. `resources/**/AccessPolicy/`) |
| `00-setup.hurl` | Creates ephemeral users/roles per role under test, captures OAuth tokens |
| `NN-as-<role>-<feature>.hurl` | One suite file per (role × feature area) — numeric prefix controls run order if needed |
| `99-teardown.hurl` | Rolls back everything the run wrote |
| A runner script | setup → all suite files → teardown, propagating the suite's exit code |

### Isolated client

Create a dedicated password-grant `Client` for the test run rather than reusing an
app's real client — this avoids accidentally exercising bootstrap/dev-mode policies
(e.g. a `devbox`-style allow-everything policy) that would mask the policy under test.

### Ephemeral identities per role

For each role under test, `PUT` a `User` linked to a real fixture resource (however your
identity model links users — `fhirUser`, `Role.links.*`, etc.), `PUT` a `Role` with the
appropriate `name`, then obtain a token via `POST /auth/token` with `grant_type: password`
and capture `access_token`. Include one identity with **no** `Role` at all to cover the
"no matching role → deny everything" baseline.

### Transaction-snapshot teardown (no manual cleanup list)

Rather than tracking every resource id a run creates, snapshot the database's
transaction sequence **before** setup runs, then ask Postgres to roll back every write
committed after that point:

```bash
# 1. Snapshot current transaction id before creating anything
TX_ID=$(hurl --variable base_url="$AIDBOX_URL" --variable admin_basic="$ADMIN_BASIC" \
  <(printf 'POST {{base_url}}/$psql\nAuthorization: Basic {{admin_basic}}\nContent-Type: application/json\n{"query":"SELECT last_value FROM transaction_id_seq;"}\n\nHTTP 200\n') \
  2>/dev/null | grep -o '"last_value":[0-9]*' | grep -o '[0-9]*$')

# 2. ...run setup, suites... (all writes happen after TX_ID)

# 3. Teardown: roll back everything committed after TX_ID
```

```hurl
# 99-teardown.hurl
POST {{base_url}}/$psql
Authorization: Basic {{admin_basic}}
Content-Type: application/json
{"query":"select drop_before_all({{tx_id}});"}

HTTP 200
[Asserts]
jsonpath "$.status" == "success"
```

This assumes your Aidbox exposes a `drop_before_all(tx_id)` helper (or equivalent) that
rolls back writes newer than a given transaction id — check what's available in your
environment; if not present, fall back to explicit `DELETE` of every `{{run_id}}-*`
fixture id in teardown.

### Runner script shape

```bash
#!/usr/bin/env sh
set -eu
AIDBOX_URL="${AIDBOX_URL:-http://localhost:8080}"
ADMIN_BASIC=$(printf '%s:%s' "${ADMIN_USER:-root}" "${ADMIN_SECRET:-secret}" | base64 | tr -d '\n')
RUN_ID="policy-test-$(od -An -N6 -tx1 /dev/urandom | tr -d ' \n')"

# snapshot TX_ID (see above), then:
SETUP_JSON=$(hurl --json --variable base_url="$AIDBOX_URL" --variable admin_basic="$ADMIN_BASIC" \
  --variable run_id="$RUN_ID" --variable tx_id="$TX_ID" 00-setup.hurl) || { echo "setup failed" >&2; exit 1; }

# extract captured tokens from --json output (grep, or jq if available), then:
set +e
hurl --test --continue-on-error --jobs 1 \
  --variable base_url="$AIDBOX_URL" --variable admin_basic="$ADMIN_BASIC" \
  --variable run_id="$RUN_ID" --variable tx_id="$TX_ID" \
  --variable clinician_token="$CLINICIAN_TOKEN" --variable guardian_token="$GUARDIAN_TOKEN" \
  hurl/*.hurl
SUITE_EXIT=$?
set -e

hurl --test --jobs 1 --variable base_url="$AIDBOX_URL" --variable admin_basic="$ADMIN_BASIC" \
  --variable run_id="$RUN_ID" --variable tx_id="$TX_ID" 99-teardown.hurl

exit "$SUITE_EXIT"
```

`--jobs 1` keeps the suite serialized against the shared transaction-snapshot teardown —
parallel jobs would race writes against the snapshot boundary.

### Running a single suite file during development

Always include setup (teardown is optional but recommended so you don't leave test
fixtures behind):

```bash
AIDBOX_URL=http://localhost:8080
ADMIN_BASIC=$(printf 'root:secret' | base64 | tr -d '\n')
RUN_ID="policy-test-$(od -An -N6 -tx1 /dev/urandom | tr -d ' \n')"
# TX_ID: snapshot as in the runner script above

hurl --test --jobs 1 \
  --variable base_url="$AIDBOX_URL" \
  --variable admin_basic="$ADMIN_BASIC" \
  --variable run_id="$RUN_ID" \
  --variable tx_id="$TX_ID" \
  00-setup.hurl \
  hurl/30-as-guardian-patients.hurl \
  99-teardown.hurl
```
