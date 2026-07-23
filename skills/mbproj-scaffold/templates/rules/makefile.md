---
paths:
  - "Makefile"
---

# Rules for project's Makefile

- Three types of targets:
  - "Main" targets: exposed through `.PHONY`, callable from command line
  - "Sub" targets: not exposed, called from main targets
  - "File" targets: named after a real file they generate; used as prerequisites to avoid recursive make
- Mandatory main targets (minimum, not exhaustive):
  - build -- build artefacts, compile source code, etc.
  - check-dev-env -- assert whether mandatory tools are available in the current environment
  - clean -- remove temporary build artefacts or packages
  - help -- describe available targets and configuration (through environment variables)
  - lint -- lint the files of the project
  - package -- build deliverable packages of the project
- Sub targets are:
  - a dedicated check for a specific tool (availability only; the command is inlined in the caller)
  - a dedicated lint for a specific file kind
  - any target shared by several main targets
- Main targets are ordered alphabetically; their sub targets immediately follow them
- Main targets are documented with a `##` comment after their name
- Main target names are lowercase
- Sub target names start with `_`
- No target calls make recursively
- When adding a target, first ask the user whether it is a main target
- When a main target require a specific tool, prefer native installation, or standalone, or in last choice via npx. Avoid Python based - pip like - installations.

CONTRIBUTING.md must be kept in sync to reflect how the Makefile targets help the development process.

CLAUDE.md must be kept in sync to explain how AI agents should use the Makefile targets.
