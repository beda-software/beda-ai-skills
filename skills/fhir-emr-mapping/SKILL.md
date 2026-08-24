---
name: fhir-emr-mapping
description: Author and debug FPML extraction Mappings in Beda EMR — the golden rule for {% if %}/{% for %} placement, array vs scalar fields, {% assign %} loops, {% merge %} for multiple conditionals in one object, coding assignment, and in-bundle URN references. Use when creating or editing resources/**/Mapping/**/*.yaml, debugging $extract output, or writing FHIRPath in mapping templates.
---

# FHIR EMR Mapping (FPML)

Full guide: [REFERENCE.md](REFERENCE.md)
Applies to any `resources/**/Mapping/**/*.yaml`.

## Golden rule

Never put `{% if %}` or `{% for %}` as **sibling keys** next to real fields in an object.

Conditionals/loops are allowed only as:
- **array element keys**, or
- the **single key** inside a non-array field value.

## Quick Do/Don't

1. **Don't:** Put FPML `{% if %}` / `{% for %}` as sibling keys next to real fields in an object.
2. **Do:** In FPML arrays, place conditionals/loops as array element keys.
3. **Do:** For same-Bundle references, use URN templates (`urn:uuid:...`), not plain `"Encounter/..."` references. The creating entry's `fullUrl` is bare (`urn:uuid:Encounter-0`), but every `reference:` field pointing at it must be `{{ }}`-wrapped (`"{{ 'urn:uuid:Encounter-0' }}"`) — a bare `reference:` string fails Aidbox's Bundle-transaction resolution with "Referenced resource ... does not exist". See [REFERENCE.md](REFERENCE.md#5-in-bundle-references).
4. **Do:** Read a scalar answer with the `%QuestionnaireResponse.answers('linkId')` shortcut. Use `%QuestionnaireResponse.repeat(item).where(linkId='...')` when you need the item node itself (repeating group rows), not the shortcut. See [REFERENCE.md](REFERENCE.md#6-reading-answers).
5. **Do:** Reference the source **only** as `%QuestionnaireResponse` — the `%resource` alias (used in Questionnaires) and bare resource-type roots (used on the frontend/backend) do not apply in FPML.
6. **Don't:** Read launch-context variables (`%Patient`, `%Author`, `%Encounter`, …) inside a Mapping. If extraction needs launch-context data, capture it as **hidden items** in the Questionnaire (populated via `initialExpression`) and read those answers from `%QuestionnaireResponse`. See [REFERENCE.md](REFERENCE.md#6-reading-answers).
7. **Do:** When one object needs **several independent `{% if %}` fragments**, wrap them in a single `{% merge %}` list (each element is an `{% if %}` producing a partial object). This is the sanctioned way around the golden rule's "no multiple sibling conditionals". See [REFERENCE.md](REFERENCE.md#7-multiple-conditionals-in-one-object).
8. **Don't:** Add `{% if %}` purely to stop a field/object from rendering as null/empty — FPML already prunes nulls and empty objects/arrays. Only guard for a real reason (a hardcoded non-null sibling literal, a present-but-not-really-there sentinel like `0`, or a function without documented empty-in/empty-out behavior). See [REFERENCE.md](REFERENCE.md#8-dont-guard-what-the-engine-already-prunes).
9. **Don't:** Check `.trim() != ''` as an existence guard. Use `.exists()`. For joining optional parts into a display string, prefer union `|` + `.join(separator)` over `&`-concat-then-`.trim()`. See [REFERENCE.md](REFERENCE.md#9-trimming-and-blank-strings).
10. **Do:** Reach for `{% assign %}` when a value is reused two or more times, or when a single-use expression is complex enough that naming it clarifies the body. **Don't** assign a value used once when the expression is already short/self-explanatory — inline it. See [REFERENCE.md](REFERENCE.md#10-assign--earns-its-place-by-reuse-or-by-readability--not-by-habit).

## Quick decision table

| Target field type | Where to put `{% if %}` / `{% for %}` |
| --- | --- |
| Array (list) | As an array element key: `- "{% for item in %items %}":` |
| Scalar / single object | As the key wrapping the value: `start: "{% if %x.exists() %}": "{{ %x }}"` |
| Several conditionals in one object | Under one `{% merge %}` key holding a list of `{% if %}` blocks (see Patterns / [REFERENCE.md](REFERENCE.md#7-multiple-conditionals-in-one-object)) |

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

**Multiple conditionals in one object (`{% merge %}`):**
```yaml
resource:
  resourceType: Observation
  status: final
  valueQuantity:
    value: "{{ %bodyTemperature }}"
  "{% merge %}":
    - "{% if %tempSeverity.exists() %}":
        note:
          - text: "Derived severity: {{ %tempSeverity }}"
    - "{% if %methodCoding.exists() %}":
        method:
          coding:
            - "{{ %methodCoding }}"
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

**No guard needed — engine prunes nulls/empty objects, and spec functions propagate empty:**
```yaml
numberOfRepeatsAllowed: "{{ %renewals.toInteger() }}"
display: "{{ (%fname | %lname).join(' ') }}"
```

## Related skills

- Questionnaire that feeds the mapping: [fhir-emr-questionnaire](../fhir-emr-questionnaire/SKILL.md)
- FHIRPath expressions embedded in templates (not FPML itself): [fhirpath](../fhirpath/SKILL.md)
- Org-scoped extraction authorization: [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md)
