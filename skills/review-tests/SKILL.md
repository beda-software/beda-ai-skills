---
name: review-tests
description: >-
  Review the tests a diff adds or changes: list every added or changed test, name the one behaviour each pins, and give each a verdict (keep, merge into a parametrized test, fold into an existing test, or drop) with the test or rule that justifies a cut. Catches tests that re-test a lower-level unit, guard a deletion that wasn't a fix, pin a branch only test data reaches, or can't fail when the code they target breaks. Use before committing a diff that adds or changes tests, when a diff's test lines are more than about twice its code lines, and when asked to review, trim or shorten tests.
user_invocable: true
---

# Review tests

## The rules

A test earns its place by pinning one behaviour of the change that no other test pins, and by failing when the code it
targets breaks. Fewer, sharper tests beat a test per branch: every test is code to read, keep green and run in CI.

Start from the **delete test**: if this test were gone, which behaviour could regress unnoticed? No answer — it goes.

| Verdict | When |
|---|---|
| `keep` | It pins a behaviour of the change that nothing else pins: the main path, an error or validation path, an access check, a data migration, a bug fix, or a rule a reviewer or the user asked for. |
| `merge` | Several tests share the setup and differ only in input and expected value: one `parametrize` (or `it.each`) test, with case ids that read as the old test names. |
| `fold` | It adds one assertion to a setup an existing test already builds: move the assertion into that test. |
| `drop` | One of the rules below matches. |

Drop a test when it:

- **re-tests a lower layer**: the path is a helper's own branch (a timeout, a `None` result) already pinned by that
  helper's unit test, re-run through the database or the HTTP stack, and the caller adds no handling of its own;
- **guards a deletion**: code removed on purpose has no test to keep it removed — unless the removal is the fix (a
  leaked field, an open endpoint, a bug);
- **pins a branch only test data reaches**: input no production writer can produce, and the schema or validation rules
  it out. In FHIR stores other clients, imports and old data write the same resources, so "our code always sets it" is
  not enough. Propose deleting the dead branch too;
- **can't fail**: it still passes when the code it targets is broken, or it asserts what its own setup wrote;
- **restates a constant**, or a value the code never touches — not a mapping test, where carrying the field across is
  the feature;
- **repeats a filter of the same kind** as one already tested (a second `_lastUpdated` age bound): merge it into that
  test's cases, or drop it, unless the filter is the point of the change.

Keep, even when it looks redundant:

- one integration test per feature, through the real stack (database, endpoint), next to the unit tests of its pure
  helpers;
- a test that pins a bug a review or QA found;
- an assertion that the change's main output contains the new thing (a prompt list, a response field), when the bug was
  that it didn't.

When a keep rule and a drop rule both match, keep wins.

Setup used by one test only is part of that test's cost: inline it, unless it cleans up after itself, or drop it with
the test. A factory or helper parameter only a dropped test used goes too.

Sanity check, not a rule: when a diff's test lines are more than about twice its code lines (snapshots and fixture data
files left out), look for `merge` and `drop` candidates first.

## The procedure

### 1. List the tests

From the repository root, over the range under review (`<base>...HEAD`; with no range, `HEAD`, which covers staged and
unstaged changes, plus the untracked files the second command lists):

```bash
TEST_PATHS=(':(glob)**/test_*.py' ':(glob)**/*_test.py' ':(glob)**/conftest.py'
            ':(glob)**/tests/**' ':(glob)**/__tests__/**' ':(glob)**/*.test.*' ':(glob)**/*.spec.*')
git diff <range> --stat -- "${TEST_PATHS[@]}"
git ls-files --others --exclude-standard -- "${TEST_PATHS[@]}"
git diff <range> -U0 -- "${TEST_PATHS[@]}" \
  | grep -E '^\+.*(def test_|class Test|@pytest\.mark\.parametrize|\b(it|test|describe)(\.[a-z]+)?\()'
```

The grep finds only tests whose first line was added. Read the whole diff of every listed file too: a test whose body
alone changed, or a new `parametrize` / `it.each` case, has no added name line. Read each test with the code it calls.

### 2. Judge every test

One line each: `path:line`, the behaviour it pins in a few words, the verdict, and the reason — for `merge` and `fold`
the target test, for `drop` the test that still covers it or the drop rule that needs none. A drop with neither is not
a drop; keep it.

Never cut a behaviour the user or a reviewer asked to have tested, even if a drop rule matches; say so in the report.

### 3. Report and apply

Report the table, then the totals: tests before and after, test lines saved per file.

Apply `merge` and `fold`, and `drop` for tests the diff added. A `drop` of a test that existed before the diff is a
proposal: list it, don't delete it. When the caller asked for a report only, apply nothing.

After applying, remove the helpers, factory parameters and imports the cuts leave unused, and run the affected test
modules once in non-watch mode (`--watchAll=false` for Jest). If a run fails, undo the verdict that broke it and keep
that test.
