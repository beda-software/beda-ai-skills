---
name: aidbox-access-policy-tests
description: >-
  Aidbox AccessPolicy Hurl tests (__debug=policy, eval-result, allow/deny
  fixtures). Use when writing or extending a Hurl suite for role-based or
  own-scoped access, when adding or changing AccessPolicy YAML, or when a policy
  test passed despite :auth/policy-error or a SQL syntax error in the logs.
---

# Aidbox AccessPolicy Hurl tests

Prove an `AccessPolicy` allows and denies what it should, using [Hurl](https://hurl.dev)
against a running Aidbox with `BOX_SECURITY_DEV_MODE=true`. The *why* of a policy lives in
[aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md); this skill proves it
with real requests.

## The trap: errored policies are silent

Policies form an allowlist: Aidbox tries candidates until one returns `eval-result: true`,
else `403`. A `sql`/`complex` policy whose query throws is logged as `:auth/policy-error`,
counts as not-allowed, and evaluation **continues**. If any other policy allows the request
the caller sees HTTP 200 while the policy under test never worked, so the outer status
proves nothing. Mechanics (including how `complex` + `and:` pollutes unrelated operations):
[REFERENCE.md](REFERENCE.md#how-aidbox-evaluates-policies).

## Steps

1. **Write the SQL.** Aidbox params take double braces: `{{user.fhirUser.id}}`,
   `{{params.resource/id}}`. Single-brace `{user.fhirUser.id}` reaches Postgres verbatim
   (`syntax error at or near "{"`). Postgres JSONB path literals (`#>> '{subject,id}'`)
   keep single braces. Done when only dotted Aidbox paths (`user.…`, `params.…`, `role.…`)
   are doubled.
2. **Reload the seed.** Confirm the live Aidbox holds the edited YAML (watch-seeds,
   seed-loader, or admin `PUT`); disk and DB drift silently. Done when the live policy
   matches disk.
3. **Seed fixtures as admin**, asserting `HTTP 201`. A failed fixture create makes a later
   allow case fail for missing data and reads as a policy bug. Prefix ids with `{{run_id}}`
   so teardown finds them.
4. **Test allow and deny for every operation the policy authorizes.** For own-scoped SQL
   policies (read/patch/update/delete by id) that means by-id requests against a resource
   *linked* to the acting identity (allow) and the same op against an *unlinked* resource
   of someone else (deny). Search and create alone leave the `WHERE` clause unexercised: a
   no-op that matches everyone would pass.
5. **Assert the dump on every `__debug=policy` request.** The flag returns HTTP 200 with a
   policy dump whether the real request would be allowed or denied, so the assertions
   carry the verdict. Pair `eval-result` with the `.id`/`.error` projections:

   **Allow:**

   ```hurl
   HTTP 200
   [Asserts]
   jsonpath "$.policies[?(@['eval-result'] == true)]" exists
   jsonpath "$.policies[?(@.error)].id" not exists
   jsonpath "$.policies[?(@.error)].error" not exists
   ```

   **Deny:**

   ```hurl
   HTTP 200
   [Asserts]
   jsonpath "$.policies[?(@['eval-result'] == true)].id" not exists
   jsonpath "$.policies[?(@.error)].id" not exists
   jsonpath "$.policies[?(@.error)].error" not exists
   ```

   Projecting `.id` and `.error` makes a failure name the policy and the SQL error. Field
   names are kebab-case (`eval-result`); a SQL failure is singular `error`, a matcho
   mismatch is plural `errors`. Detail: [REFERENCE.md](REFERENCE.md#why-project-id--error).
6. **Run the suite end to end** (setup → suites → teardown). Layout, isolated client,
   ephemeral identities, transaction-snapshot teardown, runner script:
   [REFERENCE.md](REFERENCE.md#suite-shape-and-teardown).

## Done when

- [ ] Allow **and** deny cover every authorized op, by-id ones against linked and unlinked fixtures
- [ ] Every `__debug=policy` block carries `eval-result` plus the `.id`/`.error` pair
- [ ] Fixture creates assert `HTTP 201`
- [ ] Suite green under the runner script

Blind spots: `:auth/policy-error` logged on paths no request asserted (scrape server logs
in CI), policies no fixture reaches, and seed drift.
