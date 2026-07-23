---
paths:
  - "**/*.md"
---

# Rules for Markdown files

## Verify before declaring done

Never claim a Markdown file is clean without running the real linter — not on your
own judgement, and never on a sub-agent's report that it "fixed everything":

```bash
markdownlint-cli2 "**/*.md"
```

Use the glob form (`"**/*.md"`), not `find . -name "*.md" -exec ...`. Explicit file
arguments bypass the `ignores` in `.markdownlint-cli2.yaml`, which would lint the
vendored directories configured there. The task is done only when the summary reads
`0 error(s)`.

## Lint policy is fixed in config

The rule set lives in `.markdownlint-cli2.yaml`:

- `MD013` (line-length) is **off** — prose is not hard-wrapped at 80 columns.
- Every structural rule stays **on**.

Do not silence a rule to make an error disappear. If a rule genuinely does not fit
the project, raise it first — do not edit the config unilaterally.

## Recurring pitfalls — get these right while writing

- **MD031** — surround every fenced code block with blank lines (above and below).
- **MD032** — surround every list with blank lines.
- **MD040** — give every code fence a language; use `text` for raw terminal output.
- **MD060** — table delimiter rows need spaces around the pipes:
  `| --- | --- |`, never `|---|---|`.
- **MD036** — use real headings (`###`), never bold text as a section title.
- **Task lists** — write `- [ ] item`, never `1. - [ ]` (mixed number + checkbox).

## Auto-fix, then finish by hand

`markdownlint-cli2 --fix "**/*.md"` resolves most whitespace rules (MD031, MD032)
automatically. The delimiter-row (MD060), missing-language (MD040), and
emphasis-as-heading (MD036) cases are **not** auto-fixed — correct them manually,
then re-run the linter.

## Accuracy over invention

Document only what exists. Never describe files, directories, or a project structure
that is not actually in the repository; mark anything not yet built as planned.
