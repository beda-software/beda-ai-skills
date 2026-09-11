---
name: fhirpath
description: Write and debug FHIRPath — the HL7 spec expression language — anywhere it appears in a Beda EMR / fhir-emr codebase: Questionnaire expression fields (calculatedExpression, enableWhenExpression, initialExpression, itemConstraint, variables), FPML extraction Mappings (expressions embedded in {{ }} and {[ ]} slots), frontend TypeScript (src/utils/fhirpath.ts wrapper — compileAsFirst / compileAsArray / evaluate), and backend FHIRPath helpers. Use when writing or debugging any FHIRPath expression, choosing specific value[x] access, handling empty-collection semantics (sum() vs +), casting with toDateTime(), passing %variables/context, or picking a compiled vs runtime evaluator. FHIRPath is the spec expression syntax and is NOT FPML — FPML is the Mapping templating language that merely hosts FHIRPath (see fhir-emr-mapping).
---

# FHIRPath

FHIRPath is the [HL7 spec expression language](https://build.fhir.org/ig/HL7/FHIRPath/) for navigating and computing over FHIR data. In this codebase the **same expression syntax** shows up in four places, which is why it is a skill of its own:

| Where | How FHIRPath is written | Authoring skill |
| --- | --- | --- |
| Questionnaire YAML | `expression:` fields — `calculatedExpression`, `enableWhenExpression`, `initialExpression`, `itemConstraint`, `variable` | [fhir-emr-questionnaire](../fhir-emr-questionnaire/SKILL.md) |
| Extraction Mapping YAML (FPML) | embedded inside `{{ ... }}` / `{[ ... ]}` slots | [fhir-emr-mapping](../fhir-emr-mapping/SKILL.md) |
| Frontend TypeScript | the `src/utils/fhirpath.ts` wrapper — `compileAsFirst` / `compileAsArray` / `evaluate` | [fhir-emr-frontend](../fhir-emr-frontend/SKILL.md) |
| Backend | server-side FHIRPath helpers (`compile_as_first` / `compile_as_array`) | [aidbox-python-conventions](../aidbox-python-conventions/SKILL.md) |

This skill covers the **expression language itself** — the rules that hold no matter where the expression runs. The host-specific mechanics (which context variables exist, how the expression is wired in) live in the per-context skills above and in [REFERENCE.md](REFERENCE.md).

## FHIRPath is NOT FPML

Do not conflate the two:

- **FHIRPath** — the spec expression language: navigation, `where()`, `exists()`, operators, functions. Portable across every host above.
- **FPML** (FHIRPath Mapping Language) — the YAML templating used **only** for `$extract` Mappings: `{% if %}`, `{% for %}`, `{% assign %}`. FPML *hosts* FHIRPath inside its `{{ ... }}` / `{[ ... ]}` slots but is a separate language with its own placement rules ([fhir-emr-mapping](../fhir-emr-mapping/SKILL.md)).

When something breaks, first decide which layer it is: a bad `{% for %}` placement is FPML; a wrong `.where(...)` result is FHIRPath.

## Universal rules (apply everywhere)

1. **Collections, not scalars.** Every expression returns an array; an empty result (`{}`) is normal. Guard with `.exists()`, take singletons with `.first()` / `.single()`.
2. **Never combine optional values with `+`.** `A + B` returns `{}` if either side is empty — true for numeric addition *and* string concatenation. For numbers, sum a collection instead: `(...).where(linkId='a' or linkId='b').answer.valueQuantity.value.sum()` — `.sum()` ignores empties and returns 0 for an all-empty collection. For strings, use `&` instead — it treats an empty operand as `''` rather than propagating emptiness — guarded with `iif()` when a separator should only appear alongside the optional part: `name & iif(specialty.exists(), ' (' & specialty & ')', '')`.
3. **Use specific `value[x]` access**, not generic `.answer.value`: `.answer.valueString`, `.answer.valueCoding.code`, `.answer.valueQuantity.value`.
4. **Cast DateTime variables before comparing.** The engine serialises `%var` DateTimes as `String`; comparing without a cast throws a type mismatch. Use `... <= %CurrentTime.toDateTime()`.
5. **Pass data via `%variables`/context, not string interpolation.** Interpolating values into the expression string breaks on quotes/special chars. See [REFERENCE.md](REFERENCE.md#prefer-variables-over-string-interpolation).
6. **Root access is host-specific.** Bare resource-type roots (`Patient.name`, `Questionnaire.repeat(item)...`) work **only** on frontend/backend. In Questionnaire YAML use `%resource` / `%questionnaire`; in FPML Mapping use `%QuestionnaireResponse`. See [REFERENCE.md](REFERENCE.md#referencing-the-root-is-host-specific).

## Answer-lookup essentials

```text
%resource.repeat(item).where(linkId='field-id').answer.valueString
%resource.repeat(item).where(linkId='field-id').answer.valueCoding.code
%resource.repeat(item).where(linkId='field-id').answer.valueQuantity.value.first()
```

`repeat(item)` walks nested groups at any depth. (In FPML `{% assign %}` templates a scalar answer can also be read with the `answers('linkId')` shortcut — that is a Mapping-host convenience, documented in [fhir-emr-mapping](../fhir-emr-mapping/REFERENCE.md#6-reading-answers).)

## How it's evaluated per host

This skill is the language; how an expression is *invoked* belongs to each host's skill:

- **Frontend (TypeScript):** `src/utils/fhirpath.ts` wrapper — `compileAsFirst` / `compileAsArray` / `evaluate`, custom functions, context, R4 model → [fhir-emr-frontend](../fhir-emr-frontend/REFERENCE.md#fhirpath-in-the-frontend)
- **Backend (Python):** `compile_as_first` / `compile_as_array` helpers → [aidbox-python-conventions](../aidbox-python-conventions/SKILL.md)
- **Questionnaire YAML:** SDC-evaluated `expression:` fields → [fhir-emr-questionnaire](../fhir-emr-questionnaire/SKILL.md)
- **FPML Mapping YAML:** expressions in `{{ ... }}` / `{[ ... ]}` slots → [fhir-emr-mapping](../fhir-emr-mapping/SKILL.md)
