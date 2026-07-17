# fhir-emr frontend code style — reference

Deep detail behind [SKILL.md](SKILL.md). React/TypeScript conventions specific to the `fhir-emr` frontend (`src/`).

## Components

1. Each component is placed in a directory named after the component function, with the main file located in `ComponentName/index.tsx`.
2. Child components that are not used outside the `ComponentName` context should be placed inside `ComponentName`'s directory under `src/components/ComponentName/ComponentChild/index.tsx`.
3. Component structure:
   - `src/components/ComponentName/`
     - `index.tsx` — base HTML structure; calls the associated hook
     - `hooks.ts` — business logic in `useComponentName`; testable with `renderHook`
     - `types.ts` — shared types
     - `utils.ts` — reusable utilities outside the hook
4. All logic goes in **ComponentName/hooks.ts** — keep components presentational for easier testing.

## Comments and debugging artifacts

1. Remove unnecessary comments. If deleted code is needed again, retrieve it from previous commits.
2. Remove all `console.log`, `console.error`, and `console.warn` before committing.

## Conditions and guards

1. Follow the Guard Clauses pattern: return negative results first, positive results below.
2. Avoid nested ternary operators.

## Styles

1. Do not use hardcoded colors; use the Ant Design (antd) theme.
2. Prefer standard Ant Design components; use custom CSS only in edge cases.

## TypeScript

1. Avoid inline type annotations for complex types — use type aliases and interfaces.
2. Add generic types where applicable (`useService`, `useState`, etc.).

## Algorithms and complexity

1. Use a `Map` for key-based lookups instead of filtering an array repeatedly (O(1) vs O(n) per lookup).

Example — observations table by code:

```typescript
type ObservationsByCode = { code: Coding['code']; observations: Observation[] };
```

Build the map when fetching data with `useService`; render with `Object.keys(observationsByCode)`.

## Utils

1. All `utils/fhirpath` utils must have tests.

## FHIRPath in the frontend

FHIRPath expressions run through the `src/utils/fhirpath.ts` wrapper — never import `fhirpath.evaluate` directly. The wrapper merges custom invocation tables into each evaluation; bypassing it means custom functions such as `formatDate(...)` are unavailable. (The expression syntax and cross-host language rules live in the [fhirpath](../fhirpath/SKILL.md) skill; this section is the frontend invocation contract.)

- `evaluate(data, expression, context?, model?, options?)` — dynamic evaluator for forms, reference selectors, template resolution.
- `compileAsFirst<SRC, DST>(expression, model?)` — compiles once, returns the first result as `DST | undefined`.
- `compileAsArray<SRC, DST>(expression, model?)` — compiles once, returns the full result array.
- `initFHIRPathEvaluateOptions(userInvocationTable)` — registers custom functions for later `evaluate` calls.

### Compile reused extractors

Use `compileAsFirst` / `compileAsArray` for table columns, cards, list renderers, and other repeatedly-evaluated paths:

```ts
const getPatientName = compileAsFirst<Patient, HumanName>('Patient.name.first()');
const getLineItems = compileAsArray<Bundle, InvoiceLineItem>('Bundle.entry.resource.lineItem');
```

The expression is parsed once at module load, call sites document source/result types, and render code stays small and testable. Use `compileAsFirst` only when the expression is intentionally scalar; use `compileAsArray` when multiple matches are meaningful (`answerOption.valueCoding`, line items, interpretations, repeated answers).

### Use `evaluate` for runtime expressions

Use `evaluate` when the expression comes from runtime configuration or a FHIR resource — `choiceColumn.path` display expressions, reference-filter display text, `answerExpression`, `QuestionnaireResponseFormProvider` (`evaluateFhirpath={evaluate}`), and template resolution. Always treat the result as an array:

```ts
const value = evaluate(resource, expression, context)[0];

const result = evaluate(slot, "Slot.start.formatDate('dddd • D MMM • h:mm A')");
return result.length === 1 ? String(result[0]) : 'Unknown';
```

### Pass context deliberately

Expressions often depend on context variables (`%Patient`, `%Author`, `%QuestionnaireResponse`, included resources, `%linkId`). When evaluating a display path for an included resource, pass both the application context and included resources:

```ts
evaluate(resource, path, { ...context, ...includedResources, resource });
```

For compiled helpers that accept context, prefer parameters over interpolation:

```ts
const getByLinkId = compileAsFirst<Questionnaire, QuestionnaireItem>(
    'Questionnaire.repeat(item).where(linkId=%linkId)',
);
const item = getByLinkId(questionnaire, { linkId });
```

### Choose the FHIR model when needed

Some evaluations pass the R4 model (`fhirpath/fhir-context/r4`) explicitly. Use it when the expression depends on FHIR-aware behaviour, or when compiling generic paths from external configuration (configured column FHIRPaths, embedded template expressions). For simple property traversal inside already-shaped objects the default evaluator is usually enough.

### Custom functions

Register custom FHIRPath functions through `initFHIRPathEvaluateOptions` during initialization, before any form or loader evaluates expressions:

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

### Display helpers before new FHIRPath

When displaying answer values, prefer existing helpers such as `getDisplay`, `getArrayDisplay`, and `getValueFromAnswerValue` before adding new FHIRPath. If a choice display is configurable, use the configured `choiceColumn.path` and handle missing results with `?? ''`.
