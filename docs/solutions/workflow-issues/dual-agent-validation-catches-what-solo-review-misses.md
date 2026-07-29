---
title: "Dual-agent validation catches what solo review misses"
date: 2026-07-29
category: workflow-issues
module: mbproj-scaffold
problem_type: workflow_issue
component: development_workflow
severity: high
related_components:
  - testing_framework
  - tooling
  - documentation
applies_when:
  - Shipping a scaffolder, generator, or migration tool that writes into other people's repositories
  - A single author has reviewed a fix and judged it ready to ship
  - Every fixture in a parser or writer suite was authored by the person who wrote the code
  - A dry-run report is about to become the safety gate in front of an apply step
  - Deciding whether a fresh test suite has been shown to fail on purpose, not merely to pass
symptoms:
  - Two independent reviewers on different fixtures report the same defects the author missed
  - A fix for one false negative introduces several false positives elsewhere in the same parser
  - A re-run duplicates a line it should have reconciled, while lint stays green and the report stays silent
  - Most injected mutants survive against a suite that reports a full pass
  - The fixture never contains the input shapes that trigger the defect
  - The suite asserts on report text but never on what was written to disk
root_cause: missing_workflow_step
resolution_type: workflow_improvement
tags:
  - cross-validation
  - agent-teams
  - brownfield
  - greenfield
  - mutation-testing
  - fixture-coverage
  - idempotency
  - code-review
---

## Context

Epic #14 shipped a preflight for `mbproj-scaffold`: a report of what applying the scaffold
would do, later promoted to the gate in front of the apply step itself. The author's tests
passed, `make lint` was green, and each unit looked done.

Before merging, every unit was routed through two independent validators, each a Claude Code
teammate with `--add-dir` scoped to its own repository — one **brownfield** (a real project
already carrying the tooling this scaffolder generates), one **greenfield** (a repository the
scaffolder had never touched). Their contract was narrow: build your own fixtures, measure,
and **report — do not fix**.

They found **28 real defects** in code that had been validated in isolation and judged
shippable. Mutation testing then went further and showed that even a carefully written *new*
suite covering those fixes let 11 of 13 injected mutations pass silently — including
regressions of the two worst defects already believed fixed.

## Guidance

### 1. Two validators, two terrains, report-only

Put a real already-tooled repository and a repository the tool has never seen in front of two
reviewers who do not talk to each other while working. Each builds its own fixtures in a
scratchpad, treats its repository as read-only, and compares a tree fingerprint before and
after every run.

Neither may patch what they validate. The asymmetry is the point: a validator who starts
fixing stops being a check on the implementer's blind spots and starts sharing them. In
practice both validators repeatedly said "I report, I do not correct" and left the arbitration
to the author — including on questions where they had a clear opinion.

The two found **the same defects independently, on different fixtures, without coordinating**.
That convergence is the strongest available signal that a defect is real rather than an
artifact of one person's test setup.

### 2. Expect fixes to create defects — re-validate after each one

Measured twice in this epic:

- Fixing a parser false negative introduced **three** false positives: `$(info build: …)` read
  as declaring a target, the body of a `define` block read as rules, and a tab-indented
  Markdown line read as an indented heading.
- Making the writer aware of fenced code blocks broke **idempotence**: anchor lines the writer
  had itself appended fell inside an unclosed fence, so it stopped recognising its own output
  and re-added them — two more on every run, unbounded, with lint green and the report silent.

The rule is structural, not a caution: **re-validate after each correction**, not once at the
end. A fix is a code change, and code changes regress things.

### 3. An absent form reads as a passing test, not as a missing one

The new suite was mutation-tested by one validator: 13 mutations, **11 undetected**. With two
live regressions present simultaneously it still answered `ok (0 failure(s))`.

Two structural causes, both worth generalising:

- **The fixture lacked the shapes that trigger the bugs.** Its Makefile had one target per
  line, no variables, no `define`, no `$(…)`; its Markdown had no fenced block, no indented
  heading, no setext heading. From the runner's point of view a form that never appears is
  indistinguishable from a form that was tested and passed — the green is identical.
- **The suite proved the report, never the write.** After a first round of fixes, 7 mutations
  still survived, every one restoring a *writer* bug: an anchor left in place, a BOM dropped,
  the include anchored last, an exclude left unnormalised. None of the seven changed what the
  report said, which is exactly why they survived a suite built around it.

The fix was two-pronged: pin every faulty form to its own case asserted **directly against the
parser** rather than through an end-to-end report, and add a write-path check — apply twice,
compare byte for byte, then assert the properties only the written files carry. Afterwards
every mutation failed, each with one to three distinct failures.

### 4. Measure a claim about someone else's tool; do not reason about it

Both validators corrected documentation the author had written but never run:

- "Redefining a recipe stops the generated checks from running." **False.** GNU make merges the
  prerequisites of every rule for a target and replaces only the recipe, so prerequisites
  declared by the generated include still run; what is lost is one recipe line. The warning is
  the real signal, not a broken build.
- "The preflight must be silent after migrating." **False**, and self-contradicting: the
  prerequisite-only extension the same document recommends creates a collision by
  construction, reported for as long as it exists. What must be clear is the **gate** — exit
  zero, nothing overwritten, nothing blocked — not the report.

### 5. Check your own assertions against the artifact

Two of the author's test assertions were wrong before the code was: an include documented as
being "on line 1" was asserted at index 1, in a file where a BOM precedes it; and a `//`
substring check ran against a file whose only `//` is inside a URL. Both were caught by reading
the literal artifact rather than trusting what the assertion meant to say — the same discipline
[the stale-tooling learning](../developer-experience/diagnosing-installed-but-broken-tooling.md)
states as "test the exact string you ship, never a paraphrase".

### 6. Freeze the tree when it can move under the reviewer

One validator noticed the author was committing during its pass, extracted the commit under
test with `git archive` into an isolated copy, ran its battery there, then re-ran it against
the working tree and reported both verdicts separately. Encourage this explicitly: without it,
"the reviewed commit is correct" and "the current tree is correct" silently become one claim.

## Why This Matters

- **Author-written fixtures share the author's blind spots by construction.** The four worst
  defects — a BOM colliding with include placement, a quoted `@import` deleted by anchor
  reconciliation, a two-target line seen as zero targets, unbounded anchor accumulation — were
  all invisible to fixtures written by the same hand as the code. More scrutiny of those
  fixtures would not have found them; independent terrain did.
- **A passing suite and a validated tool are different claims.** Lint green and tests green
  were both true while 28 defects stood. Tests bound only what they looked at; mutation testing
  is what measures whether they looked at the right things.
- **Some defects emit no error at all.** The BOM collision made a project's own target vanish
  while `make help` kept answering — because that answer came from the generated include, not
  the project. Nothing short of adversarial validation surfaces that before a user hits it.
- **Report-only protects independence.** Had either validator patched what it found, its
  remaining findings would carry its own fix choices, collapsing two perspectives into one.

## When to Apply

- Before merging any tool that writes into a repository someone else owns — especially once its
  dry-run report is meant to be trusted as a gate.
- When every fixture for a parser or writer was authored by whoever wrote it.
- Immediately after each fix found by validation, before declaring the epic closed.
- When documentation asserts something about a third-party tool's behaviour: run that tool.
- When claiming idempotence — that claim is proven by a second apply and a byte comparison,
  never by inspection.

## Examples

### A fixture that cannot see a defect, versus a case that pins it

The original fixture's Makefile had one target per line and no `$(…)` anywhere. A bug in how
`$(info build: …)` is classified cannot be exercised by it: the mutation restoring that bug
passes clean, not because the parser is right but because nothing in the fixture asks the
question.

Pinning the shape against the parser asks it directly:

```python
MAKE_FORMS = [
    ("two targets on one line", "lint build:\n\t@echo x\n", {"lint", "build"}),
    ("function call carrying a colon", "$(info build: starting)\n", set()),
    ("define body", "define USAGE\n  build: compile\nendef\n", set()),
]
```

Each case fails on its own the moment the classifying logic regresses, whatever the end-to-end
report happens to say. Eleven Makefile forms and eleven heading forms are pinned this way in
`skills/mbproj-scaffold/tests/brownfield_check.py`.

### The write-path check the report-only suite was missing

Applying twice and comparing the trees is what catches the whole class of writer regressions:

```bash
python3 skills/mbproj-scaffold/scripts/mbproj_apply.py "$REPO" \
  --layer lint_format --layer guards --layer changelog
cp -a "$REPO" "$REPO.first"
python3 skills/mbproj-scaffold/scripts/mbproj_apply.py "$REPO" \
  --layer lint_format --layer guards --layer changelog
diff -r "$REPO.first" "$REPO"
```

Empty output is the only acceptable result. Before this existed, the suite asserted on report
text — which stayed identical across both applies while the second one left a duplicated
`@import` line behind. File content and report text had silently diverged, and only a
comparison of the written bytes surfaces that.

## Related

- [`skills/mbproj-scaffold/tests/brownfield_check.py`](../../../skills/mbproj-scaffold/tests/brownfield_check.py)
  — the suite this learning is about. Its own docstring records the trigger for two of its four
  halves.
- [`docs/adoption.md`](../../adoption.md) — the user-facing side of the same fixture: how a
  maintainer migrates when the preflight reports conflicts.
- [`docs/spine.md`](../../spine.md) — I1 (idempotent and non-destructive) and I3 (shared-file
  mechanisms) are the invariants the accumulation and BOM defects violated.
- [`.claude/team.md`](../../../.claude/team.md) — the two validators, their grounds, and the
  four clauses a teammate prompt must carry. It does not yet state the report-only rule
  explicitly; this learning is the argument for adding it.
- [`docs/solutions/developer-experience/diagnosing-installed-but-broken-tooling.md`](../developer-experience/diagnosing-installed-but-broken-tooling.md)
  — same underlying failure mode from another angle: a green test that exercised a stand-in
  rather than the artifact that ships.
- Epic [#14](https://github.com/mathieubodin/claude-mbproj/issues/14) and units #9–#13 — the
  work this method was applied to.
