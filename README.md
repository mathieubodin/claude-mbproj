# claude-mbproj

A [Claude Code](https://code.claude.com/docs) plugin that scaffolds reusable project
tooling — lint/format conventions, git guards, changelog, and an agentic workflow — into
any repository, new **or** existing.

It ships a single skill, `mbproj-scaffold`, which is **idempotent**, **re-entrant**, and
**non-destructive**: re-running it never breaks what is already there.

## Why

The skill writes ordinary, committed files into your target repo — a Makefile include,
linter configs, `.claude/rules/*.md`, git hooks. Once generated, teammates and CI use them
with plain `make`. **Claude is only needed to initialize or update the tooling — never to
run it.**

## Layers (à la carte)

You pick which layers to apply; each can be added later on a re-run.

1. **Lint & format** — `.claude/rules/*.md`, a generic `mbproj.mk`
   (`lint` / `build` / `clean` / `help` / `check-dev-env`), `.markdownlint-cli2.yaml`,
   `.shellcheckrc`.
2. **Git guards** — `prek.toml`, `commitlint.config.js`, an `install-hooks` target.
3. **Changelog** — `cliff.toml` + [git-cliff](https://git-cliff.org/) (`make changelog`).
   Depends on the guards layer.
4. **Agentic workflow** — BMAD + compound-engineering setup and a CLAUDE.md
   "Agentic Workflow" section.

Applied layers and the plugin version are tracked in a `.config/mbproj.toml` manifest, so a
re-run reads what is already installed and offers to add or update.

## Design invariants

- **Idempotent & non-destructive** — a re-run never breaks existing files.
- **Re-entrant by whole-file rewrite** — each config is a dedicated file rewritten in full;
  the project `Makefile` delegates via `include mbproj.mk`. No managed in-file blocks.
- **Generic only** — the plugin ships only reusable tooling; project-specific parameters
  (project name, vendored dirs, tool set, project targets) are detected or asked for.

## Install

```text
/plugin marketplace add mathieubodin/claude-mbproj
/plugin install claude-mbproj@claude-mbproj
/reload-plugins
```

Or browse interactively with `/plugin` (Discover tab). Then, from the repo you want to
scaffold:

```text
/mbproj-scaffold
```

## Status

Early development (v0.1.0). The design spine is being defined and the `mbproj-scaffold`
skill is not yet implemented.

## License

[MIT](LICENSE) © Mathieu Bodin
