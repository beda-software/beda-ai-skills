# Practical Guide to AI Coding Tools

> Written from ~6 months of daily use as a software engineer. Intended to help teammates adopt AI tools faster and avoid common pitfalls.

Team skills and domain guides live in [AGENTS.md](AGENTS.md) and [skills/](skills/README.md). Load the relevant skill before starting domain-specific work (questionnaires, mappings, SDC forms, OrgBAC, etc.).

---

## Tool Overview

| Tool | Best for |
|---|---|
| Claude Code (CLI) | Complex multi-step tasks, long refactors, agentic workflows |
| Cursor / Windsurf | In-editor work, inline completions, targeted file edits |
| Gemini CLI, OpenCode, Pi | Evaluated — not recommended yet; too many hallucinations and unintended changes |

---

## Claude / Claude Code

### What it's good at

- Writing new features and boilerplate
- Debugging and tracing errors
- Code review and explaining unfamiliar code
- Getting up to speed on unfamiliar domains and libraries quickly
- Long multi-step tasks spanning multiple files

### Weak spots

- **Hallucinated APIs** — it will write confident, plausible, wrong code. Always verify API usage against docs or real source.
- **Auto-mode scope creep** — in agentic mode it tends to go beyond what was asked. Use plan mode first (see tips below).
- **Excessive grepping** — on large projects it can spend a lot of time searching files instead of using indexed tools. Mitigate with GitNexus (see External Tools).
- **Hidden decisions in refactoring** — complex updates can carry implicit architectural choices. Review diffs carefully, don't just accept.

### Tips

**Use plan mode.** It's a first-class feature — press `Shift+Tab` in Claude Code to switch to plan mode before any non-trivial task. The agent proposes a plan, you review and approve before a single line is written. This alone eliminates most scope creep.

**Load the hunk skill for diff visibility.** [hunk](https://www.hunk.dev/) gives you a live diff view including unstaged changes, with theme support. Run it as:
```
mise x hunk@latest -- hunk diff main --watch --theme catppuccin-macchiato
```
([mise](https://mise.jdx.dev/) is a dev tools version manager used to run hunk here.)

Then load its Claude Code skill into your active session — the skill path is returned by:
```
mise x hunk@latest -- hunk skill path
```
This lets Claude leave structured review comments directly tied to the active diff.

**Set up a global `~/.claude/CLAUDE.md`.** This file is auto-loaded into every Claude session. Use it to define project conventions, tool rules, domain knowledge (e.g. FHIR), and assistant behavior once — rather than repeating context in every prompt.

**Use GitNexus for codebase navigation.** GitNexus builds a static snapshot of the codebase for faster querying and impact analysis. Index with `npx gitnexus analyze`, then Claude can use it instead of grepping. Caveat: keep the index up to date after significant changes, and be aware the agent will fall back to grep if the index is stale.

**Domain-specific skills.** For FHIR work, two dedicated skills are available:
- `fhir-developer:fhir-developer-skill` — REST endpoints, HTTP status codes, OperationOutcome, SMART on FHIR, Bundles
- `fhir-developer-skills:fhir-software` — FHIR R4/R4B/R5, IG authoring, FSH/SUSHI/GoFSH, validation, terminology

---

## Cursor / Windsurf

### What it's good at

- Inline tab completions while typing
- Chat and agent mode for targeted edits
- Multi-file changes that land directly in the editor
- Codebase Q&A without leaving the IDE
- **Key advantage:** no context switching — changes appear directly in your files

### Weak spots

- Falls apart on complex, multi-step tasks that require sustained reasoning — use Claude Code for those
- Context/memory issues in very large files or long sessions

### Tips

**Pick the right model.** Model selection matters more than you'd think. Best experience has been with **Composer 2.5 Fast** — don't leave it on the default.

**Use plan mode here too.** Switch the mode selector from Agent to Plan before asking for any non-trivial change. Same principle as Claude Code — review the plan before any edits are made.

**Iterate on changes in hunks.** Cursor's biggest UX win is precise logging and easy navigation between changed hunks. Use it: accept or reject individual code blocks, ask for follow-up adjustments, and review new changes hunk by hunk. Don't just accept everything at once.

---

## Cross-Cutting Tips

These apply regardless of which tool you use.

### 1. Always use plan mode

Before any non-trivial implementation, ask the AI to produce a plan. Review it. Push back if the scope is wrong. Only then proceed to implementation. Both Claude Code and Cursor support this as a first-class mode.

### 2. Keep tasks small and narrow

AI tools perform best on focused, well-scoped requests. Break features into the smallest meaningful unit before handing them to the agent. A single well-defined task beats a broad feature request every time.

### 3. Be specific in your prompts

Broad requests produce broad, often wrong output. Instead of:
> "Add this feature"

Write:
> "Add X feature using library Y, following the pattern in `src/components/Foo.tsx`, with the same prop structure as `Bar`"

Include: what you want, a reference to valid existing examples, and any architectural or library constraints.

### 4. Write tests — and know when to write them first

Default: ask the AI to generate tests after implementation, then review them carefully.

For complex or unclear requirements: write tests first. Tests force you to define the expected behavior precisely, which makes the AI's implementation more accurate and gives you a concrete spec to work from.

### 5. Add AI tool artifacts to your global gitignore

AI tools like Claude Code and GitNexus create files and folders inside your repo — usually hidden dot-notated ones (e.g. `.claude/`, `.gitnexus/`). These still show up in `git status` and `git diff`, and since they're personal or tool-specific they shouldn't be committed or shared across the team.

Add them to your **global local gitignore** (`~/.gitignore_global` or equivalent) rather than the project `.gitignore`, since these are your tools, not the project's concern. Make sure git is configured to use it:
```
git config --global core.excludesFile ~/.gitignore_global
```

### 6. Always run your linter and formatter after AI edits

AI output is not formatter-clean. Import order, spacing, and style issues are common in every tool. Build a habit of running your linter and formatter against every modified file before committing — don't assume the AI handled it.

---

## Common Mistakes

| Mistake | What to do instead |
|---|---|
| Broad, vague requests | Be specific: describe the feature, reference existing patterns, specify libraries |
| Skipping plan mode | Always review a plan before implementation starts |
| Accepting large diffs without reading | Review hunk by hunk; hidden decisions compound over time |
| Trusting AI-generated API calls | Verify against real docs or source — hallucinated APIs are confident and wrong |
| Ignoring linting after edits | Run linter/formatter on every modified file |
| Using AI for complex tasks in Cursor | Offload sustained multi-step reasoning to Claude Code |
| Letting the index go stale (GitNexus) | Re-index after significant refactors |
