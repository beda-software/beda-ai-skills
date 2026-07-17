# FHIR Questionnaire authoring — reference

Deep detail behind [SKILL.md](SKILL.md). Use this document when editing `resources/**/Questionnaire/*.yaml`.

## 1) Structure and style

- Include standard metadata: `id`, `resourceType: Questionnaire`, `name`, `title`, `status`, `subjectType`, `url`, `meta.profile`.
- Use kebab-case for `linkId` (e.g. `measurement-type`, `symptom-status`).
- Keep item field order for readability: `linkId` -> `text` -> `type`, then other keys.
- For nested forms, use `item` recursively; for repeat rows use `repeats: true`.

## 2) Core extensions/FCE you will use often

- `calculatedExpression` — computed item value (frontend-evaluated).
- `enableWhenExpression` — computed visibility (frontend-evaluated).
- `initialExpression` — initial value (backend-evaluated).
- `_text.cqfExpression` — dynamic display text (frontend-evaluated).
- `itemConstraint` — validation rule (backend-evaluated).
- `variable` — reusable FHIRPath variables at group/root level.

Reference for full extension map:
- [sdc-qrf extensions.ts](https://github.com/beda-software/sdc-qrf/blob/main/src/converter/extensions.ts)

## 3) FHIRPath basics (practical rules)

- Language: `text/fhirpath`.
- Prefer `%resource.repeat(item).where(linkId='...')` for answer lookup at any depth.
- Use specific answer types only (`valueString`, `valueBoolean`, `valueCoding`, etc.), not generic `.answer.value`.
- Ensure singleton where required using `.first()`/`.single()`.

Examples:

```text
%resource.repeat(item).where(linkId='measurement-type').answer.valueCoding.code
%resource.repeat(item).where(linkId='has-symptoms').answer.valueString = 'yes'
%resource.repeat(item).where(linkId='diagnosis-list').answer.valueCoding.where(code='moderate-risk').exists()
%resource.repeat(item).where(linkId='admission-weight').answer.valueQuantity.value.first()
```

## 4) Context model

### Frontend-evaluated expressions

For `calculatedExpression`, `enableWhenExpression`, `variable`:
- `%resource` = current QuestionnaireResponse
- `%questionnaire` = Questionnaire definition
- `%qitem` = current Questionnaire item
- `%context` = current repeat row context

### Backend-evaluated expressions

For `initialExpression`, `itemConstraint`:
- Use `%Questionnaire` and `%QuestionnaireResponse`
- Do not rely on `%questionnaire` (lowercase)
- Do not rely on Questionnaire-defined `%VarName` variables

## 5) Compatibility notes (important)

- Calculated `choice/Coding` values may be renderer-specific; for cross-renderer portability, prefer readOnly `string` + `calculatedExpression` where acceptable.
- `_text.cqfExpression` support can vary by renderer; for portability, prefer readOnly `text/string` + `calculatedExpression`.

## 6) Common patterns

### Repeat row default (new row)

```text
iif(%context.answer.exists(), %context.answer.valueDateTime, now())
```

### Item option selected by another answer

```text
%qitem.answerOption.valueCoding.where(
  code = %resource.repeat(item).where(linkId='measurement-type').answer.valueCoding.code.first()
).first()
```

### Weighted score from selected options (`itemWeight`)

```text
%resource.repeat(item)
  .where(linkId in ('risk-factors' | 'warning-signs' | ...))
  .answer.valueCoding.extension
  .where(url='http://hl7.org/fhir/StructureDefinition/itemWeight')
  .valueDecimal
  .sum()
```

## 7) Summation patterns in repeating group-table

### Sum across all rows (grand total)

Collect all matching child items from all repeat instances and sum their values.
Works correctly even when only some fields are filled per row — empty fields produce
no entries in the collection, so `.sum()` naturally ignores them.

```text
# Defined as variable on a non-repeating summary group
- name: TotalIntake
  language: text/fhirpath
  expression: >-
    %resource.repeat(item)
      .where(linkId='fluid-intake-iv1' or linkId='fluid-intake-iv2' or linkId='fluid-intake-oral-ng')
      .answer.valueQuantity.value.sum()
```

Use `type: decimal` (not `quantity`) for the calculated field — `calculatedExpression`
returns a scalar number, not a Quantity object:

```yaml
- linkId: fluid-balance-intake-total
  text: Total Intake (mL)
  type: decimal
  readOnly: true
  calculatedExpression:
    language: text/fhirpath
    expression: "%TotalIntake"
```

### Running cumulative (prog. total per row, up to current time)

Defined as a `variable` at the **repeating** group level. Filters rows by time, then
sums child items with `or` across linkIds.

```text
# Step 1 — capture this row's time
- name: CurrentIntakeTime
  expression: "%context.item.where(linkId='fluid-intake-time').answer.valueDateTime.first()"

# Step 2 — sum all rows where time <= CurrentIntakeTime
- name: IntakeCumulative
  expression: >-
    %resource.repeat(item).where(linkId='fluid-balance-intake-table-group')
      .where(item.where(linkId='fluid-intake-time').answer.valueDateTime.first()
             <= %CurrentIntakeTime.toDateTime())
      .item.where(linkId='fluid-intake-iv1' or linkId='fluid-intake-iv2' or linkId='fluid-intake-oral-ng')
      .answer.valueQuantity.value.sum()
```

**Key rules:**
- **Never use `+` to add optional fields.** In FHIRPath `A + B` returns `{}` if either
  operand is empty. Use `.where(linkId=... or ...).answer.valueQuantity.value.sum()`
  instead — `.sum()` ignores empty fields and returns 0 for an all-empty collection.
- Always cast the variable to `.toDateTime()` on the right-hand side of `<=`; the
  FHIRPath engine serialises `DateTime` variables as `String`, causing a type-mismatch
  error otherwise: `... <= %CurrentIntakeTime.toDateTime()`.
- Use a guard variable (`AnyIntake`) + `iif(%AnyIntake, %IntakeCumulative, {})` on the
  calculated field so that a completely empty row shows blank instead of `0`.
- Partially filled rows (only some columns entered) are handled automatically — empty
  fields produce no collection entries and are effectively treated as `0` by `.sum()`.

```text
# Guard — true when at least one volume field is filled in this row
- name: AnyIntake
  expression: >-
    %context.item.where(linkId='fluid-intake-iv1').answer.valueQuantity.value.exists() or
    %context.item.where(linkId='fluid-intake-iv2').answer.valueQuantity.value.exists() or
    %context.item.where(linkId='fluid-intake-oral-ng').answer.valueQuantity.value.exists()
```

### DateTime comparison in variables — mandatory `.toDateTime()` cast

When a `variable` holds a DateTime value and is used in a comparison (`<=`, `>=`),
the variable must be cast explicitly:

```text
# Wrong — throws: Type of "..." (FP_DateTime) did not match type of "..." (String)
item.where(...).answer.valueDateTime.first() <= %CurrentIntakeTime

# Correct
item.where(...).answer.valueDateTime.first() <= %CurrentIntakeTime.toDateTime()
```

This pattern is also used in production questionnaires with repeating group-tables and time-based cumulative totals.

## 8) References

- Profile: `https://emr-core.beda.software/StructureDefinition/fhir-emr-questionnaire`
- FHIRPath spec: [HL7 FHIRPath](https://build.fhir.org/ig/HL7/FHIRPath/)
