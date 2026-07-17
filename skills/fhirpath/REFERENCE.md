# FHIRPath — reference

Deep detail behind [SKILL.md](SKILL.md). FHIRPath is the HL7 spec expression language; this document covers the language rules that hold **everywhere**. How the expression is *invoked* is host-specific and lives in the owning skill (frontend TS wrapper, backend helpers, Questionnaire/FPML YAML) — see the pointers below.

## Where FHIRPath appears

| Host                               | Written as                                                 | Context variables                                   | Skill                                                              |
| ------------------------------------| ------------------------------------------------------------| -----------------------------------------------------| --------------------------------------------------------------------|
| Questionnaire (frontend-evaluated) | `calculatedExpression`, `enableWhenExpression`, `variable` | `%resource`, `%questionnaire`, `%qitem`, `%context` | [fhir-emr-questionnaire](../fhir-emr-questionnaire/SKILL.md)       |
| Questionnaire (backend-evaluated)  | `initialExpression`, `itemConstraint`                      | `%Questionnaire`, `%QuestionnaireResponse`          | [fhir-emr-questionnaire](../fhir-emr-questionnaire/SKILL.md)       |
| Extraction Mapping (FPML)          | `{{ ... }}` / `{[ ... ]}`                                  | `%QuestionnaireResponse`, `%assign`-ed vars         | [fhir-emr-mapping](../fhir-emr-mapping/SKILL.md)                   |
| Frontend TypeScript                | `compileAsFirst` / `compileAsArray` / `evaluate`           | passed explicitly                                   | [fhir-emr-frontend](../fhir-emr-frontend/REFERENCE.md#fhirpath-in-the-frontend) |
| Backend                            | server-side helpers (`compile_as_first` / `compile_as_array`) | server-provided                                  | [aidbox-python-conventions](../aidbox-python-conventions/SKILL.md) |

**FHIRPath ≠ FPML.** FPML is the Mapping templating language (`{% if %}`, `{% for %}`, `{% assign %}`); it only *hosts* FHIRPath inside its `{{ ... }}` / `{[ ... ]}` expression slots. FPML placement rules are in [fhir-emr-mapping](../fhir-emr-mapping/REFERENCE.md).

## Language rules (host-independent)

### Everything is a collection

Expressions return arrays; empty results (`{}`) are normal and propagate.

- Guard optional data with `.exists()`.
- Take singletons with `.first()` / `.single()`.
- An absent value surfaces as an empty collection (`{}`) / `undefined` depending on host — never assume required data unless a profile guarantees it.

### Sum, don't add

`A + B` returns `{}` when either operand is empty, so optional-field arithmetic silently breaks. Collect and `.sum()` instead:

```text
%resource.repeat(item)
  .where(linkId='intake-iv' or linkId='intake-oral')
  .answer.valueQuantity.value.sum()
```

`.sum()` ignores empty entries and returns `0` for an all-empty collection.

### Specific value[x] access

Use the typed accessor, not generic `.value`:

```text
.answer.valueString
.answer.valueCoding.code
.answer.valueQuantity.value
.answer.valueDateTime
```

### DateTime comparisons need `.toDateTime()`

The engine serialises `%variable` DateTimes as `String`; comparing a raw value to a variable throws `FP_DateTime did not match String`. Cast the variable:

```text
item.where(linkId='t').answer.valueDateTime.first() <= %CurrentTime.toDateTime()
```

### Answer lookup at any depth

`repeat(item)` recurses into nested groups:

```text
%resource.repeat(item).where(linkId='measurement-type').answer.valueCoding.code
%resource.repeat(item).where(linkId='has-symptoms').answer.valueString = 'yes'
%resource.repeat(item).where(linkId='diagnosis').answer.valueCoding.where(code='moderate').exists()
```

### Referencing the root is host-specific

How you name the root object depends on where the expression runs:

- **Frontend / backend** — the evaluator receives the resource as the root, so you may start from the bare resource type: `Patient.name.first()`, `Questionnaire.repeat(item).where(linkId=%linkId)`. This bare-root form works **only** here — avoid it in Questionnaire and Mapping YAML.
- **Questionnaire YAML** — access data through `%resource` (the QuestionnaireResponse) and `%questionnaire` (the Questionnaire); these are the preferred names. `%QuestionnaireResponse` / `%Questionnaire` are also supported on both frontend and backend. Details: [fhir-emr-questionnaire](../fhir-emr-questionnaire/SKILL.md).
- **FPML Mapping YAML** — access the source **only** as `%QuestionnaireResponse`. Details: [fhir-emr-mapping](../fhir-emr-mapping/SKILL.md).

### Prefer `%variables` over string interpolation

Expressions built with template strings break when values contain quotes or special characters. Pass values as context variables:

```text
Questionnaire.repeat(item).where(linkId=%linkId)     # value bound as %linkId
repeat(item).where(linkId='<interpolated>')          # riskier — quoting bugs
```

If interpolation is unavoidable, keep the interpolated value internal and constrained (e.g. known `linkId` values from a Questionnaire definition).

## Host-specific evaluation

The rules above are the language. How an expression is *invoked* — the API, context wiring, custom functions — belongs to each host and is documented in its own skill:

- **Frontend (TypeScript)** — the `src/utils/fhirpath.ts` wrapper (`compileAsFirst` / `compileAsArray` / `evaluate`, `initFHIRPathEvaluateOptions` custom functions, context passing, R4 model, display helpers): [fhir-emr-frontend](../fhir-emr-frontend/REFERENCE.md#fhirpath-in-the-frontend).
- **Backend (Python)** — `compile_as_first` / `compile_as_array` helpers in `app/utils/<resource>.py`: [aidbox-python-conventions](../aidbox-python-conventions/REFERENCE.md).
- **Questionnaire** — expressions are YAML strings evaluated by the SDC engine (frontend or backend context, see the table above): [fhir-emr-questionnaire](../fhir-emr-questionnaire/SKILL.md).
- **FPML Mapping** — expressions live in `{{ ... }}` / `{[ ... ]}` slots evaluated by the extraction engine: [fhir-emr-mapping](../fhir-emr-mapping/SKILL.md).

## Quick checklist

- Treat every result as a collection; handle `{}` / `undefined`.
- `.sum()` over a collection instead of `+` for optional values.
- Typed `value[x]` accessors, not generic `.value`.
- `.toDateTime()` when comparing DateTime variables.
- `%variables`/context over string interpolation.
- Invoke via the host's own helper/wrapper, not a raw evaluator (see host-specific pointers above).
