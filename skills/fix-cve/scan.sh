#!/usr/bin/env bash
# Usage: scan.sh <new-workdir> [owner/repo[:Dockerfile[,dir/Dockerfile]] ...]     (no repos: every line of repos.txt)

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="${1:?Usage: scan.sh <new-workdir> [owner/repo[:Dockerfile[,dir/Dockerfile]] ...]}"
shift
TRIVY_IMAGE="aquasec/trivy:0.75.0"
TRIVY_CACHE_VOLUME="fix-cve-trivy-cache"
PLATFORM="linux/amd64"
SEVERITY="HIGH,CRITICAL"

main() {
  if [[ -e "$WORKDIR" ]]; then
    echo "$WORKDIR already exists: pass a new directory" >&2
    exit 1
  fi

  if [[ $# -eq 0 ]]; then
    # shellcheck disable=SC2046
    set -- $(grep -v -e '^#' -e '^$' "$SKILL_DIR/repos.txt")
  fi
  mkdir -p "$WORKDIR/reports"
  download_trivy_databases
  for target in "$@"; do
    scan_repo "$target" &
  done
  wait
  summarize_reports | tee "$WORKDIR/findings.tsv"
}

# Parallel scans then only read the shared databases and keep their layer cache in memory, so they never lock it.
download_trivy_databases() {
  docker run --rm \
    -v "$TRIVY_CACHE_VOLUME:/root/.cache" \
    "$TRIVY_IMAGE" \
    image --quiet --download-db-only
  docker run --rm \
    -v "$TRIVY_CACHE_VOLUME:/root/.cache" \
    "$TRIVY_IMAGE" \
    image --quiet --download-java-db-only
}

scan_repo() {
  local target="$1"
  local repo="${target%%:*}"
  local dockerfiles=""
  if [[ "$target" == *:* ]]; then
    dockerfiles="${target#*:}"
  fi
  local name="${repo#*/}"
  local checkout="$WORKDIR/$name"
  echo "== $repo" >&2
  if ! gh repo clone "$repo" "$checkout" -- --depth 1 --quiet; then
    echo "!! $name: clone failed, not scanned" >&2
    return
  fi

  run_trivy "$checkout:/src:ro" fs /src > "$WORKDIR/reports/$name.fs.json" \
    || echo "!! $name: source scan failed" >&2
  for dockerfile in ${dockerfiles//,/ }; do
    scan_image "$name" "$checkout/$dockerfile" "$(get_image_scan_label "$dockerfile")"
  done
}

# The label goes into the report name after the last dot, so it must not contain one.
get_image_scan_label() {
  local dockerfile="$1"
  if [[ "$dockerfile" == "Dockerfile" ]]; then
    echo "image"
    return
  fi

  local label="${dockerfile//\//-}"
  echo "image-${label//./-}"
}

scan_image() {
  local name="$1"
  local dockerfile="$2"
  local label="$3"
  local image="fix-cve/$name:$label"
  if ! docker build --quiet --pull --platform "$PLATFORM" --file "$dockerfile" --tag "$image" "$(dirname "$dockerfile")" > /dev/null; then
    image="$(find_final_base_image "$dockerfile")"
    if [[ -z "$image" ]]; then
      echo "!! $name: docker build failed, image not scanned" >&2
      return
    fi

    echo "!! $name: docker build failed, scanning its base image $image instead" >&2
  fi

  run_trivy /var/run/docker.sock:/var/run/docker.sock image --platform "$PLATFORM" "$image" \
    > "$WORKDIR/reports/$name.$label.json" \
    || echo "!! $name: image scan failed" >&2
}

# Prints nothing when the last stage starts from an earlier stage or a build argument.
find_final_base_image() {
  local dockerfile="$1"
  local from_line
  local base=""
  from_line="$(grep -i '^FROM ' "$dockerfile" | tail -1)"
  for word in ${from_line#* }; do
    if [[ "$word" != --* ]]; then
      base="$word"
      break
    fi
  done
  if [[ -z "$base" || "$base" == *'$'* ]] || grep -q -i -E "^FROM .* AS $base\$" "$dockerfile"; then
    return
  fi

  echo "$base"
}

run_trivy() {
  local mount="$1"
  shift
  docker run --rm \
    -v "$mount" \
    -v "$TRIVY_CACHE_VOLUME:/root/.cache" \
    "$TRIVY_IMAGE" \
    "$@" \
    --quiet \
    --skip-db-update \
    --skip-java-db-update \
    --cache-backend memory \
    --timeout 15m \
    --scanners vuln \
    --severity "$SEVERITY" \
    --ignore-unfixed \
    --format json
}

summarize_reports() {
  printf 'repo\tscan\ttarget\tpackage\tinstalled\tfixed\tseverity\tid\n'
  for report in "$WORKDIR"/reports/*.json; do
    local base
    base="$(basename "$report" .json)"
    jq -r \
      --arg repo "${base%.*}" \
      --arg scan "${base##*.}" \
      '.Results[]? | .Target as $target | .Vulnerabilities[]?
        | [$repo, $scan, $target, .PkgName, .InstalledVersion, .FixedVersion, .Severity, .VulnerabilityID]
        | @tsv' \
      "$report" \
      || echo "!! $base: unreadable report" >&2
  done
}

main "$@"
