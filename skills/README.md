# Skills — how to use

Practice-tested Cursor Agent Skills for the Beda FHIR EMR ecosystem. Each skill is a **self-contained folder**: `SKILL.md` (entry point with YAML frontmatter, loaded by the agent) plus `REFERENCE.md` (full guide) and optional extras.

The catalog and skill-relationship graph live in [AGENTS.md](../AGENTS.md).

## What a skill is

A skill is a set of instructions the AI agent loads **on demand**. The YAML frontmatter in `SKILL.md` contains a `description` — Cursor matches your request against it and pulls the skill in automatically. You keep prompting as usual; the skill just makes the agent follow our team rules instead of generic ones.

## Step 1 — install

The `SKILL.md` format is the standard [Anthropic Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) spec — the same folders work in both Cursor and Claude Code.

**One command (recommended):**

```bash
curl -fsSL https://gitlab.beda.software/emr/beda-ai-skills/-/raw/main/install.sh | bash
```

Claude Code: add `| bash -s -- --claude`. Personal scope (all projects): add `| bash -s -- --global`.

**Manual install** — if you already have the repo:

```bash
./install.sh                              # Cursor, project scope
./install.sh --claude --global            # Claude Code, personal scope
mkdir -p .cursor/skills && cp -r skills/* .cursor/skills/   # copy without script
```

Both tools discover skills the same way and load them automatically by `description`. After a `git pull` that changes skills, re-run `./install.sh`.

**Cross-skill links** (e.g. `fhir-emr-questionnaire` → `fhirpath`) resolve only when the related skills are copied together, which is why copying all of them at once is recommended.

## Step 2 — just work; skills load automatically

You don't invoke skills manually. Write your request in Cursor or Claude Code as usual — if it matches a skill's domain, the agent loads it before answering.

**Worked example.** You type:

> Add a total-score field to the AUDIT questionnaire that sums the itemWeight of all selected options

What happens:

1. Cursor matches the request against skill descriptions → loads `fhir-emr-questionnaire`.
2. The agent now knows our rules: `linkId → text → type` order, `%resource.repeat(item)...` lookup, `.sum()` instead of `+`, `type: decimal` for calculated fields.
3. The generated YAML follows team conventions instead of generic FHIR examples from the internet.

Without the skill, the agent typically produces `A + B` sums (breaks on empty answers) or generic SDC extensions that our renderer doesn't support.

The same flow applies in Claude Code — skills installed in `.claude/skills/` are matched and loaded the same way.

## Step 3 — when you want control

- **Force a skill:** name it in the prompt — *"Using the fhir-emr-mapping skill, review resources/init-seeds/Mapping/extract-vital-signs.yaml"*.
- **Check it loaded:** the agent references skill rules in its answer (e.g. cites the golden rule); if unsure, ask *"which skill did you use?"*.
- **Go deeper yourself:** open the skill's `REFERENCE.md` — it's the full human-readable guide behind the short `SKILL.md`.

A verification walk-through against a real repo file: [fhir-emr-mapping/EXAMPLE.md](fhir-emr-mapping/EXAMPLE.md).

## Using skills outside Cursor / Claude Code

The skills are plain markdown, so they work anywhere:

- **Any AI chat (claude.ai, ChatGPT, …):** attach `SKILL.md` (+ `REFERENCE.md` for depth) as context to your conversation.
- **CLAUDE.md / AGENTS.md overlays:** reference the skill files from your project's agent config so they're always in context.
- **Humans:** read them as onboarding docs — `REFERENCE.md` files are written for people, not just agents.

## Contributing a new skill

1. Create `beda-ai-skills/skills/<skill-name>/SKILL.md` with YAML frontmatter (`name`, `description`). The `description` decides when the agent auto-loads the skill — write it as "Use when …" with concrete triggers.
2. Keep `SKILL.md` short and focused; move deep detail to `REFERENCE.md` **inside the same folder** — skills must stay self-contained when copied.
3. Add the skill to the catalog in [AGENTS.md](../AGENTS.md).
4. Test: copy to `.cursor/skills/` (or `.claude/skills/`), ask a matching question, and verify the agent applies the skill's rules.

See also: [ai-tools-experience.md](../ai-tools-experience.md) for general AI tooling practices.
