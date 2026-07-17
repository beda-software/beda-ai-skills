---
name: fhir-emr-mapping
description: Author and debug FPML extraction Mappings in Beda EMR — the golden rule for {% if %}/{% for %} placement, array vs scalar fields, {% assign %} loops, coding assignment, and in-bundle URN references. Use when creating or editing resources/**/Mapping/*.yaml, debugging $extract output, or writing FHIRPath in mapping templates.
---

# FHIR EMR Mapping (FPML)

Full guide: [REFERENCE.md](REFERENCE.md)
Baseline example: `resources/init-seeds/Mapping/mapping-baseline.yaml`

## Golden rule

Never put `{% if %}` or `{% for %}` as **sibling keys** next to real fields in an object.

Conditionals/loops are allowed only as:
- **array element keys**, or
- the **single key** inside a non-array field value.

## Quick Do/Don't

1. **Don't:** Put FPML `{% if %}` / `{% for %}` as sibling keys next to real fields in an object.
2. **Do:** In FPML arrays, place conditionals/loops as array element keys.
3. **Do:** For same-Bundle references, use URN templates (`urn:uuid:...`), not plain `"Encounter/..."` references.
4. **Do:** Read a scalar answer with the `%QuestionnaireResponse.answers('linkId')` shortcut. Use `%QuestionnaireResponse.repeat(item).where(linkId='...')` when you need the item node itself (repeating group rows), not the shortcut. See [REFERENCE.md](REFERENCE.md#6-reading-answers).
5. **Do:** Reference the source **only** as `%QuestionnaireResponse` — the `%resource` alias (used in Questionnaires) and bare resource-type roots (used on the frontend/backend) do not apply in FPML.
6. **Don't:** Read launch-context variables (`%Patient`, `%Author`, `%Encounter`, …) inside a Mapping. If extraction needs launch-context data, capture it as **hidden items** in the Questionnaire (populated via `initialExpression`) and read those answers from `%QuestionnaireResponse`. See [REFERENCE.md](REFERENCE.md#6-reading-answers).

## Quick decision table

| Target field type | Where to put `{% if %}` / `{% for %}` |
| --- | --- |
| Array (list) | As an array element key: `- "{% for item in %items %}":` |
| Scalar / single object | As the key wrapping the value: `start: "{% if %x.exists() %}": "{{ %x }}"` |

## Patterns

**Array loop:**
```yaml
statusReason:
  - "{% for item in %items %}":
      coding:
        - "{{ %item }}"
```

**Scalar with conditional:**
```yaml
period:
  start:
    "{% if %start.exists() %}": "{{ %start }}"
```

**Reusable per-row values:**
```yaml
entry:
  - "{% for row in %rows %}":
      "{% assign %}":
        - rowId: "{{ %row.item.where(linkId='id').answer.valueString }}"
      resource:
        id: "{{ %rowId }}"
```

**Coding assignment** (expression returns full Coding):
```yaml
coding:
  - "{{ %someCoding }}"
```

**In-bundle reference** (same transaction Bundle):
```yaml
reference: "{{ 'urn:uuid:Encounter-0' }}"
```

## Related skills

- Questionnaire that feeds the mapping: [fhir-emr-questionnaire](../fhir-emr-questionnaire/SKILL.md)
- FHIRPath expressions embedded in templates (not FPML itself): [fhirpath](../fhirpath/SKILL.md)
- Org-scoped extraction authorization: [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md)
