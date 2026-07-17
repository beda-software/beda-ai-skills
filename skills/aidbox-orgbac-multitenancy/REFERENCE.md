# OrgBAC multi-tenancy — reference

Deep detail behind [SKILL.md](SKILL.md): tenant-extension shapes, AccessPolicy patterns, org-scoped SDC operations, the identity model, and a verification recipe. Examples use placeholder ids (`org-example`, `{org_id}`, `Example Clinic`); substitute your own.

Aidbox references:
- [Organization-based hierarchical access control](https://www.health-samurai.io/docs/aidbox/access-control/authorization/scoped-api/organization-based-hierarchical-access-control)
- [Allow patients to see their own data](https://www.health-samurai.io/docs/aidbox/tutorials/security-access-control-tutorials/allow-patients-to-see-their-own-data)
- [Flexible RBAC](https://www.health-samurai.io/docs/aidbox/tutorials/security-access-control-tutorials/rbac/flexible-rbac-built-in-to-aidbox)

## Roles

A typical role model layered on OrgBAC:

| Role | Scope | Access |
| --- | --- | --- |
| `admin` | global | unrestricted |
| `org-admin` | one organization | unrestricted within own org |
| `practitioner` | one organization | read-only on org resources |
| `patient` | self | unrestricted on own data |

Role names are conventions in your seeds, not Aidbox built-ins — what makes a clinician/admin role *org-scoped* is the tenant marker on its `User`, not the role name. Patient-app roles may instead resolve their org through the linked `Patient`.

## Two checks per request

A request to `/Organization/{org_id}/fhir/...` is authorized by two independent layers; **both** must pass.

1. **AccessPolicy authorization** — does any policy match this user, role, and request?
2. **OrgBAC resource availability** — is the target resource visible under `/Organization/{org_id}/fhir`? Aidbox decides this by the resource's tenant marker, not by AccessPolicy.

If the policy passes but OrgBAC says the resource isn't in the org:

```
Resource Practitioner/{id} is not available in Organization/{org_id}
```

The fix is the resource's `meta.extension[tenant-organization-id]`, not another policy. This visibility-vs-authorization split is the most common source of confusing 403s: a direct root `/fhir` read succeeds, the org-scoped read fails, and the AccessPolicy looks correct.

## Tenant extension shape

Aidbox stores the tenant marker in two shapes that look different but mean the same thing.

**FHIR resource bodies** (request payloads, FHIR API responses):

```yaml
meta:
  extension:
    - url: https://aidbox.app/tenant-organization-id
      valueReference:
        reference: Organization/org-example
        display: Example Clinic
```

**Aidbox root shape** (root `/Organization/{id}` reads, AccessPolicy debug context):

```yaml
meta:
  extension:
    - url: https://aidbox.app/tenant-organization-id
      value:
        Reference:
          id: org-example
          resourceType: Organization
          display: Example Clinic
```

The root shape is the one AccessPolicies match against. Mappings and seeds that generate org-visible resources should produce **root-shape** tenant metadata directly:

```yaml
meta:
  extension:
    - url: https://aidbox.app/tenant-organization-id
      value:
        Reference:
          id: "{{ %organizationId }}"
          resourceType: Organization
          display: "{{ %organizationDisplay }}"
```

### The `Reference.uri` trap

If a mapping writes the FHIR-shape `valueReference: { reference: Organization/<id> }`, Aidbox may store it internally as:

```yaml
# ❌ what a FHIR-shape write can become internally — OrgBAC + policies silently fail
value:
  Reference:
    uri: Organization/org-example

# ✅ the root shape OrgBAC visibility and .params matching require
value:
  Reference:
    id: org-example
    resourceType: Organization
```

`Reference.uri` is **not equivalent** to `Reference.id` for OrgBAC checks. OrgBAC visibility fails, and policies that match `.params.organization/id` against `Reference.id` do not fire. Newly created users then fail their first org-scoped read with a 403.

For ordinary FHIR business references (`PractitionerRole.organization`, `Patient.managingOrganization`, `Role.links.organization`, `Role.links.patient`) keep the normal FHIR shape — only the **tenant extension** needs root shape.

### `Organization` resources must be system-shared

The tenant `Organization` itself has to be visible across the org boundary, so mark it `system-shared`:

```yaml
meta:
  extension:
    - url: https://aidbox.app/tenant-resource-mode
      valueString: system-shared
```

A full `PUT /Organization/{id}` edit must preserve this extension.

**Normalization pitfall:** Aidbox normalizes `valueString: system-shared` into the typed-tuple form `{"value": {"string": "system-shared"}}` only when a resource goes through the **FHIR API** path. A direct file/watch-seed write can leave it as `{"valueString": "system-shared"}`, which the OrgBAC module does **not** recognize as system-shared — every read on the org-scoped path then returns 403 even though the read AccessPolicy passes. The resource looks identical under `_elements=meta` but the underlying jsonb differs. Fix: reseed through the init-bundle / FHIR API path (rebuild the bundle and restart Aidbox) so the resource is re-imported via the normalizing path.

## AccessPolicy patterns

### Tenant match

Matcho policies match tenant by comparing the user's tenant extension to the route's org param:

```yaml
matcho:
  user:
    meta:
      extension:
        $contains:
          url: https://aidbox.app/tenant-organization-id
          value:
            Reference:
              id: .params.organization/id
```

### Always require the route param

Without a `present?` guard, an equality between two missing values matches root `/fhir/...` requests by accident — leaking cross-tenant access:

```yaml
# ❌ no guard: on root /fhir the param is absent, so `id: .params.organization/id`
#    compares missing == missing and the policy matches — cross-tenant leak
matcho:
  user:
    meta:
      extension:
        $contains:
          url: https://aidbox.app/tenant-organization-id
          value: { Reference: { id: .params.organization/id } }

# ✅ require the route param first — the policy can only fire on org-scoped routes
matcho:
  params:
    organization/id: present?
  user:
    meta:
      extension:
        $contains:
          url: https://aidbox.app/tenant-organization-id
          value: { Reference: { id: .params.organization/id } }
```

Recommended read policy for a per-org role:

```yaml
resourceType: AccessPolicy
roleName: practitioner
engine: matcho
matcho:
  params:
    organization/id: present?
    resource/type:
      $enum: [Organization, Practitioner, PractitionerRole, Patient]
  request-method: get
  user:
    meta:
      extension:
        $contains:
          url: https://aidbox.app/tenant-organization-id
          value:
            Reference:
              id: .params.organization/id
```

`roleName: practitioner` is the field that scopes this policy to one role rather than to every tenant user. Aidbox resolves it against the `Role.name` of the `Role` linked to the requesting `User`, so the policy only fires for users in that role. It is orthogonal to the tenant match: the tenant-extension match enforces the org boundary for *any* role, while `roleName` selects *which* role the grant applies to. Express per-role differences by pairing the same tenant match with a different `roleName` and request scope — e.g. a `practitioner` policy with `request-method: get` for read-only, an `org-admin` policy that also authorizes writes. ("Role names are conventions" means Aidbox has no built-in role *semantics* — not that `roleName` is ignored.)

### Route param shape

The two org-scoped route families expose the tenant id under **different param names**, so each policy must read the one its route provides (the route→param table is in [SKILL.md](SKILL.md#route-param-shapes-differ-by-route-type)):

- **FHIR resource** routes (`/Organization/{id}/fhir/Patient`) → `params.organization/id` — used by resource read/write policies.
- **SDC operation** routes (`/Organization/{id}/fhir/Questionnaire/$extract`) → `params.org_id` — used by the SDC-operation policy shown below.

Matching the wrong name silently fails: the tenant comparison evaluates against a missing value and never fires.

### Policy layers per role

Authorization is granular per **(operation, resource type, role)**. A create/edit flow that goes through org-scoped SDC needs a *separate* policy layer for each of these — authorizing `$extract` and the transaction wrapper is **not** enough, because the wrapper and every inline entry are checked independently (see [Two checks per *entry*, too](#two-checks-per-entry-too)):

| Layer | What it authorizes |
| --- | --- |
| Outer SDC op | `$populate` / `$extract` / `$constraint-check`, matches `params.org_id` |
| Read forms | `Questionnaire`, `Mapping` via the org-scoped route |
| Read org resources | the resource types the role may read, in its own org |
| Submit transaction | `orgbac-fhir-bundle` (the transaction wrapper) |
| Create entries | each created resource type via `orgbac-fhir-create` |
| Patch entries | each patched resource type via `orgbac-fhir-patch` |

Each layer is an independent policy; a missing entry-level policy passes the wrapper but fails with `Transaction failed at entry[0]. Response status is 403`.

A write-side policy mirrors the read policy but targets the write route (which exposes `params.organization/id`, not `params.org_id`) and the entry resource types the role creates:

```yaml
resourceType: AccessPolicy
roleName: org-admin
engine: matcho
matcho:
  params:
    organization/id: present?
  resource/type:
    $enum: [Practitioner, PractitionerRole, User, Role]   # the entry types this role creates
  request-method: post
  user:
    meta:
      extension:
        $contains:
          url: https://aidbox.app/tenant-organization-id
          value:
            Reference:
              id: .params.organization/id
```

Confirm the exact matcho key against an existing write policy in your seeds: depending on setup you may match `operation: { id: orgbac-fhir-create }` instead of `request-method: post`. The patch layer is the same shape with the patch operation and the resource types that role edits.

### Avoid `Reference.uri` debug policies

Don't keep temporary policies that match `Reference.uri` under a production policy id. If a compatibility/debug policy is needed, use a distinct id and document why — otherwise it masks the real `Reference.id` bug and quietly widens access.

## Org-scoped SDC operations

SDC (Structured Data Capture) form workflows for org-scoped roles route through the org-scoped FHIR base URL:

```http
POST /Organization/{org_id}/fhir/Questionnaire/$populate
POST /Organization/{org_id}/fhir/Questionnaire/$extract
POST /Organization/{org_id}/fhir/QuestionnaireResponse/$constraint-check
```

The session must belong to `{org_id}`. The outer SDC operation proves org scope; the resources `$extract` produces must still carry the tenant marker.

### Two checks per *entry*, too

`$extract` builds a FHIR transaction `Bundle` and posts it back through the org-scoped FHIR client. **Aidbox authorizes the transaction wrapper AND each inline entry separately.** `$extract` being allowed is not enough — the transaction and every entry are checked. A failing entry surfaces as:

```
Transaction failed at entry[0]. Response status is 403
```

### Operation IDs differ from root FHIR

Org-scoped FHIR writeback uses different operation IDs than root FHIR routes:

| Action | Root FHIR | Org-scoped FHIR |
| --- | --- | --- |
| Transaction | `FhirTransaction` | `orgbac-fhir-bundle` |
| Create resource | `FhirCreate` | `orgbac-fhir-create` |
| Patch resource | `FhirPatch` | `orgbac-fhir-patch` |

Policies for these SDC/writeback flows are org-scoped — they do **not** grant root FHIR access.

### SDC-operation policies match `params.org_id`

```yaml
uri: "#^/Organization/.+/fhir/Questionnaire/\\$extract$"
user:
  meta:
    extension:
      $contains:
        url: https://aidbox.app/tenant-organization-id
        value:
          Reference:
            id: .params.org_id
```

### Transaction entry URLs are resource-relative

Bundle entry `request.url` must be resource-relative:

```yaml
# ✅ resource-relative — org scope comes from the OUTER request URL
url: /Practitioner
url: /PractitionerRole
url: /User
url: /Role

# ❌ org path baked into the entry — NOT equivalent to POSTing the txn to /Organization/{id}/fhir
url: Organization/org-example/Practitioner
```

That is not equivalent to submitting the whole transaction to `POST /Organization/org-example/fhir`. Org scoping comes from the *outer* request URL, not from each entry. Generated resources still need the tenant marker written into their bodies.

### Debugging org-scoped SDC

Start with `?__debug=policy` on the failing request. If `$extract` itself is allowed but the response says `Transaction failed at entry[0]. Response status is 403`, the outer SDC policy is fine — debug the inline entry:

```http
POST /Organization/{org_id}/fhir/Patient?__debug=policy
POST /Organization/{org_id}/fhir/Practitioner?__debug=policy
```

If a direct root `/fhir` call succeeds but `/Organization/{org_id}/fhir` fails, check the `orgbac-*` operation IDs and the `params.organization/id` tenant match.

## Identity model (tenant-relevant parts)

For clinician/admin identities, the tenant marker lives on `User`; role and links live on `Role`. Patient-app identities are different: the patient `User` may omit the tenant marker and authorize through `Role.links.patient` plus patient-specific policies. A minimal clinician/admin wiring:

```
     User ──────────────────────────────┐
      │  meta.extension                  ▼
      │  [tenant-organization-id] ──► Organization  (authoritative org pointer)
      │
      │  Role.user
      ▼
     Role  name: admin | org-admin | practitioner | patient
      ├── links.organization      ──► Organization   (admin / org-admin)
      ├── links.practitioner       ──► Practitioner
      ├── links.practitionerRole   ──► PractitionerRole
      └── links.patient            ──► Patient
```

- Clinician/admin `User` carries the **authoritative** tenant marker via `meta.extension[tenant-organization-id]`. This is what AccessPolicies and the `User:organization` search parameter resolve.
- Patient-app `User` resources may intentionally omit the tenant marker; patient identity flows through `Role.links.patient` and patient-specific OrgBAC policies. Do not add a tenant marker to patient users unless the local flow's docs and seeds already do.
- `Role.links.organization` is convenient for session role context, but it does **not** replace the `User` tenant marker that policies match on.
- Expected created-`User` shape (root shape):

```yaml
User:
  meta:
    extension:
      - url: https://aidbox.app/tenant-organization-id
        value:
          Reference:
            id: <organization-id>
            resourceType: Organization
```

To resolve the tenant marker in searches, seed a `User:organization` SearchParameter. The expression must use `value.ofType(Reference)`, not `valueReference`; Aidbox stores extension values internally as `value.Reference`, and the `valueReference` form silently matches nothing:

```yaml
resourceType: SearchParameter
base: [User]
code: organization
type: reference
expression: User.meta.extension.where(url='https://aidbox.app/tenant-organization-id').value.ofType(Reference)
```

## Verification recipe

After creating an organization and a user (e.g. a practitioner) in it:

**1. Organization is system-shared.**

```http
GET /Organization/{org_id}
```
```yaml
meta.extension:
  - url: https://aidbox.app/tenant-resource-mode
    value: { string: system-shared }
```

**2. Created resources carry the root-shape tenant marker.**

```http
GET /User/{user_id}
GET /Role/{role_id}
GET /Practitioner/{practitioner_id}
GET /PractitionerRole/{practitioner_role_id}
```
```yaml
value:
  Reference:
    id: <org_id>
    resourceType: Organization
```

**3. Org-scoped reads return 200.**

```http
GET /Organization/{org_id}/fhir/Practitioner/{practitioner_id}       → 200
GET /Organization/{org_id}/fhir/PractitionerRole/{practitioner_role_id} → 200
```

**4. OrgBAC visibility (search variant).**

```http
GET /Organization/{org_id}/fhir/Practitioner?_id={practitioner_id}   → total: 1
```

**5. Log in as the created user; root vs scoped read.**

```http
GET /fhir/Patient                       → 403
GET /Organization/{org_id}/fhir/Patient → 200
```

**6. Policy debug.**

```http
GET /Organization/{org_id}/fhir/Practitioner/{id}?__debug=policy
```

Expected:

```yaml
policy-id: <your-read-policy-id>
eval-result: true
```

If debug shows `expected … Reference.id … but … Reference.uri …`, the user's tenant extension was stored as `Reference.uri` (see [The `Reference.uri` trap](#the-referenceuri-trap)).

Also confirm login `userinfo` exposes root-shape tenant metadata. If the frontend shows something like "user with no roles", the scoped FHIR base URL may not be configured, or linked resources aren't visible under OrgBAC.

## Cleanup

Aidbox seed loading **upserts**. Renaming a Questionnaire, Mapping, AccessPolicy, or SearchParameter does not remove the old id — stale ids keep authorizing old flows until deleted explicitly per environment. Delete the old id when you rename.

## Common pitfalls checklist

- Passing AccessPolicy but 403 → check OrgBAC visibility / the tenant marker, not the policy.
- Tenant marker stored as `Reference.uri` instead of `Reference.id` → OrgBAC + policies silently fail.
- Root-shape vs FHIR-shape tenant extension confusion when a mapping writes the marker.
- `params.org_id` (SDC operation routes) vs `params.organization/id` (FHIR resource routes).
- Missing `present?` guard → policy leaks root `/fhir` access across tenants.
- Transaction entry URLs that encode an org path instead of being resource-relative.
- `system-shared` written outside the FHIR API path → not recognized, org reads 403.
- Renamed seed ids left undeleted → stale policies keep granting old access.
