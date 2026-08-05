---
name: aidbox-access-policy-tests
description: >-
  Write and harden Aidbox AccessPolicy Hurl tests (__debug=policy, eval-result,
  SQL policy errors, allow/deny fixture coverage). Use when adding or changing
  AccessPolicy YAML, writing or extending a Hurl test suite for role-based or
  own-scoped access, or diagnosing why a policy test passed despite a
  :auth/policy-error / SQL syntax error in the logs.
---

# Aidbox AccessPolicy Hurl tests

Tests that prove an `AccessPolicy` actually allows and denies what it should, using
[Hurl](https://hurl.dev) against a running Aidbox with `BOX_SECURITY_DEV_MODE=true`.
Complements [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md), which
covers *why* a policy is right or wrong; this skill covers *proving* it with real requests.

## The trap this skill exists to prevent

**A `sql`/`complex`-engine policy that throws is not an HTTP failure — it's silently swallowed.**
Aidbox evaluates policies as an allowlist: it tries each candidate until one returns
`eval-result: true`; if all are `false` (or errored), the request is `403`. A SQL policy
whose query throws is logged as `:auth/policy-error`, treated as `eval-result: false`
or `null`, and evaluation just **continues** to the next policy. If some other policy
happens to allow the same request, you get **HTTP 200 while the policy under test never
fired correctly** — asserting only the outer HTTP status hides this completely.

`engine: complex` with an `and:` block still runs the SQL branch even when the `matcho`
half fails (wrong method/resource type) — a broken by-id SQL clause can therefore pollute
search and other unrelated operations for the same role. See
[REFERENCE.md](REFERENCE.md#how-aidbox-evaluates-policies).

## Required asserts on every `__debug=policy` request

With `?__debug=policy`, Aidbox returns **HTTP 200 and a policy dump even when the real
request would be denied** — never gate these requests on `status != 403` or `HTTP *`.
Assert on the policy dump itself, and always pair `eval-result` with an `.error` check:

**Allow** (some policy must match, and none may have errored):

```hurl
HTTP 200
[Asserts]
jsonpath "$.policies[?(@['eval-result'] == true)]" exists
jsonpath "$.policies[?(@.error)].id" not exists
jsonpath "$.policies[?(@.error)].error" not exists
```

**Deny** (no policy may match, and none may have errored):

```hurl
HTTP 200
[Asserts]
jsonpath "$.policies[?(@['eval-result'] == true)].id" not exists
jsonpath "$.policies[?(@.error)].id" not exists
jsonpath "$.policies[?(@.error)].error" not exists
```

Project `.id` and `.error`, never the bare object — `not exists` on
`$.policies[?(@.error)]` shows a useless `object <Object()>` on failure, while
`.error` on failure shows the real `string <ERROR: syntax error at or near "{">`.
Debug JSON fields are kebab-case (`eval-result`); SQL failures use singular `error`,
matcho mismatches use plural `errors`. Details: [REFERENCE.md](REFERENCE.md#required-asserts-in-depth).

## SQL template braces

Aidbox SQL policy params need **double** braces:

```sql
WHERE p.id = {{user.fhirUser.id}}
  AND rp.resource->'patient'->>'id' = {{params.resource/id}}
```

Single braces (`{user.fhirUser.id}`) go to Postgres literally →
`syntax error at or near "{"`. Genuine Postgres JSONB path operators
(`r.resource#>>'{subject,id}'`) correctly keep single braces — don't blanket-convert
every brace you see.

After editing seed YAML, confirm Aidbox has reloaded it (watch-seeds / seed-loader /
admin `PUT`) before trusting a test result — disk state and live DB state can silently
diverge.

## Cover the success path, not just search/create

For any own-scoped SQL policy (read/patch/update/delete by id), asserting search and
create is not enough:

1. Seed fixtures as **admin**, asserting `HTTP 201` (never `HTTP *`) — a silently-failed
   fixture create means a later "allow" case fails for the wrong reason (missing data,
   not a bad policy).
2. **Allow**: the op against a resource genuinely linked to the acting identity.
3. **Deny**: the same op against an **unlinked** resource belonging to someone else —
   this is the case that actually proves ownership isolation, not merely that *a*
   policy exists.
4. Namespace fixture ids to a per-run identifier so teardown can find and remove
   everything the run created.

## Suite shape and teardown

A minimal suite: a setup file that creates ephemeral users/roles/tokens per role under
test, one Hurl file per (role × feature) pairing, and a teardown file that rolls back
everything the run wrote. Full layout convention, a transaction-snapshot teardown
pattern that needs no extra bookkeeping, and a copy-paste runner script:
[REFERENCE.md](REFERENCE.md#suite-shape-and-teardown).

## Checklist for new or changed policies

- [ ] SQL uses `{{…}}` for Aidbox params only, not JSONB path literals
- [ ] Suite covers allow **and** deny for every op the policy authorizes
- [ ] By-id SQL policies have by-id cases with real linked/unlinked fixtures
- [ ] Every `__debug=policy` block asserts `eval-result` **and** the `.id`/`.error` pair
- [ ] Live Aidbox reloaded after seed edits, not just disk
- [ ] Suite green end-to-end (setup → suites → teardown)

## What this style of test does not catch by default

- `:auth/policy-error` entries logged for policies that errored but weren't on the
  request path you asserted (scrape server logs in CI if you need this)
- A policy that is simply never evaluated for the role under test (no fixture exercises it)
- Seed drift — YAML fixed on disk, stale policy still live in the DB
