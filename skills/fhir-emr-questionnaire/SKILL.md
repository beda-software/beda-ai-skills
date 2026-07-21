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

## Core extensions

| Extension | Evaluated on | Context |
| --- | --- | --- |
| `calculatedExpression` | Frontend | `%resource`, `%questionnaire`, `%qitem`, `%context` |
| `enableWhenExpression` | Frontend | same |
| `variable` | Frontend | same |
| `initialExpression` | Backend | `%resource` / `%questionnaire` (newer) or `%QuestionnaireResponse` / `%Questionnaire` (legacy) |
| `itemConstraint` | Backend | same |
| `_text.cqfExpression` | Frontend (renderer-dependent) | same as frontend |

**Context variable naming.** Prefer `%resource` (the QuestionnaireResponse) and `%questionnaire` (the Questionnaire) everywhere:

- **Frontend:** `%resource` / `%questionnaire` are preferred; `%QuestionnaireResponse` / `%Questionnaire` are also supported (same as on the backend).
- **Backend:** `%QuestionnaireResponse` / `%Questionnaire` are the original names; newer server versions also support `%resource` / `%questionnaire`, which are preferred going forward.

Questionnaire-defined `%VarName` variables work in both frontend- and backend-evaluated expressions.

## FHIRPath essentials

```text
%resource.repeat(item).where(linkId='field-id').answer.valueString
%resource.repeat(item).where(linkId='field-id').answer.valueCoding.code
%resource.repeat(item).where(linkId='field-id').answer.valueQuantity.value.first()
```

- Use specific answer types, not generic `.answer.value`.
- Use `.first()` / `.single()` for singleton values.
- For summation across optional fields, use `.where(linkId=... or ...).answer.valueQuantity.value.sum()` — never `A + B` (empty operands break the result).
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
