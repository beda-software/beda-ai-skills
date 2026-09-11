# fhir-emr frontend code style — reference

Deep detail behind [SKILL.md](SKILL.md). React/TypeScript conventions specific to the `fhir-emr` frontend (`src/`).

## Uber components and framework mechanisms first

Before writing any bespoke page/component/form, run these checks in order — don't rely on
recalling the list, check it against the concrete requirement at hand:

1. **Does an uberComponent fit?** Check `ResourceListPage` / `ResourceListPageContent` /
   `ResourceDetailPage` / `QuestionnaireModal` / `ViewChart` against the actual requirement (e.g.
   does `DetailPageProps<R>`'s `tabs[].component` render-prop cover a page that resolves related
   resources across a bundle?). Only write a custom page once you've identified a specific gap an
   uberComponent can't cover.
2. **Does another shared framework mechanism already solve this?** Before hand-rolling logic that
   feels like it should be a common need (e.g. passing ambient resource context into a
   `QuestionnaireResponseForm`), check for an existing mechanism — e.g. `ClinicalContext` /
   `useClinicalContext` / `getResourceClinicalContext` instead of building a manual
   `launchContextParameters` array. Grep the framework source for the concept by name ("context",
   "launch") when unsure whether one exists.
3. **Does your own in-progress work already establish a pattern?** Before adding a new
   container, re-check other containers already added in the same feature/session (list pages,
   detail pages, attachment viewers, etc.) and mirror their uberComponent/mechanism choices rather
   than solving the same problem a different way each time.

## WithId<R> for API-loaded resources

Type resources loaded from the API as `WithId<R>` to make `.id` non-optional and remove the
null-checks/casts that would otherwise be needed everywhere it's read. Prefer parameterizing an
**uberComponent's own generic** with `WithId<R>` (e.g. `ResourceListPage<WithId<Task>>`,
`ResourceDetailPage<WithId<Task>>`, `ResourceListPageContent<WithId<Patient>>`) so the type
propagates through every derived callback prop automatically. Avoid per-callback `as WithId<R>`
casts or runtime `if (!id) return …` guards — if you find yourself writing one, it usually means
the generic should have been parameterized higher up instead.

## Error and fallback UI

Error/fallback UI (e.g. an "unable to load" state) should surface which specific lookup failed and
the concrete id/reference involved, not just a generic message — this is what makes a failure
traceable back to a specific resource instead of requiring a follow-up round-trip to ask "which
one?".

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

### FHIRPath vs plain TypeScript

Deciding to use `compileAsFirst`/`compileAsArray` at all is a separate question from *how* to
invoke FHIRPath once you've decided to. The test is **does this navigate a FHIR resource's
array/optional-shaped structure at all** — not whether it has a `.where()` filter:

- **Use FHIRPath** whenever the logic reads through an optional/array-shaped field (`CodeableConcept.coding`,
  `Reference`-typed arrays, etc.), filters a collection, type-filters a polymorphic field (`ofType()`,
  with the `fhirpath_r4_model` model from `'fhirpath/fhir-context/r4'`), or resolves a
  cross-bundle/cross-reference lookup (e.g. finding the `Bundle.entry` matching a `Reference`) —
  **even a single `.first()`/`.single()` with no `.where()` at all still counts**, because
  `coding`/similar fields are still 0..* and still need safe traversal. This is especially true once
  the extractor is shared across more than one call site: `getAppointmentTypeCode = compileAsFirst<Appointment,
  string>('Appointment.appointmentType.coding.code.first()')`, reused by every container that needs
  the appointment type, is the right call — centralizing the traversal in one compiled function
  beats re-deriving `appointment.appointmentType?.coding?.[0]?.code` at each call site. Compare
  `getReferralTypeCode`/`getReferralChannelCode` (`src/utils/referral.ts`), which need a `.where(system=...)`
  filter for the same reason but aren't otherwise different in kind.
- **Use plain TypeScript** only when there is *no FHIR resource structure to navigate at all* — the
  logic is purely combining values already in hand, e.g. building a `Reference` string from a known
  `resourceType` and `id` (`` `Practitioner/${id}` ``). There's nothing here for FHIRPath to do
  differently from a template literal, so don't convert it just for consistency with nearby FHIRPath
  code.
- When in doubt, ask rather than guess — this boundary has been misjudged in both directions: converting
  zero-navigation literal/string construction to FHIRPath, and *also* mistakenly calling a shared,
  resource-navigating single-field extractor "trivial" and reverting it to plain TypeScript because
  it happened to lack a `.where()` filter. Presence of a filter is not the test; resource-shape
  navigation is.

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
