# claude-mbproj

Guidance for AI agents working in this repository.

`docs/solutions/` — documented solutions to past problems (bugs, best practices, workflow
patterns), organized by category with YAML frontmatter (`module`, `tags`, `problem_type`).
Relevant when implementing or debugging in documented areas.

`.claude/team.md` — the two teammates that validate every change (brownfield and greenfield),
and the session configuration they require. Read it before spawning or briefing one.

`CONCEPTS.md` — shared domain vocabulary (owned and shared files, layers, the manifest, the
preflight). Relevant when orienting to the codebase or discussing its concepts.

Releasing is `make release VERSION=X.Y.Z`, which stops before publishing anything, then
`make publish`. Never run `make publish` on your own initiative — the split exists so a
human reviews the release commit first. See CONTRIBUTING.md for what each step does.

@.claude/mbproj/conventions.md
