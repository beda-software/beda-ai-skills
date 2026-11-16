# FHIR Questionnaire authoring — reference

Deep detail behind [SKILL.md](SKILL.md). Use this document when editing `resources/**/Questionnaire/**/*.yaml`.

## 1) Structure and style

- Include standard metadata: `id`, `resourceType: Questionnaire`, `name`, `title`, `status`, `subjectType`, `url`, `meta.profile`.
- Use kebab-case for `linkId` (e.g. `measurement-type`, `symptom-status`).
- Keep item field order for readability: `linkId` -> `text` -> `type`, then other keys.
- For nested forms, use `item` recursively; for repeat rows use `repeats: true`.

## 2) Core extensions/FCE you will use often

- `calculatedExpression` — computed item value (frontend-evaluated).
- `enableWhenExpression` — computed visibility (frontend-evaluated). Avoid it; see
  [Visibility](#visibility-hidden-calculated-item--enablewhen).
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

For `calculatedExpression`, `enableWhenExpression` (avoid it, see
[Visibility](#visibility-hidden-calculated-item--enablewhen)), `variable`:
- `%resource` = current QuestionnaireResponse (preferred)
- `%questionnaire` = Questionnaire definition (preferred)
- `%qitem` = current Questionnaire item
- `%context` = current repeat row context
- `%QuestionnaireResponse` / `%Questionnaire` are also supported (same as on the backend), but the lowercase `%resource` / `%questionnaire` are the **preferred** names.

### Backend-evaluated expressions

For `initialExpression`, `itemConstraint`:
- `%QuestionnaireResponse` and `%Questionnaire` are the original names and remain supported.
- `%resource` / `%questionnaire` are also supported on newer server versions and are the **preferred** names going forward — check your Aidbox/SDC version before relying on them.
- Questionnaire-defined `%VarName` variables are supported here too (not frontend-only).

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

### Variables: compute each value once

A `variable` is visible to every expression on the item that declares it and on all its descendants.
Declare it on the closest group that contains every item using it; put it on the Questionnaire root only when the
whole form needs it. Read each answer once, then derive further values from other variables:

```yaml
- linkId: measurements
  type: group
  variable:
    - name: AIn
      language: text/fhirpath
      expression: "%resource.repeat(item).where(linkId='a-in').answer.valueQuantity.value.first()"
    - name: ACm
      language: text/fhirpath
      expression: "%resource.repeat(item).where(linkId='a-cm').answer.valueQuantity.value.first()"
    - name: A
      language: text/fhirpath
      expression: "iif(%AIn.exists(), (%AIn * 2.54).round(1), %ACm)"
  item:
    - linkId: a-in
      ...
    - linkId: a-cm
      ...
    - linkId: a-summary
      ...
```

Every item inside `measurements` can read `%AIn`, `%ACm` and `%A`; items outside it cannot.

### Sum of optional variables

```yaml
variable:
  - name: ScoreA
    language: text/fhirpath
    expression: "%resource.repeat(item).where(linkId='score-a').answer.valueInteger.first()"
  - name: ScoreB
    language: text/fhirpath
    expression: "%resource.repeat(item).where(linkId='score-b').answer.valueInteger.first()"
  - name: Total
    language: text/fhirpath
    expression: "iif(%ScoreA.exists() or %ScoreB.exists(), %ScoreA.combine(%ScoreB).sum(), {})"
```

- `combine`, not `|`: `|` drops duplicates, so `2 | 2` is a single `2`.
- The `iif` guard keeps `%Total` empty when nothing is entered; `sum()` of empty is `0`.

### Visibility: hidden calculated item + enableWhen

Don't use `enableWhenExpression`; [sdc-qrf#48](https://github.com/beda-software/sdc-qrf/pull/48) proposes rewriting
it into this shape. Put the value in a hidden calculated item and gate the dependent item with a plain `enableWhen`:

```yaml
- linkId: total
  type: integer
  hidden: true
  calculatedExpression:
    language: text/fhirpath
    expression: "%Total"
...
- linkId: total-line
  type: display
  enableWhen:
    - question: total
      operator: exists
      answerBoolean: true
  _text:
    cqfExpression:
      language: text/fhirpath
      expression: "'Total: ' & %Total.toString()"
```

- `exists` is true when the question has at least one answer.
- For a calculated **boolean** flag use `operator: "="` with `answerBoolean: true`, never `exists`: a computed
  `false` is still an answer, so `exists` would show the item exactly when it should be hidden.
- `enableWhen` may reference a linkId at any nesting level.
- `_text` needs no `''` fallback for an empty `%Total`: `enableWhen` already hides the item then.

**Placement.** A hidden calculated item that exists only to gate an item's `enableWhen` goes immediately before that
item, as its sibling in the same group, not at the Questionnaire root. The condition then reads next to the item it
controls. Calculated items that carry a value (read by a mapping, a score, another expression) stay where that value
belongs:

```yaml
- linkId: details
  type: group
  item:
    - linkId: status
      type: choice
      ...
    - linkId: extra-enabled
      type: boolean
      hidden: true
      calculatedExpression:
        language: text/fhirpath
        expression: "%resource.repeat(item).where(linkId='status').answer.valueCoding.where(code = 'normal').exists().not()"
    - linkId: extra
      type: choice
      enableWhen:
        - question: extra-enabled
          operator: "="
          answerBoolean: true
```

- A flag shared by items in several places goes in their closest common parent.

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
