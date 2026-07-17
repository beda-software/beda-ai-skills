---
name: aidbox-python-conventions
description: Follow Aidbox Python app coding conventions — imperative function naming, call-tree file layout, typed r4b FHIR client usage, subscription event handling, FHIRPath helpers with compile_as_first, safe_db integration testing, and ruff/mypy checks. Use when writing or reviewing Python code in an aidbox-python-sdk app.
---

# Aidbox Python conventions

Full guide: [REFERENCE.md](REFERENCE.md)

## Quick rules

1. **Function names** — imperative verbs (`fetch_patient`, `build_payload`).
2. **File layout** — call tree from root entry point downward.
3. **Comments** — only for non-obvious why; never restate what code already shows.
4. **Types** — always annotate parameters and returns; use `r4b.*` for FHIR resources.
5. **FHIR client** — `await fhir_client.get(r4b.Type, ref)`; search with `.get()` not `.first()`.
6. **Subscriptions** — `event["resource"]` is a plain dict; fetch typed resource by id.
7. **FHIRPath helpers** — `compile_as_first` in `app/utils/<resource>.py` + unit tests.
8. **Tests** — `safe_db` + real FHIR resources; never mock `fhir_client`.
9. **Lint** — `ruff format`, `ruff check`, `mypy` must pass.

## Related skills

- Custom operations: [aidbox-python-app-operation](../aidbox-python-app-operation/SKILL.md)
- Multi-tenancy: [aidbox-orgbac-multitenancy](../aidbox-orgbac-multitenancy/SKILL.md)
