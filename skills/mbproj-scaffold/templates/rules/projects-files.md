---
paths:
  - "CHANGELOG.md"
  - "CONTRIBUTING.md"
  - "README.md"
  - "SETUP_ENV.md"
---

# Rules for projects Markdown files

Projects rely on a set of documentation (minimum not exhaustive):

- `README.md` -- Main entry for projects, it describe the purpose of the project
- `CONTRIBUTING.md` -- It describe how to contribute to the project, conventions to propose evolutions or bugfixes, etc...
- `SETUP_ENV.md` -- Dedicated documentation focused on the installation of the tooling required by the Makefile (or any analogous build tool)
- `CHANGELOG.md` -- Describe the changes history of the project

These documentations follow the DRY principle (Don't Repeat Yourself): information must be written once in the relevant document. Others may cite part of this information, but must reference the root location.

Projects documentation must not be tied to a specific AI agentic framework. AI-agent-specific docs (e.g. `CLAUDE.md`) are intentionally out of scope of this list.

## README.md rules

- It is intended to any reader that need project context
- It shouldn't contain contributing information, apart from a quick setup in a TLDR (Too Long, Didn't Read) section
- It should reference other documentation files.

## CONTRIBUTING.md rules

- It is intended to any reader that want to contribute to the project.
- It shouldn't duplicate the project context already present in `README.md`; it may add contribution-specific context (architecture, testing) not needed by general readers
- It should guide the reader through the process of setting up its environment
- It should delegate to `SETUP_ENV.md` the exact commands installing the required tools.

## SETUP_ENV.md rules

- It is intended to any reader that need to setup an environment to build or contribute to the project
- It may reference other documentation
- It should lead with the OS-agnostic install method (standalone binary or official installer), then list per-OS shortcuts (apt, brew, …) as secondary

## CHANGELOG.md rules

- `CHANGELOG.md` is **generated**, never hand-edited: run `make changelog` (wraps
  `git-cliff`) to rebuild it from the conventional commit history.
- The generation policy is explicit and versioned in `cliff.toml` (Keep a Changelog
  layout, commits grouped by type/scope).
- This closes the loop with commitlint: conventional commits in, changelog out.
