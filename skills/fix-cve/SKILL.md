---
name: fix-cve
description: >-
  Scan the default branch of one repo, or of every Beda open-source package in repos.txt, with dockerized Trivy, list
  the fixable HIGH/CRITICAL findings, fix each repo in a parallel subagent with the smallest non-major dependency bump,
  open one PR per repo, wait for CI and report a table of package, vulnerable version, fix and PR link. For the
  open-source packages it also bumps the patch version and, via `/fix-cve release`, tags and releases the merged fixes.
  Runs only on /fix-cve.
user_invocable: true
disable-model-invocation: true
---

# Fix CVE

Runs only when called as `/fix-cve`. The argument picks the target:

| Call | Target | Version bump and release |
|---|---|---|
| `/fix-cve` | none: do nothing, ask which target — the open-source packages or one repo (`owner/repo`) | — |
| `/fix-cve oss` | every repo in [repos.txt](repos.txt) (`/fix-cve oss fhir-sdc jute-microservice` limits it to those) | yes |
| `/fix-cve <owner/repo>` | that one repo, e.g. an application | no: only the fix commit, no tags or releases |
| `/fix-cve release` | the second phase, [Release](#7-release), after the maintainer merged the open-source PRs | — |

Needs `docker`, `jq` and an authenticated `gh` with push rights to the target repos.

**Never run tests, builds or installs locally**, in the main agent or a subagent: they need far more resources than a
dependency bump is worth. Each PR's CI runs them (step 5).

## 1. Scan

Make a fresh empty work directory and scan the default branch (`main` or `master`) of the target repos. With no repo
arguments the script scans every line of repos.txt:

```bash
<skill-dir>/scan.sh <workdir> [owner/repo[:Dockerfile] ...]
```

The `:Dockerfile` suffix names the Dockerfiles of the images the repo publishes, comma-separated
(`owner/repo:Dockerfile,app/Dockerfile`); each is built with its own directory as the build context. Without it only
the source tree is scanned. For a single-repo target, check the repo's publish workflow and pass the Dockerfile it builds — never a
development Dockerfile that installs and builds the whole app.

The script clones each repo into `<workdir>/<repo>`, runs Trivy on the source tree, and when a Dockerfile is named
builds the image for `linux/amd64` with a freshly pulled base and scans that too (the base image's OS
packages only show up there). When the build fails (a Dockerfile that expects CI artifacts) it scans the final stage's
base image instead. It prints one TSV line per fixable finding and keeps them in `<workdir>/findings.tsv`; raw reports
are in `<workdir>/reports/`. Lines starting with `!!` name what could not be scanned: list them in the report.

Show the findings grouped by repo and package: installed version, fixed versions, severity, IDs.

## 2. Plan the fixes

For each repo and package pick the **lowest fixed version with the same major** as the installed one (Trivy's
`fixed` column may list several lines, e.g. `21.14.7, 21.14.9`). Never take a major update: a package whose only fix
is a new major is left out and reported as `major only`. Below 1.0 the minor is the major (`0.2.2` → `0.5.1` is
`major only`).

How to apply it, by where the package comes from:

| Source | Change |
|---|---|
| Direct dependency whose range already allows the fix | Lockfile only |
| Direct dependency whose range excludes the fix | Raise the lower bound in the manifest to the fixed version, then lock |
| Transitive dependency | Lockfile only (`poetry update --lock <pkg>`, `uv lock --upgrade-package <pkg>`, `pipenv upgrade <pkg>==<ver>`, `npm update <pkg> --package-lock-only`, `yarn up -R <pkg> --mode=update-lockfile`); when the parent's range blocks it, an `overrides` / `resolutions` entry for that one package |
| Clojure / Java (`deps.edn`) | Add or raise the explicit coordinate to the fixed version |
| OS package from a pinned base image tag | Bump the tag to the newest patch of the same line (`alpine:3.24.2` → `3.24.3`, not a new distro release) |
| OS package from a floating base tag (`python:3.12-slim`) | No source change: a fresh build already picks up the fixed base. Open-source target: a release republishes the image (a `Bump to` PR first when the repo has a version file). Single repo: reported as `rebuild only` |

The scan builds with `--pull`, so an OS finding that survives it on a floating tag is not fixed upstream yet: report it
as `no upstream fix`.

In libraries (fhir-py, fhirpath-py, aidbox-python-sdk, sdc-qrf, fhir-questionnaire) change only lockfiles; keep the
published dependency ranges unless the range itself excludes the fix.

Show the plan as one table (repo, package, installed → target, change), then start fixing without waiting.

## 3. Fix in parallel

Spawn one subagent per repo that has at least one planned change, all in one message, in the background. Give each:

- the checkout path `<workdir>/<repo>` and its planned rows;
- the rules from step 2: same major only, nothing beyond the listed packages, no refactors, no unrelated lockfile
  churn (if the lock tool rewrites unrelated entries, retry with its single-package mode);
- run the repo's lock tool through `uvx` / `npx` / `docker` when it is not installed, in lock-only mode
  (`poetry lock`, `npm install --package-lock-only`); never run tests, builds or a full install: CI checks the PR;
- open-source target only, and only when the package's source holds the version its tags follow (`__version__` in
  `__init__.py`, which `pyproject.toml` may read as a dynamic version; `version` in an npm package's
  `package.json`): bump its patch there and wherever else that same version is written (grep it). A pre-release bumps
  its counter instead (`1.1.0-alpha.15` → `1.1.0-alpha.16`). No bump when the version comes from tags
  (setuptools-scm) or release automation (semantic-release, release-please), and none for a placeholder version the
  tags don't follow (`0.0.0`, or `1.0.0` with no matching tag);
- with a bump, and when the repo keeps a `CHANGELOG.md`, add an entry for the new version in its existing format
  listing the fixed packages;
- create branch `fix-cve-<YYYY-MM-DD>` (`-2`, `-3`… when that branch already exists on the remote) with two commits, subject lines below: first the dependency fixes, then the
  version bump with the changelog entry; do not push;
- reply with each package's old and new version, the old and new package version, or why a row could not be applied.

Commit messages are the subject line only, with no body, issue reference or co-author trailer:

```
Fix CVE findings in <package>, <package>
Bump to <new version>
```

A repo that uses conventional commits (`fix:`, `chore(release):` in its log) gets `fix: CVE findings in <package>,
<package>` instead, and no bump commit: its release automation turns the `fix:` commit into a patch release.

A single-repo target, and an open-source repo without a version file, gets only the first commit. An open-source
repo with a version file whose findings are all OS packages on a floating base tag gets only the second; its PR title
is then `Bump to <new version>`.

## 4. Push and open PRs

From the main agent, one repo at a time: push the branch, then open one PR with both commits against the default
branch. Every PR uses the first commit's subject as its title and this body, with no issue references and no tool or AI attribution:

```markdown
Fixes CVE findings for <owner/repo>:

| Package | Severity | IDs | Version |
|---|---|---|---|
| certifi | CRITICAL | GHSA-6q48-6c7w-9gw2 | 2024.8.30 → 2026.10.19 |
```

## 5. Wait for CI

Watch every PR's checks until they finish: `gh pr checks <url> --watch`. Report nothing to the user while they run.

When a PR's checks fail, read the failed job log (`gh run view <run-id> --log-failed`). If the failure comes from the
bump, give that repo's subagent the log for one fix round (one more `Fix CVE findings in …` commit), push it to the
same branch from the main agent and watch again. A failure that also happens on the default branch is not the bump's: leave it and say so.

A repo with no checks on the PR is reported as `no CI`.

## 6. Report

Only when every PR's checks are finished, give one table:

| Repo | Release | Package | Vulnerable version | Done | PR | CI |
|---|---|---|---|---|---|---|
| fhir-sdc | 2.4.2 → 2.4.3 | certifi | 2026.6.17 | lock → 2026.10.19 | <url> | passed |
| jute-microservice | 0.1.4 → 0.1.5 | musl (alpine 3.24.2) | 1.2.5-r10 | release republishes the image | <url> | passed |

List every finding from step 1: fixed ones with their PR, and `major only`, `rebuild only`, `no upstream fix` or failed
ones with the reason. Merging stays with the maintainer; end by telling them to run `/fix-cve release` once the PRs are
merged, naming any repos without a PR that need a release to republish their image.

## 7. Release

`/fix-cve release`, after the maintainer merged the PRs. It covers the repos in repos.txt with a merged fix-cve PR,
plus any repos named after it (`/fix-cve release jute-microservice`: an image that only needs republishing). Repos
released by automation (semantic-release, release-please) are skipped: merging already released them. Find the PRs
from branches named `fix-cve-*`:

```bash
gh pr list --repo <owner/repo> --state all --search "head:fix-cve-" --json number,url,state,headRefName,mergeCommit
```

Skip repos whose fix-cve PR is still open or closed unmerged, and repos that already have a tag on the merge commit.
For each merged one work out, without cloning:

- previous version: the latest release or tag (`gh release list --repo <owner/repo> --limit 5`,
  `gh api repos/<owner/repo>/tags`);
- new version: the one in the PR's `Bump to <version>` commit; with no such commit, the previous version's patch + 1.

Keep the existing tag style (`v2.4.2` or `2.4.2`). A pre-release line continues as a pre-release
(`v1.1.0-alpha.15` → `v1.1.0-alpha.16`). When the repo has no tags yet, or the new version doesn't follow from the
latest tag, propose a version and mark the row `confirm version`.

Show one table and ask the maintainer to confirm, or correct a version, before creating anything:

| Repo | Previous version | New version | Merge commit | PR |
|---|---|---|---|---|

On confirmation, per repo: create the GitHub release with its tag on the merge commit, titled with the tag, the body
listing the fixed packages as in the PR body:

```bash
gh release create <tag> --repo <owner/repo> --target <merge-commit-sha> --title <tag> --notes-file <notes.md>
```

Then report each release URL and whether the repo's release workflow started (`gh run list --repo <owner/repo>
--limit 3`).
