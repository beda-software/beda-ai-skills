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
import re
import subprocess
import sys
import tokenize
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PY_SUFFIXES = {".py", ".pyi"}
JS_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
RUST_SUFFIXES = {".rs"}
YAML_SUFFIXES = {".yaml", ".yml"}
HURL_SUFFIXES = {".hurl"}
SHELL_SUFFIXES = {".sh", ".bash", ".zsh"}
HASH_SUFFIXES = {".conf", ".cfg", ".ini", ".toml", ".properties", ".tpl"}
# HCL also takes // and /* */.
HCL_SUFFIXES = {".tf", ".tfvars", ".hcl"}
DOCKERFILE_PREFIX = "Dockerfile"
MAKE_NAMES = {"Makefile", "makefile", "GNUmakefile"}

YAML_BLOCK_SCALAR = re.compile(r"(?:^|\s)[|>][1-9+-]{0,2}$")

SHELL_HEREDOC = re.compile(r"(?<!<)<<-?\s*\\?(['\"]?)([A-Za-z_][\w.-]*)\1")
MAKE_COMMENT = re.compile(r"(?<!\\)#")

RUST_RAW_STRING = re.compile(r'r(#*)"')

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
        finder = get_comment_finder(Path(path))
        if finder is None:
            skipped.append(path)
            continue

        source = read_source(path, content_rev)
        if source is None:
            skipped.append(f"{path} (unreadable)")
            continue

        comments = finder(source)
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


def get_comment_finder(path: Path) -> Callable[[str], list[Comment]] | None:
    if path.name in MAKE_NAMES or path.suffix == ".mk":
        return find_make_comments
    suffix = path.suffix
    if suffix in PY_SUFFIXES:
        return find_py_comments
    if suffix in JS_SUFFIXES:
        return find_js_comments
    if suffix in RUST_SUFFIXES:
        return find_rust_comments
    if suffix in YAML_SUFFIXES:
        return find_yaml_comments
    if suffix in HURL_SUFFIXES:
        return find_hurl_comments
    if suffix in SHELL_SUFFIXES:
        return find_shell_comments
    if suffix in HCL_SUFFIXES:
        return lambda source: find_hash_comments(source, slash=True)
    if suffix in HASH_SUFFIXES or path.name.startswith(DOCKERFILE_PREFIX):
        return find_hash_comments
    return None


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


def find_rust_comments(source: str) -> list[Comment]:
    """Scan Rust character by character so strings, raw strings and char literals never match."""
    comments: list[Comment] = []
    i, line, last_own_line = 0, 1, False
    n = len(source)

    while i < n:
        c = source[i]
        nxt = source[i + 1] if i + 1 < n else ""

        if c == "/" and nxt == "/":
            end = source.find("\n", i)
            end = n if end == -1 else end
            text = source[i:end].strip()
            last = comments[-1] if comments else None
            own_line = not source[source.rfind("\n", 0, i) + 1 : i].strip()
            if own_line and last_own_line and last and last.end == line - 1 and last.text.startswith("//"):
                comments[-1] = Comment(last.start, line, f"{last.text}\n{text}")
            else:
                comments.append(Comment(line, line, text))
            last_own_line = own_line
            i = end
            continue

        if c == "/" and nxt == "*":
            close = skip_nested_block_comment(source, i)
            text = source[i:close]
            comments.append(Comment(line, line + text.count("\n"), text))
            line += text.count("\n")
            i = close
            continue

        raw = RUST_RAW_STRING.match(source, i) if c == "r" and starts_rust_literal(source, i) else None
        if raw:
            terminator = '"' + raw.group(1)
            close = source.find(terminator, raw.end())
            close = n if close == -1 else close + len(terminator)
        elif c == '"':
            close, _ = skip_quoted(source, i, line, c)
        elif c == "'":
            close = skip_char_literal(source, i)
        else:
            if c == "\n":
                line += 1
            i += 1
            continue

        line += source.count("\n", i, close)
        i = close

    return sorted(comments, key=lambda c: c.start)


def find_yaml_comments(source: str) -> list[Comment]:
    """Collect # comments outside quoted scalars; consecutive own-line ones form one block."""
    comments: list[Comment] = []
    quote, block_indent, last_own_line = None, None, False
    for line_no, raw in enumerate(source.splitlines(), start=1):
        indent = len(raw) - len(raw.lstrip(" "))
        if block_indent is not None:
            if not raw.strip() or indent > block_indent:
                # A block scalar usually embeds a config or script, whose comments a reviewer still reads.
                _, hash_at, _ = scan_shell_line(raw, None)
                if hash_at is not None:
                    last_own_line = add_hash_comment(comments, line_no, raw, hash_at, last_own_line)
                continue

            block_indent = None

        quote, hash_at = scan_yaml_line(raw, quote)
        if hash_at is None:
            content = raw
        else:
            content = raw[:hash_at]
            last_own_line = add_hash_comment(comments, line_no, raw, hash_at, last_own_line)

        if quote is None and YAML_BLOCK_SCALAR.search(content.rstrip()):
            block_indent = indent

    return comments


def add_hash_comment(comments: list[Comment], line_no: int, raw: str, hash_at: int, last_own_line: bool) -> bool:
    """Append the comment at hash_at, merging it into the previous own-line block; return whether it is own-line."""
    text = raw[hash_at:].rstrip()
    own_line = not raw[:hash_at].strip()
    last = comments[-1] if comments else None
    if own_line and last_own_line and last and last.end == line_no - 1:
        comments[-1] = Comment(last.start, line_no, f"{last.text}\n{text}")
    else:
        comments.append(Comment(line_no, line_no, text))

    return own_line


def find_hurl_comments(source: str) -> list[Comment]:
    """Collect # comments outside quoted strings and ``` bodies; consecutive own-line ones form one block."""
    comments: list[Comment] = []
    in_body, last_own_line = False, False
    for line_no, raw in enumerate(source.splitlines(), start=1):
        start = 0
        if in_body:
            fence = raw.find("```")
            if fence == -1:
                continue
            in_body, start = False, fence + 3

        in_body, hash_at = scan_hurl_line(raw, start)
        if hash_at is not None:
            last_own_line = add_hash_comment(comments, line_no, raw, hash_at, last_own_line)

    return comments


def scan_hurl_line(line: str, i: int) -> tuple[bool, int | None]:
    """Return whether a ``` body is left open at line end and where a comment starts, if any."""
    n = len(line)
    while i < n:
        c = line[i]
        if c == "#" and (i == 0 or line[i - 1] in " \t"):
            return False, i

        if line.startswith("```", i):
            close = line.find("```", i + 3)
            if close == -1:
                return True, None
            i = close + 3
            continue

        if c == '"':
            i, _ = skip_quoted(line, i, 0, c)
            continue

        if c == "`":
            close = line.find("`", i + 1)
            i = n if close == -1 else close + 1
            continue

        i += 1

    return False, None


def scan_yaml_line(line: str, quote: str | None) -> tuple[str | None, int | None]:
    """Return the quote open at line end and where a comment starts; quotes open at token start, unlike `key: it's`."""
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if quote == "'":
            if c == "'":
                if line[i + 1 : i + 2] == "'":
                    i += 1
                else:
                    quote = None
        elif quote == '"':
            if c == "\\":
                i += 1
            elif c == '"':
                quote = None
        elif c == "#" and (i == 0 or line[i - 1] in " \t"):
            return None, i
        elif c in "'\"" and (not line[:i].strip() or line[:i].rstrip()[-1] in ":-[{,?"):
            quote = c
        i += 1

    return quote, None


def find_shell_comments(source: str) -> list[Comment]:
    """Collect # comments outside quotes and heredocs; consecutive own-line ones form one block."""
    comments: list[Comment] = []
    quote, heredoc, last_own_line = None, None, False
    for line_no, raw in enumerate(source.splitlines(), start=1):
        if heredoc:
            if raw.strip() == heredoc:
                heredoc = None
            continue

        if line_no == 1 and raw.startswith("#!"):
            continue

        quote, hash_at, heredoc = scan_shell_line(raw, quote)
        if hash_at is not None:
            last_own_line = add_hash_comment(comments, line_no, raw, hash_at, last_own_line)

    return comments


def scan_shell_line(line: str, quote: str | None) -> tuple[str | None, int | None, str | None]:
    """Return the quote still open at line end, where a comment starts, and the heredoc delimiter it opens, if any."""
    i, n, heredoc = 0, len(line), None
    while i < n:
        c = line[i]
        if quote == "'":
            if c == "'":
                quote = None
        elif quote == '"':
            if c == "\\":
                i += 1
            elif c == '"':
                quote = None
        elif c == "\\":
            i += 1
        elif c == "#" and (i == 0 or line[i - 1] in " \t;&|()"):
            return quote, i, heredoc
        elif c in "'\"":
            quote = c
        elif line.startswith("((", i):
            close = line.find("))", i + 2)
            i = n if close == -1 else close + 2
            continue
        elif match := SHELL_HEREDOC.match(line, i):
            heredoc = heredoc or match.group(2)
            i = match.end()
            continue
        i += 1

    return quote, None, heredoc


def find_make_comments(source: str) -> list[Comment]:
    """Recipe lines go to the shell, so they follow its quoting; elsewhere any unescaped # starts a comment."""
    comments: list[Comment] = []
    last_own_line = False
    for line_no, raw in enumerate(source.splitlines(), start=1):
        if raw.startswith("\t"):
            _, hash_at, _ = scan_shell_line(raw, None)
        else:
            match = MAKE_COMMENT.search(raw)
            hash_at = match.start() if match else None

        if hash_at is not None:
            last_own_line = add_hash_comment(comments, line_no, raw, hash_at, last_own_line)

    return comments


def starts_rust_literal(source: str, i: int) -> bool:
    """True when the r at i opens a raw string (r"", br"", cr"") rather than ending an identifier."""
    if i > 0 and source[i - 1] in "bc":
        i -= 1

    return i == 0 or not (source[i - 1].isalnum() or source[i - 1] == "_")


def skip_nested_block_comment(source: str, i: int) -> int:
    depth = 0
    while i < len(source):
        if source.startswith("/*", i):
            depth, i = depth + 1, i + 2
        elif source.startswith("*/", i):
            depth, i = depth - 1, i + 2
            if not depth:
                return i
        else:
            i += 1

    return i


def skip_char_literal(source: str, i: int) -> int:
    """Skip 'x' or '\\n'; a quote that closes neither is a lifetime or label, so only it is skipped."""
    if source[i + 1 : i + 2] == "\\":
        close = source.find("'", i + 3)
        return len(source) if close == -1 else close + 1

    if source[i + 2 : i + 3] == "'":
        return i + 3

    return i + 1


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
                if line.find("*/", i + 2) == -1:
                    return None, i, None

                return i, None, None
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


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as err:
        print(f"git failed: {' '.join(err.cmd)}\n{err.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
