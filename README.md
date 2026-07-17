# beda-ai-skills

Team AI skills and authoring guides for the Beda FHIR EMR ecosystem. Works with **Cursor** and **Claude Code**.

**Start here:** [AGENTS.md](AGENTS.md) — index, skill catalog, and usage instructions.

## Quick install

```bash
git clone git@gitlab.beda.software:emr/beda-ai-skills.git

# Cursor
mkdir -p .cursor/skills && cp -r beda-ai-skills/skills/* .cursor/skills/

# Claude Code
mkdir -p .claude/skills && cp -r beda-ai-skills/skills/* .claude/skills/
```

See [skills/README.md](skills/README.md) for the full usage guide.
