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

## Required asserts, in depth

`?__debug=policy` always returns `HTTP 200` with a JSON policy dump, **regardless of
whether the underlying request would be allowed or denied** — the debug flag intercepts
before the deny short-circuit. Never write `HTTP *` or check `status != 403` against a
debug request; assert on the dump contents instead.

**Allow:**

```hurl
GET {{base_url}}/fhir/Patient/{{patient_id}}?__debug=policy
Authorization: Bearer {{clinician_token}}

HTTP 200
[Asserts]
jsonpath "$.policies[?(@['eval-result'] == true)]" exists
jsonpath "$.policies[?(@.error)].id" not exists
jsonpath "$.policies[?(@.error)].error" not exists
```

**Deny:**

```hurl
GET {{base_url}}/fhir/Patient/{{unrelated_patient_id}}?__debug=policy
Authorization: Bearer {{guardian_token}}

HTTP 200
[Asserts]
jsonpath "$.policies[?(@['eval-result'] == true)].id" not exists
jsonpath "$.policies[?(@.error)].id" not exists
jsonpath "$.policies[?(@.error)].error" not exists
```

### Why project `.id` / `.error`, not the bare filtered object

| Assert | On failure, Hurl reports |
|---|---|
| `$.policies[?(@.error)]` not exists | `object <Object()>` — tells you nothing |
| `$.policies[?(@.error)][0].id` | Often **silently passes** — easy to write a JsonPath chain that doesn't actually select anything |
| `$.policies[?(@.error)].id` not exists | `string <as-guardian-patch-patient>` — you know which policy broke |
| `$.policies[?(@.error)].error` not exists | `string <ERROR: syntax error at or near "{">` — you know why |

Always assert the `.id` + `.error` pair together so a SQL failure is visible directly
in test output instead of requiring a log dive.

Debug JSON field names are kebab-case: `eval-result`. A single erroring policy exposes
`error` (singular); a policy whose `matcho` clause simply didn't match exposes `errors`
(plural, a list of mismatched keys) — don't conflate the two when writing asserts.

## SQL template braces

Aidbox SQL policies interpolate context values with **double** curly braces:

```sql
select 1 from careteam ct
where ct.practitioner_id = {{user.fhirUser.id}}
  and ct.patient_id = {{params.resource/id}}
```

A single-brace template (`{user.fhirUser.id}`) is not rewritten by Aidbox and is sent to
Postgres verbatim, producing `syntax error at or near "{"`. This error surfaces as a
`policy-error`/`error` field per the section above — it will not 500 the request if
another policy also allows it, so it's easy to miss without the required asserts.

Do not confuse this with genuine Postgres JSONB path syntax, which also uses braces and
must **not** be doubled:

```sql
-- ✅ Postgres JSONB path literal — single braces are correct here
r.resource #>> '{subject,id}'
```

A blanket find-and-replace of `{` → `{{` will break JSONB path queries; only double the
braces that are Aidbox template placeholders (dotted paths like `user.…`, `params.…`,
`role.…`).

Seed changes are not automatically live. After editing an `AccessPolicy` YAML, confirm
Aidbox has actually reloaded it (via your project's watch-seeds mechanism, a seed-loader
run, or a direct admin `PUT` of the resource) before trusting a "still failing" or
"now passing" result — disk and the live DB can silently diverge, and a stale in-DB
policy will make edits appear to have no effect.

## Coverage: exercising the success path of SQL policies

Search and create endpoints are the easiest to write asserts for, but for an own-scoped
SQL policy (read/patch/update/delete gated by "is this *my* resource") they don't
exercise the interesting logic at all. The policy's real job is distinguishing "linked to
me" from "not linked to me," which only a by-id request against both a linked and an
unlinked resource can prove.

1. Seed fixtures with an **admin** identity so they exist regardless of the policy under
   test, and assert `HTTP 201` on the fixture create itself — never `HTTP *`. A silently
   failed fixture create (validation error, missing required field) means a later "this
   should be allowed" assertion fails with `eval-result` absent/null, which looks like a
   policy bug but is actually a missing fixture.
2. **Allow** case: perform the by-id op against a resource that is actually linked to the
   acting identity (e.g. a `Patient` whose `generalPractitioner` or care-team link points
   at the test clinician).
3. **Deny** case: perform the *same* op against a resource linked to a **different**
   identity. This is the case that proves isolation — an allow-only suite would pass even
   if the SQL policy's `WHERE` clause were a no-op that matched everyone.
4. Prefix fixture ids with a per-run identifier (e.g. `{{run_id}}-…`) so a transaction-
   snapshot teardown (below) can find and remove everything the run created without
   hand-maintained cleanup lists.

Some resources need extra care beyond `__debug=policy`: FHIR resources with constraint
invariants (e.g. a `Consent` needing `policyRule`) may need a real `PUT`/create rather
than a debug-only check, because `__debug=policy` create requests often don't persist
the resource.

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

## Checklist for new or changed policies

- [ ] SQL uses `{{…}}` for Aidbox template params only, not for JSONB path literals
- [ ] Suite covers allow **and** deny for every operation the policy authorizes
- [ ] By-id SQL policies have by-id cases against real linked **and** unlinked fixtures
- [ ] Every `__debug=policy` block asserts `eval-result` **and** the `.id`/`.error` pair
- [ ] Live Aidbox reloaded after seed edits (disk ≠ live DB)
- [ ] Suite green end-to-end under the runner script (setup → suites → teardown)

## What this style of test does not catch by default

- `:auth/policy-error` log entries for policies that errored on paths you didn't assert
  against — scrape server logs in CI if this matters for your compliance posture
- A policy that is simply never evaluated because no fixture in the suite reaches it
- Seed drift: YAML fixed on disk while an old, unpatched version is still live in the DB
