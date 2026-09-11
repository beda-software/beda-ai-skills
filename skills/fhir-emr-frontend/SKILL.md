---
name: fhir-emr-frontend
description: Follow fhir-emr React/TypeScript conventions — component directory structure (index.tsx, hooks.ts, types.ts, utils.ts), guard clauses, Ant Design theme usage, typed hooks, and fhirpath test coverage. Use when writing or reviewing frontend code in src/.
---

# fhir-emr frontend code style

Full guide: [REFERENCE.md](REFERENCE.md)

EMR-specific frontend conventions. Applies when editing `src/` in the fhir-emr repo.

## Quick Do/Don't

1. **Do:** Before writing a bespoke page/component/form, check whether an uberComponent
   (`ResourceListPage` / `ResourceListPageContent` / `ResourceDetailPage` / `QuestionnaireModal` /
   `ViewChart`) fits, and check for other shared framework mechanisms (e.g. `ClinicalContext` for
   passing ambient resource context into a `QuestionnaireResponseForm`) before hand-rolling
   equivalent logic. See [REFERENCE.md](REFERENCE.md#uber-components-and-framework-mechanisms-first).
2. **Do:** Place each component in its own directory with `index.tsx`, `hooks.ts`, `types.ts`, `utils.ts`.
3. **Do:** Keep business logic in `hooks.ts`; components stay presentational.
4. **Do:** Use Ant Design theme — no hardcoded colors.
5. **Do:** Use guard clauses (early returns for negative cases).
6. **Do:** Type API-loaded resources as `WithId<R>`, parameterizing the **uberComponent's own
   generic** (e.g. `ResourceListPage<WithId<Task>>`) rather than casting/guarding per callback. See
   [REFERENCE.md](REFERENCE.md#withidr-for-api-loaded-resources).
7. **Do:** Reserve FHIRPath for anything that navigates a FHIR resource's array/optional-shaped
   structure (even a single `.first()` with no `.where()`), filters/type-filters a collection, or
   does a cross-bundle/cross-reference lookup; use plain TypeScript only when there's no resource
   structure to navigate at all (e.g. building a `Reference` string from values already in hand).
   A `.where()` filter is not the dividing line — resource-shape navigation is. See
   [REFERENCE.md](REFERENCE.md#fhirpath-vs-plain-typescript).
8. **Do:** Evaluate FHIRPath through the `src/utils/fhirpath.ts` wrapper (`compileAsFirst` / `compileAsArray` / `evaluate`), never `fhirpath.evaluate` directly. See [REFERENCE.md](REFERENCE.md#fhirpath-in-the-frontend).
9. **Do:** Cover all `utils/fhirpath` helpers with tests.
10. **Do:** Error/fallback UI (e.g. an "unable to load" state) should name the specific failed
    lookup and the concrete id/reference involved, not a generic message. See
    [REFERENCE.md](REFERENCE.md#error-and-fallback-ui).
11. **Don't:** Leave `console.log` / `console.error` / `console.warn` in committed code.
12. **Don't:** Use nested ternary operators.

## Related skills

- FHIRPath expression language (syntax + cross-host rules): [fhirpath](../fhirpath/SKILL.md). The frontend invocation wrapper (`src/utils/fhirpath.ts`) is in this skill's [REFERENCE.md](REFERENCE.md#fhirpath-in-the-frontend).
- i18n strings: [translate](../translate/SKILL.md)
