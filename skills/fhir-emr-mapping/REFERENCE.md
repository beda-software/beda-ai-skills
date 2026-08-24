# FPML mapping rules — reference

Deep detail behind [SKILL.md](SKILL.md). Use this document when editing `resources/**/Mapping/**/*.yaml`.

## Quick Navigation (Mapping)

- **Start here:** Golden rule (section below).
- **If target field is an array/list:** read **1) Arrays (lists)**.
- **If target field is scalar/single object:** read **2) Non-array fields**.
- **If you need reusable per-row values:** read **3) `{% assign %}` inside loops**.
- **If expression already returns Coding:** read **4) Coding assignment**.
- **If linking resources in same Bundle:** read **5) In-bundle references**.
- **If reading answers from the QuestionnaireResponse:** read **6) Reading answers**.
- **If one object needs several independent `{% if %}` fragments:** read **7) Multiple conditionals in one object**.
- **If you're about to wrap something in `{% if %}` just to stop it rendering as null/empty:** read **8) Don't guard what the engine already prunes**.
- **If you're checking `.trim() != ''` or similar blank-string checks:** read **9) Trimming and blank strings**.
- **If you're about to `{% assign %}` a value used only once:** read **10) `{% assign %}` earns its place by reuse or by readability — not by habit**.

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

**Pitfall: `fullUrl` is bare, `reference` is not.** The entry that *creates* the resource sets a bare, untemplated `fullUrl`:

```yaml
- fullUrl: urn:uuid:Encounter-0
  request: { method: POST, url: /Encounter }
  resource: { resourceType: Encounter, ... }
```

Any *other* entry that points at it must wrap the identical string in `{{ '...' }}`:

```yaml
  subject:
    reference: "{{ 'urn:uuid:Encounter-0' }}"   # correct — {{ }}-wrapped
  # reference: "urn:uuid:Encounter-0"           # WRONG — Aidbox rejects this at Bundle-validation
  #                                               time with "Referenced resource urn:uuid:... does
  #                                               not exist"
```

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

## 7) Multiple conditionals in one object

The golden rule forbids multiple `{% if %}` sibling keys in one object. But an object with real fields sometimes also needs **several independent optional fragments**. Put them under a single `{% merge %}` key whose value is a **list** of `{% if %}` blocks; each block produces a partial object and all of them are merged into the parent object next to its real fields.

### GOOD

```yaml
resource:
  resourceType: Observation
  status: final
  code:
    coding:
      - system: http://loinc.org
        code: "8310-5"
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

### BAD (multiple `{% if %}` as sibling keys — violates the golden rule)

```yaml
resource:
  resourceType: Observation
  status: final
  "{% if %tempSeverity.exists() %}":
    note:
      - text: "Derived severity: {{ %tempSeverity }}"
  "{% if %methodCoding.exists() %}":
    method:
      coding:
        - "{{ %methodCoding }}"
```

A single conditional key wrapping one scalar/object value (section 2) is fine on its own — reach for `{% merge %}` only when **two or more** conditional fragments must coexist in the same object.

## 8) Don't guard what the engine already prunes

FPML drops `null` values and empty objects/arrays from the rendered output automatically. A `{% if %}` whose only job is to stop a field from rendering as null/empty is redundant — the engine already does that.

Only add a guard when one of these is actually true:

- A **sibling field is a hardcoded non-null literal** that would keep the object non-empty even when the guarded field is absent (e.g. `unit: d` / `system: ...` / `code: d` next to an optional `value` — without a guard you'd get a `Duration` with a unit but no value).
- A **business rule treats a present-but-not-really-there value as absent** — e.g. `0` or a sentinel column value. `.exists()` is `true` for `0`; null-pruning won't remove it either, since it isn't empty. This needs real logic, not engine pruning.
- The function being called has **no documented empty-in/empty-out guarantee** (a custom/engine-specific function, e.g. a custom date formatter) — guard those. Standard FHIRPath functions (`.toInteger()`, `.toDecimal()`, `.join()`, etc.) are spec-guaranteed to return empty on empty input, so wrapping them "just in case" is unnecessary — verify a function's guarantee before assuming you need a guard for it, don't add one preemptively.

### GOOD

```yaml
numberOfRepeatsAllowed: "{{ %renewals.toInteger() }}"
```

```yaml
# each child guards itself for a real reason; no need to also guard the parent —
# if every child ends up absent, dispenseRequest itself is pruned automatically
dispenseRequest:
  expectedSupplyDuration:
    "{% if %daysSupply.exists() and %daysSupply.toInteger() != 0 %}":
      value: "{{ %daysSupply.toDecimal() }}"
      unit: d
      system: http://unitsofmeasure.org
      code: d
  quantity:
    "{% if %quantityValue.exists() and %quantityValue.toDecimal() != 0 %}":
      value: "{{ %quantityValue.toDecimal() }}"
      unit: "{{ %quantityUnits.toString() }}"
```

### BAD

```yaml
numberOfRepeatsAllowed:
  "{% if %renewals.exists() %}": "{{ %renewals.toInteger() }}"
```

```yaml
# redundant outer guard — purely re-deriving what the already-guarded children imply
dispenseRequest:
  "{% if %hasDuration or %hasQuantity %}":
    expectedSupplyDuration:
      "{% if %hasDuration %}":
        value: "{{ %daysSupply.toDecimal() }}"
        unit: d
        system: http://unitsofmeasure.org
        code: d
    quantity:
      "{% if %hasQuantity %}":
        value: "{{ %quantityValue.toDecimal() }}"
```

## 9) Trimming and blank strings

Don't guard existence with `.trim() != ''`. Source data should not arrive as whitespace-only strings; use `.exists()` to check presence.

When joining optional parts (e.g. an optional first/last name) into one display string, prefer union `|` + `.join(separator)` over `&` concatenation. Union drops an absent part entirely instead of turning it into `''`, so you never get a stray leading/trailing separator to clean up with `.trim()` afterward, and the whole expression naturally evaluates to empty (and gets pruned, see section 8) when every part is absent.

### GOOD

```yaml
display: "{{ (%fname | %lname).join(' ') }}"
```

### BAD

```yaml
display: "{{ iif(%fname.trim() != '' or %lname.trim() != '', (%fname & ' ' & %lname).trim(), {}) }}"
```

## 10) `{% assign %}` earns its place by reuse or by readability — not by habit

The default reason to `{% assign %}` a value is that it's referenced **two or more times** — that's reuse, and it's always justified. A value used only **once** can still be worth assigning, but only when naming it genuinely clarifies the body — e.g. a long or non-obvious expression that reads better as `%hasActivePrescription` than inlined at its one call site. If the expression is already short and self-explanatory, assigning it just adds a layer of indirection without adding anything — inline it instead.

### GOOD (reuse — always justified)

```yaml
"{% assign %}":
  - fullName: "{{ (%fname | %lname).join(' ') }}"
subject:
  display: "{{ %fullName }}"
note:
  - text: "Prescribed for {{ %fullName }}"
```

### GOOD (single use, but the name earns its keep)

```yaml
"{% assign %}":
  - hasActivePrescription: "{{ %rxStatus != 'VOIDED' and %achiveStatus.toString() != '1' }}"
status: "{{ iif(%hasActivePrescription, 'active', 'inactive') }}"
```

### BAD (single use, expression is already trivial — indirection with no payoff)

```yaml
"{% assign %}":
  - isVoided: "{{ %rxStatus = 'VOIDED' }}"
status: "{{ iif(%isVoided, 'cancelled', 'active') }}"
```

Inline instead:

```yaml
status: "{{ iif(%rxStatus = 'VOIDED', 'cancelled', 'active') }}"
```
