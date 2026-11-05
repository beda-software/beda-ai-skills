---
name: review-comments
description: >-
  Review the comments a diff adds: a script extracts every added comment, then each is judged against the comment rules (earns its place only if non-obvious to a reader of the code, three lines at most, clearer naming preferred over prose, still true of the code). Use before every commit, and when asked to review or clean up comments in changed code. Pass `manual` to have every block put to the user one at a time after the automatic pass.
user_invocable: true
---

# Review comments

## The rules

The best code is code that needs no comments: it explains itself. The next best is code you never write.

Code must read on its own. Reach for a better name, a smaller function, or a clearer structure before reaching for a comment — a comment that explains what the code does is a sign the code is wrong, not that a comment was missing.

Comment only what genuinely cannot be read off the code: a hidden constraint, an external quirk, a decision whose alternative looks equally valid. Never restate the line below, never explain the obvious. Be concise — no one reads long comments. Docstrings for functions are good but keep them short.

Put a comment on its own line above the statement it explains, as a full sentence — never trailing the line (`continue  # a legacy row`). An early `return`/`continue` that needs a reason gets the reason on the line above it.

A comment describes the **code**. A fact about the **data** — how many seeds matched a survey, which codes a series uses, what a one-off measurement showed — never goes in a comment, however expensive it was to discover; it belongs in `docs/` or the commit message. The implementation is general and the data changes independently of it, so such a comment is stale on the next data edit. History is out for the same reason: no "now", no "used to be", no account of what changed.

Beware the trap that makes this rule fail: a fact that took a long investigation to derive *feels* non-obvious, so the "comment the non-obvious" rule fires on it. The test is what is non-obvious **to a reader of this code**, not to whoever just derived it. Before keeping a comment, ask: if I delete this line, what wrong action does a reader take? No answer — delete it. A docstring is one line by default; a second line only earns its place by answering "why not the obvious alternative".

In a repo that isn't the current project itself — a shared library, an open-source dependency, anything with other consumers — keep comments about the code's own mechanism, not about why one particular downstream project needed it. Same rule as for commit messages: leave out org/deployment-specific context that only makes sense to one consumer.

A comment must stand on its own for every future reader, so never point it at something that reader might not have: an untracked file (absent from anyone else's checkout), an ADR, or a GitHub issue (may be private, deleted, or just not cloned alongside the code). If the reasoning matters, state it inline; a pointer to a place some readers can't reach isn't a substitute.

## The procedure

Applying the rules above to a diff, step by step, so that no added comment goes unjudged.

**Modes.** By default the pass is automatic: judge every block and apply the verdicts. When the invocation
carries `manual`, the automatic pass still runs first — then every block goes to the user one at a time for
their verdict (step 4). Never enter manual mode unasked; never skip the automatic pass because manual was
asked for.

### 1. Extract

The script sits next to this `SKILL.md`; `<skill-dir>` is the folder this skill was loaded from.

```bash
python3 <skill-dir>/extract_added_comments.py            # everything not in HEAD
python3 <skill-dir>/extract_added_comments.py main..HEAD # a whole branch
```

The default covers staged, unstaged and untracked files together, and paths are resolved from the repository
root, so neither a partly staged tree nor the directory you run from can hide half the review.

The script scans the post-change file content and reports only comment blocks that added lines touch, so
pre-existing comments stay out of the review. It counts each block's lines for you. Files it cannot scan are
named in a trailing line — read that line, and review those comments by hand.

Run it again after editing comments in response to a review: a block written after the last run was never
judged.

### 2. Judge every block

Each block gets exactly one verdict. Start from the **delete test**: if this comment were gone, what wrong
action does a reader take? No answer — `delete`.

| Verdict | When |
|---|---|
| `keep` | Answers the delete test: a hidden constraint, an external quirk, a decision whose alternative looks equally valid. |
| `shorten` | The point is real and fits in fewer lines. Bound: 1–2 lines, 3 at the absolute limit; a docstring is one line unless a second answers "why not the obvious alternative". |
| `rename` | The comment explains what better names would say. Name the rename or the extracted function that retires it. |
| `delete` | Restates the line below, states a fact about the data rather than the code, records history ("now", "used to be"), points at an untracked file/ADR/GitHub issue instead of stating the reasoning inline, or no longer matches the code. |

### 3. Report and apply

Report one line per block — `path:line`, verdict, and the reason in a few words. Then apply every `keep`,
`shorten` and `delete` verdict directly. Leave each `rename` as a proposal: it changes code, not just a
comment, so it is the user's call.

Done when every block the script printed carries a verdict and every applied edit is in the working tree —
unless `manual` was asked for, in which case continue to step 4 before applying anything.

### 4. Manual pass (only when asked)

Put each block to the user **one at a time**, in the script's order, and wait for their verdict before moving
to the next. Never batch several blocks into one question, and never assume a verdict from an earlier answer.

Each turn shows, for one block:

- `path:line` and the comment text as it stands.
- Enough surrounding code to judge it — the function it sits in, or the lines it describes. Show the code,
  not a description of it; the user cannot judge a comment they cannot see in context.
- Your own verdict from step 2 and the one-line reason, so the user is agreeing or overruling rather than
  starting from nothing.

Ask for `keep`, `shorten` or `delete` (add `rename` only where a name change would genuinely retire the
comment). Apply the user's verdict, not yours, and move on without arguing a rejected one.

Re-run the extract script at the end: a comment reworded during the pass was never judged in its new form.
