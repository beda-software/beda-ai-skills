# Beda SDC forms — reference

Deep detail behind [SKILL.md](SKILL.md): the full lifecycle, launch options, loaders and save services, custom widgets, extraction, drafts, the SDC backend choice, and the FCE seed pipeline. Examples use placeholder ids (`org-example`, `my-questionnaire-id`); substitute your own. Tenant/policy mechanics for org-scoped routes live in the sibling skill [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md); FHIRPath conventions in [FHIRPATH.md](FHIRPATH.md).

## Architecture

```
FHIR server (SDC operations: $populate / $extract / $constraint-check)
  ↑
QuestionnaireResponseForm          ← high-level wrapper
  └── BaseQuestionnaireResponseForm ← core renderer (react-hook-form + yup)
        └── QuestionnaireResponseFormProvider (sdc-qrf)
              ├── Question items: QuestionString, QuestionChoice, ...
              └── Group items: Group, Row, GroupWizard, GroupTable, ...
```

Key packages / library paths (the `fhir-emr` library is typically vendored under `contrib/fhir-emr/`):

- `sdc-qrf` — `mapFormToResponse`, `mapResponseToForm`, `toFirstClassExtension`
- `components/BaseQuestionnaireResponseForm/` — rendering
- `hooks/questionnaire-response-form-data.ts` — data lifecycle
- `services/questionnaire.ts` — FHIR service calls

## Lifecycle

```
Load
  Questionnaire (id or fn) → /$assemble → toFirstClassExtension
  → /Questionnaire/$populate → mapResponseToForm → formValues

Render
  BaseQuestionnaireResponseForm renders by item type + itemControl;
  enableWhen / calculatedExpression evaluated in real time.

Submit
  removeDisabledAnswers → mapFormToResponse → /QuestionnaireResponse/$constraint-check
  → save QR (or keep in memory) → /Questionnaire/$extract → Bundle
```

- **`$assemble`** resolves sub-questionnaires and modular pieces into one Questionnaire. Skip it with a raw loader when the Questionnaire is already self-contained.
- **`$populate`** fills initial answers from launch context (e.g. patient demographics) and `initialExpression` FHIRPath.
- **`$constraint-check`** validates the assembled `QuestionnaireResponse` server-side before save/extract.
- **`$extract`** transforms the QR into FHIR resources via the Questionnaire's mapper.

Clinical-document flows persist the QR; org-scoped create/edit flows use `inMemorySaveService` (validate + extract, no QR draft).

## Launching a form

The recommended path for clinical docs is `PatientDocument`:

```tsx
import { PatientDocument } from '@beda.software/emr/containers';

<PatientDocument
    patient={patient}
    author={practitioner}
    questionnaireId="my-questionnaire-id"
    encounterId={encounterId}
    launchContextParameters={[{ name: 'Encounter', resource: encounter }]}
    onSuccess={(response) => { /* navigate / refresh */ }}
    autoSave={false}
    qrDraftServiceType="local"   // 'local' | 'server'
/>
```

Other entry points (use when the situation calls for it):

- `QuestionnaireResponseForm` from `@beda.software/emr/components` — general-purpose, accepts a custom `questionnaireLoader` and `questionnaireResponseSaveService`.
- `QuestionnaireModal` from `@beda.software/emr/uberComponents` — quick modal for one-off forms.
- Patient-facing URL: `/patient-questionnaire?patient=<id>&questionnaire=<id>&encounter=<id>`.

### Launch context parameters

| Name | Resource | Purpose |
| --- | --- | --- |
| `Patient` | Patient | Current patient |
| `Author` | Practitioner \| Organization | Form author |
| `Encounter` | Encounter | Current encounter |
| `Provenance` | Provenance | Audit trail |
| `LaunchPatient` | Patient | Alternative patient reference |

These are consumed by `$populate` and by `launchContext` / `initialExpression` FHIRPath in the Questionnaire.

## Loaders and save services

```typescript
import {
    questionnaireIdLoader,           // load by id + /$assemble
    questionnaireIdWOAssembleLoader, // load by id, skip /$assemble (used by org-scoped flows)
} from '@beda.software/emr/hooks';

import {
    inMemorySaveService,              // no QR persistence (org-scoped, preview)
    persistSaveService,               // saves QR to FHIR
    persistWithProvenanceSaveService, // saves QR + Provenance
} from '@beda.software/emr/hooks';
```

**Loader — pick by whether the Questionnaire is modular:**

| Loader | Use when |
| --- | --- |
| `questionnaireIdLoader` | Questionnaire is assembled from sub-questionnaires / modular pieces (runs `/$assemble`). |
| `questionnaireIdWOAssembleLoader` | Questionnaire is already self-contained, or an org-scoped flow — skip `/$assemble`. |

**Save service — pick by what should persist:**

| Save service | Persists | Use when |
| --- | --- | --- |
| `persistSaveService` | QR | Clinical documents that must be stored and re-openable. |
| `persistWithProvenanceSaveService` | QR + Provenance | Same, with an audit trail. |
| `inMemorySaveService` | nothing (validate + extract only) | Org-scoped create/edit and preview flows where only the extracted resources matter. |

Mismatch symptoms: choosing `inMemorySaveService` when you expected a re-openable draft → nothing persists; using an assemble loader on a self-contained form → an extra `/$assemble` round trip and possible shape surprises.

## Supported SDC extensions

### itemControl — questions

| Code | Description |
| --- | --- |
| `inline-choice` | Inline radio / checkbox |
| `solid-radio-button` | Styled radio buttons |
| `slider` | Range slider (start/stop/step) |
| `phoneWidget` | Phone number input |
| `email` | Email field |
| `passwordWidget` | Password input |
| `text-with-macro` | Text with macro expansion |
| `input-inside-text` | Input embedded in surrounding text |
| `markdown-editor` | Markdown editor |
| `audio-recorder-uploader` | Audio recording + upload |
| `barcode` | Barcode scanner |
| `markdown`, `markdown-card` | Display-only markdown |
| `anxiety-score`, `depression-score` | Example custom clinical score widgets |

### itemControl — groups

| Code | Description |
| --- | --- |
| `col` (default) | Column layout |
| `row` | Row layout |
| `gtable`, `table` | Table layout |
| `grid` | Grid layout |
| `section`, `section-with-divider` | Section headers |
| `main-card`, `sub-card` | Card containers |
| `wizard`, `wizard-with-tooltips` | Horizontal multi-step wizard |
| `wizard-vertical` | Vertical multi-step wizard |
| `group-tabs` | Tab-based group |
| `group-table` | Repeatable group as table |
| `editable-group` | Inline editable repeatable group |
| `blood-pressure` | Systolic/diastolic input pair |
| `time-range-picker` | Start/end time selector |

### Other

- `enableWhen` — conditional visibility (`=`, `!=`, `<`, `<=`, `>`, `>=`, `exists`).
- `answerExpression` — dynamic options via FHIRPath.
- `calculatedExpression` — auto-calculated values.
- `initialExpression` — initial value from launch context (see [FHIRPATH.md](FHIRPATH.md#questionnaire-usage)).
- `launchContext` — context parameters available at populate time.
- FHIRPath is evaluated server-side via the SDC backend.

## Custom widgets

Register a component against an `itemControl` code. Question-level and group-level components use separate maps:

```tsx
<BaseQuestionnaireResponseForm
    formData={formData}
    itemControlQuestionItemComponents={{ 'my-custom-control': MyCustomQuestion }}
    itemControlGroupItemComponents={{ 'my-custom-group': MyCustomGroup }}
    onSubmit={handleSubmit}
/>
```

A custom question component receives:

```typescript
interface QuestionItemProps {
    parentPath: string[];
    questionItem: FCEQuestionnaireItem;
    context: ItemContext;   // group items receive ItemContext[]
}
```

Read/write the answer through the shared form context (`react-hook-form` state seeded from `parentPath` + the item `linkId`) rather than local state, so `enableWhen`, `calculatedExpression`, and extraction see the value. Before writing a widget, check the built-in itemControl tables above — most layouts already exist.

## Extraction

After saving the QR (or keeping it in memory), the library calls `POST /Questionnaire/$extract` automatically. The Questionnaire must define extraction (template extraction or StructureMap). The result is a `Bundle` of FHIR resources.

With `persistSaveService`, extraction errors are **non-blocking** — the QR is saved and `extractedError` is returned. With `inMemorySaveService` no QR is persisted, so a failed extract leaves nothing behind.

### Mapping execution

`$extract` runs the mapper from the Questionnaire's mapper extension. For root/admin flows the selected organization in the QR is **payload data** — it does **not** turn the request into an org-scoped one. Root flows that create resources for a chosen org must explicitly write tenant metadata into the generated bodies (see [aidbox-orgbac-multitenancy — tenant extension shape](../aidbox-orgbac-multitenancy/REFERENCE.md#tenant-extension-shape)).

Mapping-authoring conventions (variable extraction, `.exists()` guards, `Provenance.target` for edit flows) are in [FHIRPATH.md](FHIRPATH.md#mapping-resource-patterns).

### Transaction entry URLs

Bundle entry `request.url` is **resource-relative**:

```yaml
# ✅ resource-relative — org scope comes from the OUTER request URL
url: /Practitioner
url: /PractitionerRole
url: /User
url: /Role

# ❌ org path baked into the entry — NOT equivalent to POSTing the txn to /Organization/{id}/fhir
url: Organization/org-example/Practitioner
```

Org scoping comes from the *outer* request URL, not from each entry. When the outer request is org-scoped, Aidbox authorizes the transaction wrapper **and each inline entry independently** — a create/edit flow needs a policy per (operation, resource type, role), and a missing entry-level policy surfaces as `Transaction failed at entry[0]. Response status is 403`. Full detail: [aidbox-orgbac-multitenancy — org-scoped SDC operations](../aidbox-orgbac-multitenancy/REFERENCE.md#org-scoped-sdc-operations).

## Drafts

Auto-save drafts via `qrDraftServiceType` on `PatientDocument`, or pass a `questionnaireResponseDraftService`:

```typescript
import { getQuestionnaireResponseDraftServices } from '@beda.software/emr/hooks';

getQuestionnaireResponseDraftServices('local');   // localStorage
getQuestionnaireResponseDraftServices('server');  // server-side in-progress QR
```

## SDC backend: current FHIR base vs standalone fhir-sdc

SDC operations can be served by **Aidbox's built-in SDC module** or by the standalone [`beda-software/fhir-sdc`](https://github.com/beda-software/fhir-sdc) Python service (registered as an app).

Strict access control on SDC ops is enabled via compose env:

```yaml
BOX_MODULE_SDC_STRICT_ACCESS_CONTROL: true
```

`sdcBackendUrl` (in your EMR config) selects where frontend SDC operations go:

- `null` → operations route through the **current FHIR base URL**. After login, a post-login hook sets that base to the scoped route (`{baseURL}/Organization/{org_id}/fhir`), so SDC ops land org-scoped:

  ```http
  POST /Organization/{org_id}/fhir/Questionnaire/$populate
  POST /Organization/{org_id}/fhir/Questionnaire/$extract
  POST /Organization/{org_id}/fhir/QuestionnaireResponse/$constraint-check
  ```

- a URL → operations route to that **separate SDC backend** instead of the current FHIR base. Do this only deliberately; it changes whether requests inherit the org-scoped FHIR base URL and therefore changes the authorization/debugging surface.

## FCE seed pipeline

Questionnaires are authored in **FCE** (First Class Extension — SDC extensions as native YAML properties), converted to standard FHIR by an `fce-fhir-converter` during the seed build, and loaded into the server via `BOX_INIT_BUNDLE`. A typical dev compose stack:

| Service | Image (example) | Purpose |
| --- | --- | --- |
| `postgres` | `postgres:18` | DB |
| `aidbox` | `healthsamurai/aidboxone:latest` | FHIR server + SDC |
| `questionnaire-fce-fhir-converter` | `bedasoftware/questionnaire-fce-fhir-converter:latest` | Converts FCE → plain FHIR at seed-build time |
| `build-seeds` | `bedasoftware/fhirsnake:latest` | `resources/init-seeds/` → `bundle.json` |
| `build-dev-seeds` | `bedasoftware/fhirsnake:latest` | `resources/demo-seeds/` → `dev-bundle.json` |
| `upload-dev-seeds` | `curlimages/curl` | POSTs `dev-bundle.json` on startup |
| `watch-seeds-init` | `bedasoftware/fhirsnake:latest` | Watches seeds and re-uploads on change |

To add a Questionnaire seed:

1. Drop YAML in `resources/init-seeds/Questionnaire/my-form.yaml` (seed directory name varies by project).
2. Run `docker compose run --rm build-seeds` to regenerate `bundle.json`.
3. Restart the server (re-loads `bundle.json` from `BOX_INIT_BUNDLE`).

Author in FCE, not hand-written FHIR SDC: the native-property YAML is what the converter expects, and it keeps `enableWhen` / `itemControl` / expressions readable.

### Cleanup — seeds upsert

Seed loading **upserts**: renaming a Questionnaire or Mapping does not delete the old id — the stale resource keeps serving old flows until you delete it explicitly per environment. Delete the old id when you rename. (Same upsert caveat applies to AccessPolicy and SearchParameter seeds — see [aidbox-orgbac-multitenancy — cleanup](../aidbox-orgbac-multitenancy/REFERENCE.md#cleanup).)

## Common pitfalls checklist

- Form change not showing → rebuild the seed bundle and restart the server (Questionnaires are compiled seeds).
- Renamed Questionnaire/Mapping but old one still fires → seeds upsert; delete the stale id.
- Expected a re-openable draft but nothing persisted → `inMemorySaveService` persists no QR; use `persistSaveService`.
- Extra `/$assemble` round trip / wrong assembled shape → used an assemble loader on a self-contained form.
- `$extract` 403 on an org-scoped route → the transaction wrapper and every entry are authorized independently; add the missing per-entry policy.
- Org path baked into a transaction entry URL → make entry URLs resource-relative; scope comes from the outer request.
- Root/admin extract created resources with no tenant marker → write tenant metadata into the generated bodies.
- Custom widget value ignored by `enableWhen` / extraction → write through form context, not local state.
