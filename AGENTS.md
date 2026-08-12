# AGENTS.md — Team AI & authoring guide

Central index for AI-assisted development in the Beda FHIR EMR ecosystem. Use this file to find the right guide or skill before starting work.

## How this repo is organized

| Layer | Location | Purpose |
| --- | --- | --- |
| **Index** | `beda-ai-skills/AGENTS.md` (this file) | Navigation |
| **Skills** | `beda-ai-skills/skills/` | Self-contained domain guides (SKILL.md + REFERENCE.md), auto-discoverable by Cursor |
| **Examples** | `beda-ai-skills/agents.example.md` | Template for project-specific agent overlays |

Each skill is a self-contained folder: `SKILL.md` (entry point, loaded by the agent) plus `REFERENCE.md` (full guide).

---

## How to use the skills (start here)

The `SKILL.md` format is the standard Anthropic Agent Skills spec — the same folders work in **Cursor and Claude Code**.

**One-time setup** — clone once, then install globally (recommended):

```bash
git clone git@github.com:beda-software/beda-ai-skills.git ~/beda-ai-skills
~/beda-ai-skills/install.sh --global            # → ~/.cursor/skills (all projects)
```

To install into a single project only: `~/beda-ai-skills/install.sh ~/work/fhir-emr`. Full notes: [README.md](README.md).

**Then just work normally.** You don't "call" a skill — the agent reads each skill's `description` and loads it automatically when your request matches. For example:

| You ask the agent | Skill that kicks in |
| --- | --- |
| "Add a BMI calculated field to the vitals questionnaire" | `fhir-emr-questionnaire` |
| "Write an extraction mapping for this form" | `fhir-emr-mapping` |
| "Why does my FHIRPath expression return empty / how do I sum optional fields?" | `fhirpath` |
| "I get 403 'resource not available in Organization'" | `aidbox-orgbac-multitenancy` |
| "Add a component for the patient card" | `fhir-emr-frontend` |
| "Translate the new strings" | `translate` |

**To force a specific skill**, mention it by name in your prompt: *"Using the fhir-emr-mapping skill, review this Mapping file."*

**Without Cursor or Claude Code** (other AI chats, code review, onboarding) — the skills are plain markdown: read `SKILL.md` for the rules, `REFERENCE.md` for details, or attach them to any AI chat as context.

Step-by-step usage guide with worked examples: [skills/README.md](skills/README.md).

---

## Quick navigation — what are you working on?

| You are working on | Skill |
| --- | --- |
| `resources/**/Questionnaire/**/*.yaml` | [fhir-emr-questionnaire](skills/fhir-emr-questionnaire/SKILL.md) |
| `resources/**/Mapping/**/*.yaml` | [fhir-emr-mapping](skills/fhir-emr-mapping/SKILL.md) |
| FHIRPath expressions (Questionnaire, Mapping, frontend TS, backend) | [fhirpath](skills/fhirpath/SKILL.md) |
| OrgBAC, multi-tenancy, AccessPolicy | [aidbox-orgbac-multitenancy](skills/aidbox-orgbac-multitenancy/SKILL.md) |
| Aidbox Python App operations | [aidbox-python-app-operation](skills/aidbox-python-app-operation/SKILL.md) |
| Python Aidbox app conventions | [aidbox-python-conventions](skills/aidbox-python-conventions/SKILL.md) |
| React / TypeScript UI (`src/`) | [fhir-emr-frontend](skills/fhir-emr-frontend/SKILL.md) |
| i18n / locale strings | [translate](skills/translate/SKILL.md) |

### Where these skills apply

- Questionnaire YAML: any `resources/**/Questionnaire/**/*.yaml`
- Mapping YAML: any `resources/**/Mapping/**/*.yaml`

### Skill relationships

```
fhir-emr-questionnaire ──┐
fhir-emr-mapping ────────┼──► fhirpath  (FHIRPath expression language — shared by all)
fhir-emr-frontend ───────┤
aidbox-python-conventions┘

fhir-emr-questionnaire / fhir-emr-mapping ──► aidbox-orgbac-multitenancy  (org-scoped extraction)
aidbox-python-app-operation ──────────────► aidbox-orgbac-multitenancy
```

- **Questionnaire + Mapping** skills cover YAML authoring rules (including Quick Do/Don't checklists).
- **fhirpath** covers the FHIRPath expression language shared by Questionnaire, Mapping, frontend, and backend — it is NOT FPML (the Mapping templating language, which lives in `fhir-emr-mapping`).
- **fhir-emr-frontend** covers React/TypeScript conventions specific to this EMR repo.
- **aidbox-orgbac-multitenancy** is needed when forms or operations run org-scoped.
- **aidbox-python-app-operation** and **aidbox-python-conventions** apply to Aidbox Python apps.

---

## AI workflow essentials

Key team practices:

- **Plan mode first** — review scope before implementation (Claude Code and Cursor).
- **Small, focused tasks** — one well-defined change per agent request.
- **Reference existing patterns** — point the agent at a working example file.
- **Review diffs hunk by hunk** — do not accept large changes blindly.
- **Run linter/formatter** after every AI edit.

For project-specific overlays (commit style, vendored code rules, test commands), see [agents.example.md](agents.example.md).

Verification example: [skills/fhir-emr-mapping/EXAMPLE.md](skills/fhir-emr-mapping/EXAMPLE.md).
