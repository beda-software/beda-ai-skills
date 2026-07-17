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
5. **Do:** Cover all `utils/fhirpath` helpers with tests.
6. **Don't:** Leave `console.log` / `console.error` / `console.warn` in committed code.
7. **Don't:** Use nested ternary operators.

## Related skills

- FHIRPath in forms and columns: [beda-sdc-forms/FHIRPATH.md](../beda-sdc-forms/FHIRPATH.md)
- i18n strings: [translate](../translate/SKILL.md)
