# beda-ai-skills

Team AI skills and authoring guides for the Beda FHIR EMR ecosystem. Works with **Cursor** and **Claude Code** — same `SKILL.md` format, one install script for both.

**Start here:** [AGENTS.md](AGENTS.md) — index, skill catalog, and usage instructions.

## Install

You need GitLab access to `emr/beda-ai-skills` (SSH key or HTTPS credentials).

**1. Clone the repo (once):**

```bash
git clone git@gitlab.beda.software:emr/beda-ai-skills.git
cd beda-ai-skills
```

HTTPS alternative:

```bash
git clone https://gitlab.beda.software/emr/beda-ai-skills.git
cd beda-ai-skills
```

**2. Run the install script from the project where you want the skills** (or pass `--global`):

```bash
# Cursor — current project → .cursor/skills
./install.sh

# Claude Code — current project → .claude/skills
./install.sh --claude

# Cursor — all projects → ~/.cursor/skills
./install.sh --global

# Claude Code — all projects → ~/.claude/skills
./install.sh --claude --global
```

Typical flow when your shell is already inside a product repo (e.g. `fhir-emr`):

```bash
git clone git@gitlab.beda.software:emr/beda-ai-skills.git ~/beda-ai-skills
~/beda-ai-skills/install.sh
```

Options: `--cursor` (default), `--claude`, `--global`, `--target /path/to/skills`.

**Updates:** after skills change upstream:

```bash
cd ~/beda-ai-skills   # or wherever you cloned
git pull
./install.sh          # re-run with the same flags you used before
```

After install, restart the IDE or start a new agent session. Skills load automatically by task — or invoke manually (`/fhir-emr-mapping` in Cursor).

See [skills/README.md](skills/README.md) for the full usage guide.
