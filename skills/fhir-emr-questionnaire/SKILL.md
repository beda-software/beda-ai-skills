---
name: fhir-emr-questionnaire
description: Author and debug FHIR Questionnaire YAML in Beda EMR — FCE extensions (calculatedExpression, enableWhenExpression, initialExpression, itemConstraint, variables), FHIRPath answer lookup, scoring patterns, and group-table summation. Use when creating or editing resources/**/Questionnaire/*.yaml, debugging form visibility or calculated fields, or writing FHIRPath for SDC questionnaires.
---

# FHIR EMR Questionnaire authoring

Full guide: [REFERENCE.md](REFERENCE.md)
Baseline example: `resources/init-seeds/Questionnaire/example.yaml`

## Before you start

1. Read the baseline example above.
2. Use profile `https://emr-core.beda.software/StructureDefinition/fhir-emr-questionnaire`.
3. Keep item field order: `linkId` → `text` → `type`, then other keys.

## Quick Do/Don't

1. **Do:** Use `linkId → text → type` order in Questionnaire items.
2. **Do:** Use `%resource.repeat(item).where(linkId='...')` for answer lookup.
3. **Do:** Use specific answer types (`valueString`, `valueCoding`, etc.), not generic `.answer.value`.
4. **Do:** Use `.first()` / `.single()` when a singleton value is required.
5. **Do:** Keep `initialExpression` for backend prefill and `calculatedExpression` for frontend recalculation.
6. **Don't:** Use Questionnaire variables in backend-evaluated expressions (`initialExpression`, `itemConstraint`).
7. **Don't:** Assume `_text.cqfExpression` behaves the same across all renderers.

## Core extensions

| Extension | Evaluated on | Context |
| --- | --- | --- |
| `calculatedExpression` | Frontend | `%resource`, `%questionnaire`, `%qitem`, `%context` |
| `enableWhenExpression` | Frontend | same |
| `variable` | Frontend | same |
| `initialExpression` | Backend | `%Questionnaire`, `%QuestionnaireResponse` |
| `itemConstraint` | Backend | `%Questionnaire`, `%QuestionnaireResponse` |
| `_text.cqfExpression` | Frontend (renderer-dependent) | same |

**Do not** use Questionnaire-defined `%VarName` variables in backend expressions (`initialExpression`, `itemConstraint`).

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

## Compatibility notes

- Calculated `choice/Coding` values may be renderer-specific; prefer readOnly `string` + `calculatedExpression` for portability.
- `_text.cqfExpression` support varies; prefer readOnly `text/string` + `calculatedExpression` when possible.

## Related skills

- Runtime form pipeline: [beda-sdc-forms](../beda-sdc-forms/SKILL.md)
- Extraction from questionnaire responses: [fhir-emr-mapping](../fhir-emr-mapping/SKILL.md)
- Org-scoped form operations: [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md)
