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
