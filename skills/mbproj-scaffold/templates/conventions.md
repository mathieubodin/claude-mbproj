# Conventions

Project conventions scaffolded by mbproj-scaffold (the `lint_format` layer). These are
framework-agnostic; agentic-workflow specifics live in a separate imported file.

## Code standards

- Record durable project context (decisions, rationale) in your project memory, not
  scattered across code comments; comment only the non-obvious *why*.
- Follow Conventional Commits — use the `conventional-commit` skill to author messages.
- Review in two phases: metadata triage (decide *where* to look), then code-grounded
  findings (the only phase that ranks severity).
- **Documentation review before pushing is mandatory.** Confront every checkable claim in the
  human-facing documents with the code, and look hardest at the documents the change did not
  touch. Stale prose breaks no test, fails no lint and appears in no diff. How to run it is the
  project's agentic workflow's business; that it runs is not optional.
- Pre-merge checklist: a code-grounded review of the diff, a measured coverage number,
  then `make lint` green for both code and documentation. The tooling lints; it does not
  reformat, so formatting is on the author.

## When adding a feature

1. Search prior decisions before starting.
2. Brainstorm critically against project history and domain best practices.
3. Document non-obvious decisions (not as code comments unless the *why* is truly hidden).
4. Plan before implementing; short-circuit trivial fixes.
5. Review the diff before merging.
6. Include a measured coverage number in the change description.
