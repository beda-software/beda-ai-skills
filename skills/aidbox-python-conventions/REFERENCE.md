# Aidbox Python app conventions — reference

Deep detail behind [SKILL.md](SKILL.md). Coding conventions and testing practices for Aidbox Python apps built with `aidbox-python-sdk`. Applies to any backend service in the Beda ecosystem that uses the Python SDK.

## Function naming

Name every callable so the stem reads as an **imperative verb** (`fetch_patient`, `build_payload`, `parse_reference`). Avoid noun-only names (`payload`, `helpers`, `data`) unless the codebase already mandates otherwise.

Constructors, standard protocol hooks (`__len__`), and `@property` accessors are exempt.

## File layout

In each source file, after imports and module-level constants (and any types/models they need), order functions like a **call tree from the root**:

1. **Root entry point** — the public function that is the file's main API.
2. **Direct callees** — functions the root calls, in first-use order.
3. **Deeper helpers** — for each callee, its own helpers immediately below it.
4. **`if __name__ == "__main__"`** last (Python).

When a file has multiple independent roots, list the more important or externally invoked one first.

## Comments

Add comments only when they carry information the code does not already express — non-obvious **why**, business rules, invariants, or external constraints.

**Do not add** comments that restate names, types, or structure already clear from function names, imports, fixtures, or tests.

**When refactoring:** preserve existing comments. Do not delete or shorten them unless the user asks, or the commented behavior no longer exists.

## Python typing

Always specify types on function parameters and return values. Use `r4b.*` models from `fhirpy_types_r4b` for FHIR resources.

## FHIR client usage

- Use `AsyncFHIRClient` with typed resources: `r4b.Patient`, `r4b.Encounter`, etc.
- Prefer `await fhir_client.get(r4b.ResourceType, reference)` when you have a reference.
- When searching via `fhir_client.resources(r4b.ResourceType).search(...)`, use **`.get()`** instead of `.first()`.
- If a reference is present, assume the referred resource exists in the database; do not add separate existence guards for that case.

## Subscription event payloads

Subscription handlers receive `event["resource"]` as a plain `dict`. **Do not** treat it as an `r4b.*` resource — do not pass it to `model_validate()`, typed FHIRPath helpers, or other code that expects a validated model.

Extract the resource `id` from the event and **fetch** the typed resource from Aidbox:

```python
encounter_id = event["resource"]["id"]
encounter = await fhir_client.get(r4b.Encounter, f"Encounter/{encounter_id}")
```

Pass only the `id` (or a reference string) into orchestrators; let them fetch `r4b.*` models via `fhir_client.get`.

## Required fields on typed models

`fhirpy_types_r4b` models mark many FHIR elements optional even when our workflows always populate them. When you **know** a field is guaranteed for the code path, it is acceptable to use **`assert`** on that field:

```python
patient = await fetch_patient_by_reference(fhir_client, patient_reference)
assert patient.name
display_name = format_human_name(patient.name[0])
```

**Policy:**

- In the future, guaranteed fields will be defined by our **Implementation Guide (IG)** profiles.
- Until then, **ask the user for confirmation** before adding `assert` on a FHIR field when it is not immediately obvious from the code path.
- Prefer **`compile_as_first` helpers** in `app/utils/<resource>.py` for reusable, safe extraction (returns `None` when absent).

## FHIRPath resource helpers

When you need a nested attribute from a FHIR resource, add a helper in `app/utils/<resource>.py` using `compile_as_first` from `fhirpathpy`:

```python
get_encounter_practitioner_role_reference = compile_as_first(
    "Encounter.participant.individual.reference.where(startsWith('PractitionerRole/'))",
    r4b.Encounter,
    str,
)
```

`compile_as_first` already picks the first result — do **not** add `.first()` at the end of the FHIRPath expression. Every such helper **must** have unit tests (positive cases at minimum).

## Resource template lookups

When your app resolves FHIR or custom resources by a canonical identifier (e.g. prompt templates, configuration bundles), resolve by **`url`** (or another stable canonical field), not by resource `id`. The `url` is the family identifier; `id` is only the server-assigned instance id.

## Testing

**Run tests from the monorepo root that owns the Docker test stack**, not from the app subfolder:

```bash
cd <monorepo-root>
make test
```

To run a subset, pass a path relative to the app folder:

```bash
make test TEST_PATH=./tests/test_my_module/
make test TEST_PATH=./tests/test_my_module/test_example.py
```

Do **not** run `poetry run pytest` directly from the app folder — the test stack is wired through Docker compose.

| What | How |
| --- | --- |
| Sync FHIRPath helpers (`app/utils/*.py`) | Unit tests with in-memory `r4b.*` instances — no database |
| Async code that uses `fhir_client` | **Do not mock** the FHIR client. Use the **`safe_db`** fixture |
| Integration flows | Prefer `safe_db` + real FHIR resources over mocks |

### Test fixtures

- Build unsaved FHIR resources with **`tests/fhir_resource_factories.py`** (`build_patient`, `build_encounter`, etc.).
- Pass **`r4b.Reference`** for links between resources, not separate id/display arguments.
- **Never assign `id`** on test resources. Let Aidbox assign ids on `save()` / `create()`.

## Lint and typecheck

After code changes, from the app folder:

```bash
poetry run ruff format .
poetry run ruff check .
poetry run mypy
```

All three must pass before finishing.
