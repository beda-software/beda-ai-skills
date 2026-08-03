#!/usr/bin/env bash
# Install beda-ai-skills into Cursor or Claude Code.
#
# Usage:
#   git clone git@gitlab.beda.software:emr/beda-ai-skills.git
#   cd beda-ai-skills && ./install.sh
#
# Examples:
#   ./install.sh                      # Cursor, project scope (.cursor/skills)
#   ./install.sh --claude             # Claude Code, project scope
#   ./install.sh --global             # Cursor, personal scope (~/.cursor/skills)
#   ./install.sh --claude --global    # Claude Code, personal scope
#   ./install.sh --target /path/to/skills

set -euo pipefail

REPO_URL="${BEDA_AI_SKILLS_REPO:-git@gitlab.beda.software:emr/beda-ai-skills.git}"
REF="${BEDA_AI_SKILLS_REF:-main}"
TOOL="cursor"
SCOPE="project"
TARGET=""
TMPDIR=""

usage() {
  sed -n '2,12p' "$0" | tail -n +2
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cursor) TOOL="cursor"; shift ;;
    --claude) TOOL="claude"; shift ;;
    --global) SCOPE="global"; shift ;;
    --target)
      TARGET="${2:?--target requires a path}"
      shift 2
      ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 1 ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  if [[ "$TOOL" == "claude" ]]; then
    [[ "$SCOPE" == "global" ]] && TARGET="$HOME/.claude/skills" || TARGET=".claude/skills"
  else
    [[ "$SCOPE" == "global" ]] && TARGET="$HOME/.cursor/skills" || TARGET=".cursor/skills"
  fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE=""

if [[ -d "$SCRIPT_DIR/skills" && -f "$SCRIPT_DIR/skills/fhir-emr-mapping/SKILL.md" ]]; then
  SOURCE="$SCRIPT_DIR/skills"
else
  TMPDIR="$(mktemp -d)"
  trap 'rm -rf "$TMPDIR"' EXIT
  echo "Cloning $REPO_URL (ref: $REF)..."
  git clone --depth 1 --branch "$REF" "$REPO_URL" "$TMPDIR/repo"
  SOURCE="$TMPDIR/repo/skills"
fi

mkdir -p "$TARGET"
for item in "$SOURCE"/*; do
  [[ "$(basename "$item")" == "README.md" ]] && continue
  cp -R "$item" "$TARGET/"
done

echo "Installed $(find "$SOURCE" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ') skills to $TARGET"
echo "Tool: $TOOL | Restart the IDE or start a new agent session if skills do not appear immediately."
