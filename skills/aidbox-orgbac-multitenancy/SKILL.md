---
name: aidbox-orgbac-multitenancy
description: Design and debug multi-tenant, organization-scoped authorization on Aidbox using OrgBAC, AccessPolicy, and the tenant-organization-id extension. Use when building per-organization data isolation, writing AccessPolicies that match a tenant, working with org-scoped FHIR or SDC routes (/Organization/{id}/fhir/...), or debugging "resource not available in Organization" errors, 403s that persist despite a passing policy, or the Reference.uri-vs-Reference.id tenant trap.
---

# Aidbox OrgBAC multi-tenancy

Organization-scoped authorization on Aidbox: each tenant is an `Organization`; clinician/admin users, patients, and clinical data are isolated to their org and reached through `/Organization/{org_id}/fhir/...` routes. Authorization is enforced by **two independent layers** plus a tenant marker on org-visible resources.

## The one rule to internalize: two checks per request

A request to `/Organization/{org_id}/fhir/...` must pass **both**, independently:

1. **AccessPolicy authorization** — does a policy match this user, role, and request?
2. **OrgBAC resource availability** — is the target resource *visible* under `/Organization/{org_id}/fhir`? Aidbox decides this from the resource's **tenant marker**, not from any AccessPolicy.

A passing policy is not enough. If OrgBAC says the resource isn't in the org you get:

```
Resource Practitioner/{id} is not available in Organization/{org_id}
```

The fix is almost never another AccessPolicy — it's the resource's `meta.extension[tenant-organization-id]`. See [REFERENCE.md](REFERENCE.md#two-checks-per-request).

## The tenant marker

Every org-visible resource (`Patient`, `Practitioner`, `PractitionerRole`, org-scoped `Role`, and clinician/admin `User`) carries:

```yaml
meta:
  extension:
    - url: https://aidbox.app/tenant-organization-id
      value:
        Reference:
          id: org-example
          resourceType: Organization
```

This **root shape** (`value.Reference.id`) is what OrgBAC visibility and AccessPolicies match against. FHIR request/response bodies show the same marker in **FHIR shape** (`valueReference.reference: Organization/org-example`) — same meaning, different serialization. When a mapping or seed *writes* the marker, produce root shape directly. Full detail: [REFERENCE.md](REFERENCE.md#tenant-extension-shape).

Patient-app `User` resources are the main exception: patient identity may flow through `Role.links.patient` instead of `User.meta.extension`. Check your identity model before adding a tenant marker to patient users. See [REFERENCE.md](REFERENCE.md#identity-model-tenant-relevant-parts).

## The #1 trap: `Reference.uri` vs `Reference.id`

If a write stores the marker as `value.Reference.uri: Organization/<id>` instead of `value.Reference.id: <id>`, OrgBAC visibility silently fails and policies matching `.params.organization/id` against `Reference.id` never fire. Symptom: a newly created user's first org-scoped read returns 403 even though the policy looks correct.

```yaml
value: { Reference: { uri: Organization/org-example } }               # ❌ breaks OrgBAC + policy match
value: { Reference: { id: org-example, resourceType: Organization } } # ✅ what OrgBAC and policies require
```

See [REFERENCE.md](REFERENCE.md#the-referenceuri-trap).

## Route param shapes differ by route type

| Route | Param exposed |
| --- | --- |
| Org-scoped FHIR resource (`/Organization/{id}/fhir/Patient`) | `params.organization/id` |
| Org-scoped SDC operation (`/Organization/{id}/fhir/Questionnaire/$extract`) | `params.org_id` |

Matching the wrong one silently fails. See [REFERENCE.md](REFERENCE.md#route-param-shape).

## Minimal tenant-scoped AccessPolicy

Always guard with `present?` so a missing route param doesn't accidentally match root `/fhir` requests:

```yaml
resourceType: AccessPolicy
engine: matcho
matcho:
  params:
    organization/id: present?          # REQUIRED guard
    resource/type: { $enum: [Organization, Practitioner, PractitionerRole, Patient] }
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

More patterns — per-role policy layers and the write-side (create/patch) policy shape: [REFERENCE.md](REFERENCE.md#policy-layers-per-role). Org-scoped SDC operation IDs and the transaction-bundle two-checks: [REFERENCE.md](REFERENCE.md#org-scoped-sdc-operations).

## Debug in one move

Append `?__debug=policy` to the failing request. If it shows:

```yaml
expected: { Contains: { value: { Reference: { id: .params.organization/id } } } }
but:      { value:    { Reference: { uri: Organization/<org_id> } } }
```

the tenant marker was stored as `Reference.uri` — fix the write, not the policy. Full verification ladder (root vs scoped reads, orgbac visibility search, system-shared org check): [REFERENCE.md](REFERENCE.md#verification-recipe).

## When adding or renaming seeds

Aidbox seed loading **upserts** — renaming a Questionnaire, Mapping, or AccessPolicy does not delete the old id. Stale ids keep authorizing old flows until deleted explicitly per environment. See [REFERENCE.md](REFERENCE.md#cleanup).
