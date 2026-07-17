# agents.example.md — Project-specific agent overlay (template)

Copy relevant sections into your project's `AGENTS.md` or `CLAUDE.md`. Keep only what applies to the target repo.

---

## Vendored code (`contrib/`)

- **Do not upgrade, refactor, or bulk-sync vendored code in `contrib/`** unless explicitly asked.

## Commits

When asked to commit:

1. **Split changes into smaller, semantic commits** — one logical change per commit (feature, fix, refactor, test, config).
2. Use **Conventional Commits** format:

```
<type>(<optional scope>): <short description>

<optional body>
```

Common types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`, `ci`, `build`.

- Write a clear subject line focused on **why**, not a file list.
- Match the existing style of the target repository.

**Do not add tool or agent attribution trailers.** No `Co-authored-by:` for AI, no `Made-with:` / `Generated-by:` lines.

## Code style & quality

### Frontend (fhir-emr)

See [skills/fhir-emr-frontend](skills/fhir-emr-frontend/SKILL.md) for React/TypeScript conventions:
- Component directory structure (`index.tsx`, `hooks.ts`, `types.ts`, `utils.ts`)
- Guard clauses, no hardcoded colors, Ant Design theme
- All `utils/fhirpath` utils must have tests

### Python (Aidbox apps)

See [skills/aidbox-python-conventions](skills/aidbox-python-conventions/REFERENCE.md) for Python conventions:
- Python 3.13+, Poetry, ruff, mypy
- Typed `r4b.*` FHIR resources
- Integration tests with `safe_db`, not mocked FHIR client

## Testing

### Frontend

```bash
docker compose up -d   # start stack first
yarn test
```

### Python (Aidbox apps)

```bash
cd <monorepo-root>   # the directory that owns docker-compose / Makefile for tests
make test
```

## Domain guides

Point the agent at the right guide for the task:

| Task | Guide |
| --- | --- |
| Frontend UI (`src/`) | [skills/fhir-emr-frontend](skills/fhir-emr-frontend/SKILL.md) |
| Questionnaire YAML | [skills/fhir-emr-questionnaire](skills/fhir-emr-questionnaire/SKILL.md) |
| Mapping YAML | [skills/fhir-emr-mapping](skills/fhir-emr-mapping/SKILL.md) |
| FHIRPath expressions (all layers) | [skills/fhirpath](skills/fhirpath/SKILL.md) |
| OrgBAC / multi-tenancy | [skills/aidbox-orgbac-multitenancy](skills/aidbox-orgbac-multitenancy/SKILL.md) |
| AI tool usage | [ai-tools-experience.md](ai-tools-experience.md) |
