# FPML mapping rules — reference

Deep detail behind [SKILL.md](SKILL.md). Use this document when editing `resources/**/Mapping/*.yaml`.

## Quick Navigation (Mapping)

- **Start here:** Golden rule (section below).
- **If target field is an array/list:** read **1) Arrays (lists)**.
- **If target field is scalar/single object:** read **2) Non-array fields**.
- **If you need reusable per-row values:** read **3) `{% assign %}` inside loops**.
- **If expression already returns Coding:** read **4) Coding assignment**.
- **If linking resources in same Bundle:** read **5) In-bundle references**.
- **If reading answers from the QuestionnaireResponse:** read **6) Reading answers**.

## Golden rule

Never put `{% if %}` or `{% for %}` as sibling keys next to real fields in an object.

Conditionals/loops are allowed only as:
- array element keys, or
- the single key inside a non-array field value.

Reference:
- [FPML style guide](https://github.com/beda-software/FHIRPathMappingLanguage/issues/35)

## 1) Arrays (lists)

### GOOD

```yaml
statusReason:
  - "{% for item in %items %}":
      coding:
        - "{{ %item }}"
```

```yaml
extension:
  - "{% if %condition %}":
      url: ...
```

### BAD

```yaml
period:
  "{% if %start.exists() %}":
    start: "{{ %start }}"
  "{% if %end.exists() %}":
    end: "{{ %end }}"
```

```yaml
statusReason:
  "{% if %condition %}":
    - ...
```

## 2) Non-array fields (scalar/single object)

### GOOD

```yaml
period:
  start:
    "{% if %encounterPeriodStart.exists() %}": "{{ %encounterPeriodStart }}"
  end:
    "{% if %encounterPeriodEnd.exists() %}": "{{ %encounterPeriodEnd }}"
```

### BAD

```yaml
period:
  "{% if %encounterPeriodStart.exists() %}":
    start: "{{ %encounterPeriodStart }}"
  "{% if %encounterPeriodEnd.exists() %}":
    end: "{{ %encounterPeriodEnd }}"
```

## 3) `{% assign %}` inside loops

Use `{% assign %}` inside `{% for ... %}` to avoid repeating long paths.

```yaml
entry:
  - "{% for row in %rows %}":
      "{% assign %}":
        - rowId: "{{ %row.item.where(linkId='row-id').answer.valueString }}"
        - rowCoding: "{{ %row.item.where(linkId='row-coding').answer.valueCoding }}"
      request:
        "{% if %rowId.exists() %}":
          method: PUT
          url: "/SomeResource/{{ %rowId }}"
        "{% else %}":
          method: POST
          url: /SomeResource
      resource:
        coding:
          - "{{ %rowCoding }}"
```

## 4) Coding assignment

If expression returns full `Coding`, assign directly:

```yaml
coding:
  - "{{ %someCoding }}"
```

## 5) In-bundle references

When referencing resources created in the same transaction Bundle, use URN template:

```yaml
reference: "{{ 'urn:uuid:Encounter-0' }}"
```

Do not use plain external-style references (`"Encounter/..."`) for in-bundle links.

## 6) Reading answers

Read a **scalar** answer with the `answers('linkId')` shortcut inside a `{% assign %}` block:

```yaml
"{% assign %}":
  - patientId: "{{ %QuestionnaireResponse.answers('patientId') }}"
  - pulseRate: "{{ %QuestionnaireResponse.answers('pulse-rate') }}"
```

It is shorter and less error-prone than repeating `%QuestionnaireResponse.repeat(item).where(linkId='...').answer.value...`. But it returns the **answer value**, so use it only for scalars. When you need the **item node itself** — repeating group rows you loop over — use `repeat(item).where(...)`, not `answers()`:

```yaml
  - contactRows: "{[ %QuestionnaireResponse.repeat(item).where(linkId='contacts') ]}"
  - conditionRows: "{[ %QuestionnaireResponse.repeat(item).where(linkId='conditions') ]}"
```

Always reference the source as `%QuestionnaireResponse`. The `%resource` alias used in Questionnaire expressions and the bare resource-type root (`QuestionnaireResponse.…`) used on the frontend/backend do **not** apply in FPML.

### Do not read launch context in a Mapping

A Mapping should read **only** from `%QuestionnaireResponse`. Do **not** reach for launch-context variables (`%Patient`, `%Author`, `%Encounter`, …) inside extraction templates — it couples the Mapping to how the form was launched and breaks when the same QR is re-extracted in a different context.

If extraction needs a value that comes from launch context (e.g. the patient id, the author, the encounter), expose it in the form first: add a **hidden item** to the Questionnaire whose `initialExpression` reads the launch-context variable, so the value lands in the QuestionnaireResponse. The Mapping then reads it as an ordinary answer:

```yaml
# Questionnaire (see fhir-emr-questionnaire): hidden item populated from launch context
- linkId: patientId
  type: string
  hidden: true
  initialExpression:
    language: text/fhirpath
    expression: "%Patient.id"
```

```yaml
# Mapping: read it as a normal answer, never %Patient
"{% assign %}":
  - patientId: "{{ %QuestionnaireResponse.answers('patientId') }}"
```

See [fhir-emr-questionnaire](../fhir-emr-questionnaire/SKILL.md) for hidden-field authoring.
