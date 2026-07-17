---
name: fhir-emr-frontend
description: Follow fhir-emr React/TypeScript conventions — component directory structure (index.tsx, hooks.ts, types.ts, utils.ts), guard clauses, Ant Design theme usage, typed hooks, and fhirpath test coverage. Use when writing or reviewing frontend code in src/.
---

# fhir-emr frontend code style

Full guide: [REFERENCE.md](REFERENCE.md)

EMR-specific frontend conventions. Applies when editing `src/` in the fhir-emr repo.

## Quick Do/Don't

1. **Do:** Place each component in its own directory with `index.tsx`, `hooks.ts`, `types.ts`, `utils.ts`.
2. **Do:** Keep business logic in `hooks.ts`; components stay presentational.
3. **Do:** Use Ant Design theme — no hardcoded colors.
4. **Do:** Use guard clauses (early returns for negative cases).
5. **Do:** Evaluate FHIRPath through the `src/utils/fhirpath.ts` wrapper (`compileAsFirst` / `compileAsArray` / `evaluate`), never `fhirpath.evaluate` directly. See [REFERENCE.md](REFERENCE.md#fhirpath-in-the-frontend).
6. **Do:** Cover all `utils/fhirpath` helpers with tests.
7. **Don't:** Leave `console.log` / `console.error` / `console.warn` in committed code.
8. **Don't:** Use nested ternary operators.

## Related skills

- FHIRPath expression language (syntax + cross-host rules): [fhirpath](../fhirpath/SKILL.md). The frontend invocation wrapper (`src/utils/fhirpath.ts`) is in this skill's [REFERENCE.md](REFERENCE.md#fhirpath-in-the-frontend).
- i18n strings: [translate](../translate/SKILL.md)
