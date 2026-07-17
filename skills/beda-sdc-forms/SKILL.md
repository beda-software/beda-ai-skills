---
name: beda-sdc-forms
description: Build, seed, and debug SDC (Structured Data Capture) Questionnaire forms in a Beda EMR / Aidbox app — the $populate → render → $constraint-check → $extract lifecycle, the FCE-to-FHIR seed pipeline, questionnaire loaders and save services, custom item widgets, and compiled-FHIRPath conventions. Use when adding or launching a Questionnaire, wiring PatientDocument / QuestionnaireResponseForm, writing extraction Mappings, picking a loader or save service, building a custom itemControl widget, debugging why a form change won't show (rebuild + restart) or why $extract or a transaction entry 403s, or writing FHIRPath in forms, columns, or Mappings.
---

# Beda SDC forms

SDC (Structured Data Capture) is the form mechanism in a Beda EMR build. Forms are FHIR `Questionnaire` resources rendered by `sdc-qrf` + the `fhir-emr` React components, backed by SDC operations on the FHIR server (Aidbox's built-in SDC module, or a standalone `fhir-sdc` service). Two things to internalize before touching a form:

1. **A form is a pipeline of server operations on a Questionnaire** — `$populate`, `$constraint-check`, `$extract`. Most "why is my form doing X" traces back to one of these three.
2. **Each Questionnaire is a compiled seed artifact.** You author it in FCE and it is converted to plain FHIR at seed-build time — so a form change is invisible until you rebuild the bundle and restart the server.

## The lifecycle

```
Load     Questionnaire (id or fn) → /$assemble → toFirstClassExtension
         → /Questionnaire/$populate → mapResponseToForm → formValues
Render   BaseQuestionnaireResponseForm renders by item type + itemControl;
         enableWhen / calculatedExpression evaluated in real time
Submit   removeDisabledAnswers → mapFormToResponse
         → /QuestionnaireResponse/$constraint-check
         → save QR (or keep in memory) → /Questionnaire/$extract → Bundle
```

SDC operation URLs are relative to the current FHIR base URL. After login that base is typically the org-scoped route, so the three ops land on `/Organization/{org_id}/fhir/Questionnaire/$populate` etc. — see [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md) for the tenant/policy mechanics. Full lifecycle, launch-context table, and drafts: [REFERENCE.md](REFERENCE.md#lifecycle).

## Questionnaires are compiled seeds (FCE → FHIR)

Questionnaires are written in **FCE** (First Class Extension — SDC extensions as native YAML properties), converted to standard FHIR by an `fce-fhir-converter` during the seed build, and loaded via `BOX_INIT_BUNDLE`. To add or change one:

1. Edit YAML under `resources/init-seeds/Questionnaire/my-form.yaml` (path may vary by repo — check your project's seed directory).
2. Run `docker compose run --rm build-seeds` to regenerate `bundle.json`.
3. Restart the server so it re-loads `bundle.json`.

Seed loading **upserts** — renaming a Questionnaire or Mapping leaves the old id in place until you delete it explicitly. Pipeline, converter, and dev-seed watch flow: [REFERENCE.md](REFERENCE.md#fce-seed-pipeline).

## Launching a form

Prefer `PatientDocument` for clinical docs; it wires loader + save service for you:

```tsx
import { PatientDocument } from '@beda.software/emr/containers';

<PatientDocument patient={patient} author={practitioner}
    questionnaireId="my-questionnaire-id" encounterId={encounterId}
    launchContextParameters={[{ name: 'Encounter', resource: encounter }]}
    onSuccess={(response) => { /* navigate / refresh */ }}
    autoSave={false} qrDraftServiceType="local" />
```

Other entry points (`QuestionnaireResponseForm`, `QuestionnaireModal`, the patient-facing URL): [REFERENCE.md](REFERENCE.md#launching-a-form).

## Loaders and save services

The loader decides how the Questionnaire is fetched; the save service decides what happens to the `QuestionnaireResponse` on submit. Org-scoped create/edit flows typically use `inMemorySaveService`. Pick deliberately — the wrong pair is a common source of "extraction ran but nothing persisted" or "form assembled the wrong shape". Decision tables: [REFERENCE.md](REFERENCE.md#loaders-and-save-services).

## Custom widgets

Register a component against an `itemControl` code; the built-in codes cover most layouts (`slider`, `wizard`, `gtable`, `blood-pressure`, …):

```tsx
<BaseQuestionnaireResponseForm formData={formData} onSubmit={handleSubmit}
    itemControlQuestionItemComponents={{ 'my-control': MyCustomQuestion }}
    itemControlGroupItemComponents={{ 'my-group': MyCustomGroup }} />
```

Built-in itemControl tables + the `QuestionItemProps` contract: [REFERENCE.md](REFERENCE.md#custom-widgets).

## Extraction and the transaction-entry-URL rule

`$extract` runs the Questionnaire's mapper and returns a FHIR transaction `Bundle`. Bundle entry `request.url` is **resource-relative** — never bake an org path into it:

```yaml
url: /Practitioner                              # ✅ org scope comes from the OUTER request URL
url: Organization/org-example/Practitioner      # ❌ NOT equivalent to POSTing the txn org-scoped
```

Root/admin flows that create resources for a chosen org must write the tenant marker into the generated bodies themselves — the selected org in the QR is payload data, not request scope. Extraction errors, mapping execution, and the per-entry authorization traps: [REFERENCE.md](REFERENCE.md#extraction) and [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/REFERENCE.md#org-scoped-sdc-operations).

## FHIRPath in forms and Mappings

Use the `fhir-emr` `src/utils/fhirpath.ts` wrapper, never `fhirpath.evaluate` directly — compile static/repeated expressions with `compileAsFirst` / `compileAsArray`, use `evaluate` for runtime expressions, and pass context via `%variables` rather than string interpolation. Conventions, Mapping-template patterns, and custom-function registration: [FHIRPATH.md](FHIRPATH.md).
