#!/usr/bin/env bash
# Install beda-ai-skills into Cursor or Claude Code.
#
# Usage (run from anywhere after cloning this repo once):
#   git clone git@gitlab.beda.software:emr/beda-ai-skills.git ~/beda-ai-skills
#   ~/beda-ai-skills/install.sh --global                     # → ~/.cursor/skills (recommended)
#   ~/beda-ai-skills/install.sh --claude --global            # → ~/.claude/skills
#   ~/beda-ai-skills/install.sh ~/work/fhir-emr              # → project/.cursor/skills (optional)
#   ~/beda-ai-skills/install.sh --claude ~/work/fhir-emr     # → project/.claude/skills
#   ~/beda-ai-skills/install.sh --target /path/to/skills

set -euo pipefail

REPO_URL="${BEDA_AI_SKILLS_REPO:-git@gitlab.beda.software:emr/beda-ai-skills.git}"
REF="${BEDA_AI_SKILLS_REF:-main}"
TOOL="cursor"
SCOPE="project"
PROJECT=""
TARGET=""
TMPDIR=""

usage() {
  sed -n '2,11p' "$0" | tail -n +2
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cursor) TOOL="cursor"; shift ;;
    --claude) TOOL="claude"; shift ;;
    --global) SCOPE="global"; shift ;;
    --project)
      PROJECT="${2:?--project requires a path}"
      shift 2
      ;;
    --target)
      TARGET="${2:?--target requires a path}"
      shift 2
      ;;
    -h|--help) usage 0 ;;
    -*)
      echo "Unknown option: $1" >&2
      usage 1
      ;;
    *)
      if [[ -n "$PROJECT" ]]; then
        echo "Only one project path allowed (got '$PROJECT' and '$1')" >&2
        usage 1
      fi
      PROJECT="$1"
      shift
      ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  if [[ "$SCOPE" == "global" ]]; then
    if [[ -n "$PROJECT" ]]; then
      echo "Do not pass a project path together with --global" >&2
      usage 1
    fi
    if [[ "$TOOL" == "claude" ]]; then
      TARGET="$HOME/.claude/skills"
    else
      TARGET="$HOME/.cursor/skills"
    fi
  else
    if [[ -z "$PROJECT" ]]; then
      echo "Pass a project path, or use --global." >&2
      echo "Example: $0 ~/work/fhir-emr" >&2
      usage 1
    fi
    if [[ ! -d "$PROJECT" ]]; then
      echo "Project directory not found: $PROJECT" >&2
      exit 1
    fi
    PROJECT="$(cd "$PROJECT" && pwd)"
    if [[ "$TOOL" == "claude" ]]; then
      TARGET="$PROJECT/.claude/skills"
    else
      TARGET="$PROJECT/.cursor/skills"
    fi
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
