---
name: fhir-emr-questionnaire
description: Author and debug FHIR Questionnaire YAML in Beda EMR — FCE extensions (calculatedExpression, enableWhenExpression, initialExpression, itemConstraint, variables), FHIRPath answer lookup, scoring patterns, and group-table summation. Use when creating or editing resources/**/Questionnaire/**/*.yaml, debugging form visibility or calculated fields, or writing FHIRPath for SDC questionnaires.
---

# FHIR EMR Questionnaire authoring

Full guide: [REFERENCE.md](REFERENCE.md)
Applies to any `resources/**/Questionnaire/**/*.yaml`.

## Before you start

1. Read an existing questionnaire under `resources/**/Questionnaire/**/*.yaml` for reference.
2. Use profile `https://emr-core.beda.software/StructureDefinition/fhir-emr-questionnaire`.
3. Keep item field order: `linkId` → `text` → `type`, then other keys.

## Quick Do/Don't

1. **Do:** Use `linkId → text → type` order in Questionnaire items.
2. **Do:** Use `%resource.repeat(item).where(linkId='...')` for answer lookup.
3. **Do:** Use specific answer types (`valueString`, `valueCoding`, etc.), not generic `.answer.value`.
4. **Do:** Use `.first()` / `.single()` when a singleton value is required.
5. **Do:** Keep `initialExpression` for backend prefill and `calculatedExpression` for frontend recalculation.
6. **Do:** Prefer `%resource` (QuestionnaireResponse) and `%questionnaire` (Questionnaire); the `%QuestionnaireResponse` / `%Questionnaire` names are also supported but the lowercase ones are preferred.
7. **Don't:** Assume `_text.cqfExpression` behaves the same across all renderers.
8. **Do:** Read each answer once into a `variable` on the closest group that contains every item using it, and build
   derived values from other variables.
9. **Don't:** Use `enableWhenExpression`; gate the item with a plain `enableWhen` on a hidden calculated item instead.
10. **Do:** Place a hidden calculated item used only by an `enableWhen` right before the item it gates, as its
    sibling, not at the root.

## Core extensions

| Extension | Evaluated on | Context |
| --- | --- | --- |
| `calculatedExpression` | Frontend | `%resource`, `%questionnaire`, `%qitem`, `%context` |
| `enableWhenExpression` | Frontend | same — avoid, see [Visibility](#visibility-calculated-item--enablewhen) |
| `variable` | Frontend | same |
| `initialExpression` | Backend | `%resource` / `%questionnaire` (newer) or `%QuestionnaireResponse` / `%Questionnaire` (legacy) |
| `itemConstraint` | Backend | same |
| `_text.cqfExpression` | Frontend (renderer-dependent) | same as frontend |

**Context variable naming.** Prefer `%resource` (the QuestionnaireResponse) and `%questionnaire` (the Questionnaire) everywhere:

- **Frontend:** `%resource` / `%questionnaire` are preferred; `%QuestionnaireResponse` / `%Questionnaire` are also supported (same as on the backend).
- **Backend:** `%QuestionnaireResponse` / `%Questionnaire` are the original names; newer server versions also support `%resource` / `%questionnaire`, which are preferred going forward.

Questionnaire-defined `%VarName` variables work in both frontend- and backend-evaluated expressions.

## Variables: compute each value once

Declare a `variable` on the closest group that contains every item using it (the root only when the whole form needs
it), read each answer once, and derive further values from other variables:
[REFERENCE.md § Variables](REFERENCE.md#variables-compute-each-value-once).

## Visibility: calculated item + enableWhen

Don't use `enableWhenExpression`. Put the condition, or the value it depends on, in a hidden calculated item and gate
the item with a plain `enableWhen` — the shape
[sdc-qrf#48](https://github.com/beda-software/sdc-qrf/pull/48) proposes rewriting `enableWhenExpression` into. A
calculated item that exists only for that `enableWhen` goes right before the gated item, as its sibling, also inside
`group-voice` and `wizard` groups; it moves up to the closest common parent only when items in several places share it.
Worked example:
[REFERENCE.md § Visibility](REFERENCE.md#visibility-hidden-calculated-item--enablewhen).

## FHIRPath essentials

```text
%resource.repeat(item).where(linkId='field-id').answer.valueString
%resource.repeat(item).where(linkId='field-id').answer.valueCoding.code
%resource.repeat(item).where(linkId='field-id').answer.valueQuantity.value.first()
```

- Use specific answer types, not generic `.answer.value`.
- Use `.first()` / `.single()` for singleton values.
- For summation across optional fields, use `.where(linkId=... or ...).answer.valueQuantity.value.sum()` — never `A + B` (empty operands break the result).
- To add two optional variables, use `%A.combine(%B).sum()`, not `%A | %B`: `|` drops duplicates, so 2 and 2
  collapse into one value. Guard with `iif(%A.exists() or %B.exists(), …, {})`, because `sum()` of empty is `0`.
- `.first()` before `exists()` / `empty()` is redundant; drop it.
- When comparing DateTime variables, cast with `.toDateTime()`.

## Common patterns

**Repeat row default:**
```text
iif(%context.answer.exists(), %context.answer.valueDateTime, now())
```

**Weighted score from itemWeight:**
```text
%resource.repeat(item).where(linkId in ('q1' | 'q2'))
  .answer.valueCoding.extension
  .where(url='http://hl7.org/fhir/StructureDefinition/itemWeight')
  .valueDecimal.sum()
```

**Expose launch context for extraction (hidden field):** a Mapping reads only `%QuestionnaireResponse`, never launch-context variables. When extraction needs launch-context data, capture it in a hidden item so it lands in the QuestionnaireResponse:

```yaml
- linkId: patientId
  type: string
  hidden: true
  initialExpression:
    language: text/fhirpath
    expression: "%Patient.id"
```

The Mapping then reads `%QuestionnaireResponse.answers('patientId')`. See [fhir-emr-mapping](../fhir-emr-mapping/SKILL.md).

## Compatibility notes

- Calculated `choice/Coding` values may be renderer-specific; prefer readOnly `string` + `calculatedExpression` for portability.
- `_text.cqfExpression` support varies; prefer readOnly `text/string` + `calculatedExpression` when possible.

## Related skills

- FHIRPath expression language (used in all expression fields): [fhirpath](../fhirpath/SKILL.md)
- Extraction from questionnaire responses: [fhir-emr-mapping](../fhir-emr-mapping/SKILL.md)
- Org-scoped form operations: [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md)
