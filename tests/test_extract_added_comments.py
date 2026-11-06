import importlib.util
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).parents[1] / "skills" / "review-comments" / "extract_added_comments.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("extract_added_comments", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


extractor = load_script()


def test_find_yaml_comments__merges_own_line_runs_and_skips_quoted_hashes() -> None:
    source = """
        # first
        # second
        url: "http://x#fragment"
        quoted: 'it''s # still a string'
        note: it's # trailing after an apostrophe
    """
    assert collect(extractor.find_yaml_comments, source) == [
        (1, 2, "# first\n# second"),
        (5, 5, "# trailing after an apostrophe"),
    ]


def test_find_yaml_comments__reports_comments_embedded_in_a_block_scalar() -> None:
    source = """
        data:
          config.yaml: |
            model_list:
              # embedded config comment
              - model_name: gpt
            command: echo "# not a comment"
        after: 1 # trailing after the block
    """
    assert collect(extractor.find_yaml_comments, source) == [
        (4, 4, "# embedded config comment"),
        (7, 7, "# trailing after the block"),
    ]


def test_find_shell_comments__skips_shebang_parameters_quotes_and_heredocs() -> None:
    source = """
        #!/usr/bin/env bash
        # real comment
        echo "# not" '# not' $# ${#ARR[@]}
        cat <<EOF
        # inside a heredoc
        EOF
        echo done # trailing
    """
    assert collect(extractor.find_shell_comments, source) == [
        (2, 2, "# real comment"),
        (7, 7, "# trailing"),
    ]


def test_find_rust_comments__skips_strings_raw_strings_chars_and_lifetimes() -> None:
    source = """
        // first
        // second
        fn main<'a>(x: &'a str) {
            let s = "// not a comment";
            let r = r#"/* not either */"#;
            let c = '/';
            /* outer /* nested */ still outer */
            let y = 1; // trailing
        }
    """
    assert collect(extractor.find_rust_comments, source) == [
        (1, 2, "// first\n// second"),
        (7, 7, "/* outer /* nested */ still outer */"),
        (8, 8, "// trailing"),
    ]


def test_find_make_comments__skips_escaped_hashes_and_quoted_recipe_text() -> None:
    source = """
        # top comment
        VAR = a\\#b
        target:
        \techo "# not" # recipe trailing
    """
    assert collect(extractor.find_make_comments, source) == [
        (1, 1, "# top comment"),
        (4, 4, "# recipe trailing"),
    ]


def test_find_hurl_comments__skips_url_fragments_and_fenced_bodies() -> None:
    source = """
        # request comment
        GET http://x/#fragment
        ```
        # inside a body
        ```
        HTTP 200 # trailing
    """
    assert collect(extractor.find_hurl_comments, source) == [
        (1, 1, "# request comment"),
        (6, 6, "# trailing"),
    ]


def test_find_hash_comments__reads_hcl_slash_and_inline_block_comments() -> None:
    source = """
        a = 1 /* inline block */
        # hash comment
        // slash comment
    """
    found = collect(lambda text: extractor.find_hash_comments(text, slash=True), source)
    assert found == [
        (1, 1, "/* inline block */"),
        (2, 3, "# hash comment\n// slash comment"),
    ]


def test_find_py_comments__collects_comments_and_docstrings_but_not_strings() -> None:
    source = '''
        """Module docstring."""

        # py comment
        x = "# not"
    '''
    assert collect(extractor.find_py_comments, source) == [
        (1, 1, '"""Module docstring."""'),
        (3, 3, "# py comment"),
    ]


def test_find_js_comments__skips_strings_templates_and_regexes() -> None:
    source = """
        // js comment
        const s = "// not";
        const r = /\\/\\/ not/;
        const t = `${a /* in a hole */}`;
    """
    assert collect(extractor.find_js_comments, source) == [
        (1, 1, "// js comment"),
        (4, 4, "/* in a hole */"),
    ]


@pytest.mark.parametrize(
    ("name", "finder"),
    [
        ("config.yml", "find_yaml_comments"),
        ("run.sh", "find_shell_comments"),
        ("lib.rs", "find_rust_comments"),
        ("Makefile", "find_make_comments"),
        ("rules.mk", "find_make_comments"),
        ("api.hurl", "find_hurl_comments"),
        ("app.py", "find_py_comments"),
        ("app.tsx", "find_js_comments"),
        ("settings.toml", "find_hash_comments"),
        ("Dockerfile.dev", "find_hash_comments"),
    ],
)
def test_comment_finder__picks_the_finder_by_file_name(name: str, finder: str) -> None:
    assert extractor.comment_finder(Path(name)) is getattr(extractor, finder)


def test_comment_finder__returns_none_for_an_unsupported_file() -> None:
    assert extractor.comment_finder(Path("notes.md")) is None


def collect(finder: Callable[[str], list[Any]], source: str) -> list[tuple[int, int, str]]:
    text = textwrap.dedent(source).lstrip("\n")
    return [(c.start, c.end, c.text.strip()) for c in finder(text)]
