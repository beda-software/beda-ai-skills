# Verification example — fhir-emr-mapping skill

This document shows that the [fhir-emr-mapping](SKILL.md) skill rules match a real baseline file in the repo.

## Baseline file

`resources/init-seeds/Mapping/mapping-baseline.yaml`

## Rule 1: conditionals as array element keys (not sibling keys)

**Skill says:** In FPML arrays, place `{% for %}` / `{% if %}` as array element keys.

**Baseline — GOOD** (`telecom` is an array; loop is an element key):

```yaml
telecom:
  - "{% for contactRow in %contactRows %}":
      system: "{{ %contactRow.item.where(linkId='contact-type').answer.valueCoding.code }}"
      value: "{{ %contactRow.item.where(linkId='contact-value').answer.valueString }}"
```

**Baseline — GOOD** (`entry` array; condition rows use loop as element key):

```yaml
entry:
  - "{% for conditionRow in %conditionRows %}":
      ...
```

## Rule 2: conditionals on scalar fields wrap the value key

**Skill says:** For scalar/single-object fields, put `{% if %}` as the key wrapping the value.

**Baseline — GOOD** (`request` object; each branch is a single conditional key):

```yaml
request:
  "{% if %patientId.exists() %}":
    url: "/Patient/{{ %patientId }}"
    method: PATCH
  "{% else %}":
    url: /Patient
    method: POST
```

**Baseline — GOOD** (`abatementDateTime` scalar):

```yaml
abatementDateTime:
  "{% if %statusCode != 'active' and %abatementDateTime.exists() %}": "{{ %abatementDateTime }}"
```

## Rule 3: in-bundle references use URN templates

**Skill says:** Use `urn:uuid:...` for resources in the same transaction Bundle.

**Baseline — GOOD:**

```yaml
fullUrl: "{{ 'urn:uuid:patient-id' }}"
...
subject:
  uri: "{{ 'urn:uuid:patient-id' }}"
```

## Rule 4: `{% assign %}` inside loops

**Baseline — GOOD** (per-row variables in condition loop):

```yaml
- "{% for conditionRow in %conditionRows %}":
    "{% assign %}":
      - conditionCoding: "{{ %conditionRow.item.where(linkId='condition').answer.valueCoding }}"
      - conditionId: "{{ %conditionRow.item.where(linkId='condition-id').answer.valueString }}"
```

---

Every rule above is satisfied by the baseline file, showing the skill's guidance matches real mappings in the repo. For the full rule set (including `{% merge %}` and reading answers), see [REFERENCE.md](REFERENCE.md).
