# beda-ai-skills

Team AI skills and authoring guides for the Beda FHIR EMR ecosystem. Works with **Cursor** and **Claude Code** — same `SKILL.md` format, one install script for both.

**Start here:** [AGENTS.md](AGENTS.md) — index, skill catalog, and usage instructions.

## One-command install

**Cursor (current project):**

```bash
curl -fsSL https://gitlab.beda.software/emr/beda-ai-skills/-/raw/main/install.sh | bash
```

**Claude Code:**

```bash
curl -fsSL https://gitlab.beda.software/emr/beda-ai-skills/-/raw/main/install.sh | bash -s -- --claude
```

**All your projects (personal scope):**

```bash
curl -fsSL https://gitlab.beda.software/emr/beda-ai-skills/-/raw/main/install.sh | bash -s -- --global
```

**Already cloned:**

```bash
git clone git@gitlab.beda.software:emr/beda-ai-skills.git
cd beda-ai-skills && ./install.sh          # Cursor
./install.sh --claude --global             # Claude Code, all projects
```

Options: `--cursor` (default), `--claude`, `--global`, `--target /path/to/skills`.

After install, restart the IDE or start a new agent session. Skills load automatically by task — or invoke manually (`/fhir-emr-mapping` in Cursor).

See [skills/README.md](skills/README.md) for the full usage guide.
