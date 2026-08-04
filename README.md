# beda-ai-skills

Team AI skills and authoring guides for the Beda FHIR EMR ecosystem. Works with **Cursor** and **Claude Code** — same `SKILL.md` format, one install script for both.

**Start here:** [AGENTS.md](AGENTS.md) — index, skill catalog, and usage instructions.

## Install

You need GitLab access to `emr/beda-ai-skills` (SSH key or HTTPS credentials).

**1. Clone once** into any convenient folder:

```bash
git clone git@gitlab.beda.software:emr/beda-ai-skills.git ~/beda-ai-skills
```

HTTPS: `git clone https://gitlab.beda.software/emr/beda-ai-skills.git ~/beda-ai-skills`

**2. Install globally** (recommended) — skills become available in all projects:

```bash
~/beda-ai-skills/install.sh --global                 # Cursor → ~/.cursor/skills
~/beda-ai-skills/install.sh --claude --global        # Claude Code → ~/.claude/skills
```

**Optional: install into a single project only:**

```bash
~/beda-ai-skills/install.sh ~/work/fhir-emr                 # Cursor → project/.cursor/skills
~/beda-ai-skills/install.sh --claude ~/work/fhir-emr        # Claude Code → project/.claude/skills
```

Options: `--cursor` (default), `--claude`, `--global`, `--project /path`, `--target /path/to/skills`.

**Updates:**

```bash
cd ~/beda-ai-skills && git pull
~/beda-ai-skills/install.sh --global    # same args as before
```

After install, restart the IDE or start a new agent session. Skills load automatically by task — or invoke manually (`/fhir-emr-mapping` in Cursor).

See [skills/README.md](skills/README.md) for the full usage guide.
