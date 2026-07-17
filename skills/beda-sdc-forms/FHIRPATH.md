# FHIRPath conventions

How FHIRPath is used across the `fhir-emr` library and the patterns to follow when adding form, column, or Mapping code. Companion to [SKILL.md](SKILL.md) and [REFERENCE.md](REFERENCE.md).

## Main entry points

Use the library wrapper in `src/utils/fhirpath.ts` instead of importing `fhirpath.evaluate` directly.

- `evaluate(data, expression, context?, model?, options?)` — dynamic evaluator used by forms, reference selectors, and template resolution.
- `compileAsFirst<SRC, DST>(expression, model?)` — compiles once, returns the first result as `DST | undefined`.
- `compileAsArray<SRC, DST>(expression, model?)` — compiles once, returns the full result array.
- `initFHIRPathEvaluateOptions(userInvocationTable)` — registers custom functions for later `evaluate` calls.

The wrapper merges custom invocation tables into each evaluation. Bypassing it means custom functions such as `formatDate(...)` will not be available.

## Prefer compiled helpers for reused extractors

Use `compileAsFirst` / `compileAsArray` for table columns, cards, list renderers, and other paths evaluated repeatedly:

```ts
const getPatientName = compileAsFirst<Patient, HumanName>('Patient.name.first()');
const getLineItems = compileAsArray<Bundle, InvoiceLineItem>('Bundle.entry.resource.lineItem');
```

Benefits: the expression is parsed once at module load; TypeScript call sites document source and result types; render code stays small and testable.

Use `compileAsFirst` only when the expression is intentionally scalar. Use `compileAsArray` when multiple matches are meaningful (`answerOption.valueCoding`, line items, interpretations, repeated questionnaire answers).

## Use `evaluate` for runtime expressions

Use `evaluate` when the expression comes from runtime configuration or a FHIR resource — e.g. `choiceColumn.path` display expressions, reference-filter display text, `answerExpression`, `QuestionnaireResponseFormProvider` (`evaluateFhirpath={evaluate}`), and template resolution.

Always treat `evaluate` as returning an array:

```ts
const value = evaluate(resource, expression, context)[0];
```

Check length when ambiguity matters:

```ts
const result = evaluate(slot, "Slot.start.formatDate('dddd • D MMM • h:mm A')");
return result.length === 1 ? String(result[0]) : 'Unknown';
```

## Pass context deliberately

FHIRPath expressions here often depend on context variables:

- `%Patient`, `%Author`, `%QuestionnaireResponse` in Questionnaire and Mapping resources;
- included resources passed as context for reference display paths;
- `%linkId`-style variables passed to compiled helpers, e.g. `where(linkId=%linkId)`.

When evaluating a display path for an included resource, pass both the application context and included resources if the expression may need them:

```ts
evaluate(resource, path, { ...context, ...includedResources, resource });
```

For compiled helpers that accept context, prefer parameters over string interpolation:

```ts
const getByLinkId = compileAsFirst<Questionnaire, QuestionnaireItem>(
    'Questionnaire.repeat(item).where(linkId=%linkId)',
);
const item = getByLinkId(questionnaire, { linkId });
```

This avoids quoting bugs and malformed expressions.

## Choose the FHIR model when needed

Some evaluations pass the R4 model (`fhirpath/fhir-context/r4`) explicitly. Use it when evaluating expressions that depend on FHIR-aware behavior or when compiling generic paths from external configuration (e.g. configured column FHIRPaths, embedded template expressions). For simple property traversal inside already-shaped objects, the default evaluator is usually enough.

## Questionnaire usage

FHIRPath is central to SDC form behavior.

Use `initialExpression` for read-only or hidden fields derived from launch context:

```yaml
initialExpression:
  language: text/fhirpath
  expression: "%Patient.name.first().given.first() + ' ' + %Patient.name.first().family"
```

Use form context through `QuestionnaireResponseFormProvider` rather than calling FHIRPath directly inside controls. Both editable and readonly forms pass the shared evaluator with `evaluateFhirpath={evaluate}`, which keeps custom invocation functions and behavior consistent.

When displaying answer values, prefer existing helpers such as `getDisplay`, `getArrayDisplay`, and `getValueFromAnswerValue` before adding new FHIRPath. If a choice display is configurable, use the configured `choiceColumn.path` and handle missing results with `?? ''`.

## Mapping resource patterns

Seed Mappings use two styles:

- Aidbox Mapping templates with `{% assign %}` and inline `{{ ... }}` expressions;
- `$let`, `$body`, `$if`, `$map` structures with `fhirpath("...")` calls.

Conventions:

- Pull values into named variables first, then build the transaction bundle.
- Use `.0` when exactly one value is expected from a FHIRPath array.
- Use `.exists()` before emitting optional resources or fragments.
- For edit flows, read existing target IDs from `Provenance.target.where(resourceType='...').id`.
- Prefer `QuestionnaireResponse.answers('linkId')` where available — shorter and less error-prone than repeating `QuestionnaireResponse.repeat(item).where(linkId='...').answer...`.

Template style:

```yaml
"{% assign %}":
  - patientId: "{{ %QuestionnaireResponse.answers('patientId') }}"
  - pulseRate: "{{ %QuestionnaireResponse.answers('pulse-rate') }}"

entry:
  - "{% if %pulseRate.exists() %}":
      resource:
        resourceType: Observation
        status: final
        valueQuantity:
          value: "{{ %pulseRate.value }}"
```

`$let` style — keep extraction paths together at the top:

```yaml
$let:
  patientId: $ fhirpath("QuestionnaireResponse.repeat(item).where(linkId='patientId').answer.valueString").0
  qrLastUpdated: >-
    $ fhirpath("QuestionnaireResponse.meta.lastUpdated") ||
      fhirpath("QuestionnaireResponse.repeat(item).where(linkId='dateTime').answer.valueDateTime").0
```

## Nullability and empty results

FHIRPath returns arrays; empty arrays are normal.

- `compileAsFirst` and `evaluate(...)[0]` return `undefined` when no value exists.
- Don't assume required data unless the Questionnaire or resource profile guarantees it.
- Use fallbacks for display strings and dates.
- For values used in writes, validate or guard with `$if`, `.exists()`, or schema-level form validation.

## Avoid fragile string interpolation

Expressions built with template strings break when values contain quotes or special characters. Prefer context variables:

```ts
// Acceptable — value passed as a %variable
compileAsFirst<Questionnaire, QuestionnaireItem>('Questionnaire.repeat(item).where(linkId=%linkId)');

// Riskier — interpolated into the expression string
compileAsFirst<QuestionnaireResponse, string>(`repeat(item).where(linkId='${linkId}').answer.valueString`);
```

If interpolation is unavoidable, keep the interpolated value internal and constrained (e.g. known `linkId` values from Questionnaire definitions).

## Custom functions

Register custom FHIRPath functions through `initFHIRPathEvaluateOptions`, during initialization, before any form or reference loader evaluates expressions:

```ts
initFHIRPathEvaluateOptions({
    formatDate: {
        fn: (inputs: string[], format: string) =>
            inputs.map((input) => parseFHIRDateTime(input).format(format)),
        arity: { 0: [], 1: ['String'] },
    },
});
```

Keep functions pure and deterministic; return arrays compatible with FHIRPath expectations. Add tests for both the missing-function failure (before registration) and successful evaluation (after).

## Quick checklist

- Use the `src/utils/fhirpath.ts` wrapper, not direct `fhirpath.evaluate`.
- Compile static, repeated expressions; use `evaluate` for runtime expressions from resources or configuration.
- Pass context explicitly; prefer `%variables` over string interpolation.
- Pick `compileAsFirst` only for scalar paths; otherwise `compileAsArray`.
- Handle empty results.
- Use the R4 model when FHIR-aware behavior or external generic configuration needs it.
- Keep Mapping extraction variables at the top and guard optional bundle entries.
