#!/usr/bin/env python3
"""Print the comments touched by added lines in a git diff, one block per comment.

By default everything not in HEAD is reviewed at once: staged, unstaged and untracked alike, so a
partly staged tree cannot hide half of it. Pass a revision range (e.g. main..HEAD) for a branch.

Paths come out of git, so the whole repository is reviewed wherever the script is run from.
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

PY_SUFFIXES = {".py", ".pyi"}
JS_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
HASH_SUFFIXES = {
    ".yaml", ".yml", ".tf", ".tfvars", ".hcl", ".conf", ".cfg", ".ini",
    ".toml", ".properties", ".tpl", ".sh", ".bash", ".zsh",
}
# HCL also takes // and /* */.
SLASH_SUFFIXES = {".tf", ".tfvars", ".hcl"}
DOCKERFILE_PREFIX = "Dockerfile"

REGEX_FORBIDDEN_BEFORE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_)]}\"'`")


@dataclass
class Comment:
    start: int
    end: int
    text: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("range", nargs="?", help="git revision range, e.g. main..HEAD")
    args = parser.parse_args()

    chdir_to_repo_root()
    diff_args, content_rev = resolve_range(args.range)
    added = collect_added_lines(diff_args)
    if not args.range:
        added |= collect_untracked_lines()

    if not added:
        print("No added lines in range.")
        return 0

    reviewed, skipped = 0, []
    for path, lines in sorted(added.items()):
        suffix = Path(path).suffix
        if not (suffix in PY_SUFFIXES or suffix in JS_SUFFIXES or takes_hash_comments(path)):
            skipped.append(path)
            continue

        source = read_source(path, content_rev)
        if source is None:
            skipped.append(f"{path} (unreadable)")
            continue

        if suffix in PY_SUFFIXES:
            comments = find_py_comments(source)
        elif suffix in JS_SUFFIXES:
            comments = find_js_comments(source)
        else:
            comments = find_hash_comments(source, slash=suffix in SLASH_SUFFIXES)
        touched = [c for c in comments if any(c.start <= n <= c.end for n in lines)]
        if not touched:
            continue

        reviewed += len(touched)
        print(f"\n=== {path} ===")
        for c in touched:
            span = f"{c.start}" if c.start == c.end else f"{c.start}-{c.end}"
            print(f"\n--- {path}:{span} ({c.end - c.start + 1} line(s)) ---")
            print(c.text.rstrip())

    print(f"\n{reviewed} comment block(s) touched by added lines.")
    if skipped:
        print(f"Not scanned (unsupported or unreadable): {', '.join(skipped)}")

    return 0


def chdir_to_repo_root() -> None:
    """Git reports paths from the root, so reading them back has to happen from there."""
    os.chdir(run(["git", "rev-parse", "--show-toplevel"]).strip())


def resolve_range(rev_range: str | None) -> tuple[list[str], str | None]:
    """Return the git diff arguments and the revision whose file content to scan."""
    if rev_range:
        end = rev_range.rsplit("..", 1)[-1] or "HEAD"
        return [rev_range], end

    return ["HEAD"], None


def collect_untracked_lines() -> dict[str, set[int]]:
    """A new file is added in full, and `git diff HEAD` does not mention it."""
    paths = run(["git", "ls-files", "--others", "--exclude-standard"]).split()

    added: dict[str, set[int]] = {}
    for path in paths:
        try:
            line_count = len(Path(path).read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeDecodeError):
            continue

        added[path] = set(range(1, line_count + 1))

    return added


def collect_added_lines(diff_args: list[str]) -> dict[str, set[int]]:
    """Map each changed file to the new-file line numbers the diff adds."""
    diff = run(["git", "diff", "--unified=0", "--no-color", *diff_args])

    added: dict[str, set[int]] = {}
    path, new_line = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            path = None if target == "/dev/null" else target[2:] if target.startswith("b/") else target

        elif line.startswith("@@"):
            new_line = parse_hunk_start(line)

        elif line.startswith("+") and path:
            added.setdefault(path, set()).add(new_line)
            new_line += 1

    return added


def parse_hunk_start(header: str) -> int:
    plus = header.split("+", 1)[1]
    return int(plus.split(",", 1)[0].split(" ", 1)[0])


def read_source(path: str, rev: str | None) -> str | None:
    if rev:
        try:
            return run(["git", "show", f"{rev}:{path}"])
        except subprocess.CalledProcessError:
            return None

    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def find_py_comments(source: str) -> list[Comment]:
    """Collect # comments via tokenize and docstrings via ast, so strings never match."""
    comments: list[Comment] = []

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        tokens = []

    run_start, run_end, run_lines = None, None, []
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue

        line = token.start[0]
        if run_end is not None and line == run_end + 1 and is_own_line(source, token):
            run_end, _ = line, run_lines.append(token.string.strip())
        else:
            if run_start is not None:
                comments.append(Comment(run_start, run_end, "\n".join(run_lines)))
            run_start, run_end, run_lines = line, line, [token.string.strip()]

    if run_start is not None:
        comments.append(Comment(run_start, run_end, "\n".join(run_lines)))

    comments.extend(find_py_docstrings(source))

    return sorted(comments, key=lambda c: c.start)


def is_own_line(source: str, token: tokenize.TokenInfo) -> bool:
    """True when the comment is alone on its line, so trailing comments stay separate blocks."""
    return not source.splitlines()[token.start[0] - 1][: token.start[1]].strip()


def find_py_docstrings(source: str) -> list[Comment]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            end = node.end_lineno or node.lineno
            text = "\n".join(source.splitlines()[node.lineno - 1 : end])
            found.append(Comment(node.lineno, end, text))

    return found


def find_js_comments(source: str) -> list[Comment]:
    """Scan JS/TS character by character so strings, templates and regexes never match."""
    comments: list[Comment] = []
    i, line, prev = 0, 1, ""
    brace_stack: list[int] = []
    n = len(source)

    while i < n:
        c = source[i]
        nxt = source[i + 1] if i + 1 < n else ""

        if c == "/" and nxt == "/":
            end = source.find("\n", i)
            end = n if end == -1 else end
            comments.append(Comment(line, line, source[i:end].strip()))
            i = end
            continue

        if c == "/" and nxt == "*":
            close = source.find("*/", i + 2)
            close = n if close == -1 else close + 2
            text = source[i:close]
            comments.append(Comment(line, line + text.count("\n"), text))
            line += text.count("\n")
            i = close
            continue

        if c in "\"'":
            i, line = skip_quoted(source, i, line, c)
            prev = c
            continue

        if c == "`":
            i, line, template_comments = skip_template(source, i, line)
            comments.extend(template_comments)
            prev = c
            continue

        if c == "/" and prev not in REGEX_FORBIDDEN_BEFORE:
            i, line = skip_regex(source, i, line)
            prev = "/"
            continue

        if c == "\n":
            line += 1
        elif not c.isspace():
            prev = c

        i += 1

    return sorted(comments, key=lambda c: c.start)


def skip_quoted(source: str, i: int, line: int, quote: str) -> tuple[int, int]:
    i += 1
    while i < len(source):
        c = source[i]
        if c == "\\":
            i += 2
            continue

        if c == quote:
            return i + 1, line

        if c == "\n":
            line += 1

        i += 1

    return i, line


def skip_template(source: str, i: int, line: int) -> tuple[int, int, list[Comment]]:
    """Skip a template literal, scanning each ${...} hole for comments."""
    comments: list[Comment] = []
    i += 1
    while i < len(source):
        c = source[i]
        if c == "\\":
            i += 2
            continue

        if c == "`":
            return i + 1, line, comments

        if c == "$" and source[i + 1 : i + 2] == "{":
            hole, i, line = extract_hole(source, i + 2, line)
            for c2 in find_js_comments(hole):
                comments.append(Comment(line - hole.count("\n") + c2.start - 1, line - hole.count("\n") + c2.end - 1, c2.text))
            continue

        if c == "\n":
            line += 1

        i += 1

    return i, line, comments


def extract_hole(source: str, i: int, line: int) -> tuple[str, int, int]:
    start, depth = i, 1
    while i < len(source) and depth:
        c = source[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if not depth:
                break
        elif c == "\n":
            line += 1

        i += 1

    return source[start:i], i + 1, line


def skip_regex(source: str, i: int, line: int) -> tuple[int, int]:
    i += 1
    in_class = False
    while i < len(source):
        c = source[i]
        if c == "\\":
            i += 2
            continue

        if c == "\n":
            return i, line

        if c == "[":
            in_class = True
        elif c == "]":
            in_class = False
        elif c == "/" and not in_class:
            return i + 1, line

        i += 1

    return i, line


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout



def takes_hash_comments(path: str) -> bool:
    name = Path(path).name
    return Path(path).suffix in HASH_SUFFIXES or name.startswith(DOCKERFILE_PREFIX)


def find_hash_comments(source: str, slash: bool = False) -> list[Comment]:
    """Collect # comments (plus // and /* */ for HCL), skipping strings and heredoc bodies."""
    comments: list[Comment] = []
    heredoc: str | None = None
    block_start: int | None = None
    block_lines: list[str] = []
    run_start: int | None = None
    run_end = 0
    run_lines: list[str] = []

    def flush() -> None:
        nonlocal run_start, run_lines
        if run_start is not None:
            comments.append(Comment(run_start, run_end, "\n".join(run_lines)))
        run_start, run_lines = None, []

    for lineno, line in enumerate(source.splitlines(), start=1):
        if heredoc is not None:
            heredoc = None if line.strip() == heredoc else heredoc
            flush()
            continue

        if block_start is not None:
            block_lines.append(line.rstrip())
            if "*/" in line:
                comments.append(Comment(block_start, lineno, "\n".join(block_lines)))
                block_start, block_lines = None, []
            continue

        col, block_col, opened = scan_line(line, slash)
        if block_col is not None:
            flush()
            block_start, block_lines = lineno, [line[block_col:].rstrip()]
            continue

        if col is None:
            heredoc = opened
            flush()
            continue

        text = line[col:].strip()
        own_line = not line[:col].strip()
        if run_start is not None and own_line and lineno == run_end + 1:
            run_end, _ = lineno, run_lines.append(text)
        else:
            flush()
            run_start, run_end, run_lines = lineno, lineno, [text]
            if not own_line:
                flush()

    flush()

    return sorted(comments, key=lambda c: c.start)


def scan_line(line: str, slash: bool) -> tuple[int | None, int | None, str | None]:
    """Return (line-comment column, unterminated /* column, heredoc terminator) for one line."""
    for ignore_quotes in (False, True):
        i, quote = 0, None
        while i < len(line):
            ch = line[i]
            if quote:
                if quote == '"' and ch == "\\":
                    i += 2
                    continue

                quote = None if ch == quote else quote
                i += 1
                continue

            if ch in "\"'" and not ignore_quotes:
                quote = ch
            elif ch == "#" and (i == 0 or line[i - 1].isspace()):
                return i, None, None
            elif slash and line.startswith("//", i):
                return i, None, None
            elif slash and line.startswith("/*", i):
                end = line.find("*/", i + 2)
                if end == -1:
                    return None, i, None

                i = end + 1
            elif slash and line.startswith("<<", i):
                terminator = heredoc_terminator(line[i + 2 :])
                if terminator:
                    return None, None, terminator

            i += 1

        # An unterminated quote is usually an apostrophe in a plain scalar, not a
        # string; rescanning without quoting is better than missing the comment.
        if quote is None:
            break

    return None, None, None


def heredoc_terminator(rest: str) -> str:
    rest = rest[1:] if rest.startswith("-") else rest
    ident = ""
    for ch in rest:
        if ch.isalnum() or ch == "_":
            ident += ch
        else:
            break

    return ident

if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as err:
        print(f"git failed: {' '.join(err.cmd)}\n{err.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
