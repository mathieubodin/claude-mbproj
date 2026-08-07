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

1. **Lint & format** — `.claude/rules/*.md` and `.claude/mbproj/conventions.md`, a generic
   `mbproj.mk` (`lint` / `build` / `package` / `clean`), `.markdownlint-cli2.yaml`,
   `.shellcheckrc`.
2. **Git guards** — `prek.toml`, `commitlint.config.js`, a secret-scanning block in
   `.gitleaks.toml`, and an `install-hooks` target.
3. **Changelog** — `cliff.toml` + [git-cliff](https://git-cliff.org/) (`make changelog`).
   Depends on the guards layer.
4. **Agentic workflow** — BMAD + compound-engineering setup and a CLAUDE.md
   "Agentic Workflow" section.

Whichever layers you pick, `mbproj.mk` always carries `help` and `check-dev-env`.

Applied layers and the plugin version are tracked in a `.config/mbproj.toml` manifest, so a
re-run reads what is already installed and offers to add or update.

## Design invariants

- **Idempotent & non-destructive** — a re-run never breaks existing files.
- **Re-entrant by whole-file rewrite** — each config is a dedicated file rewritten in full;
  the project `Makefile` delegates via `include mbproj.mk`. Where a file offers no such
  indirection (`.gitignore`, `SETUP_ENV.md`, `.gitleaks.toml`), the plugin owns a delimited
  block inside it and regenerates that block whole — everything outside the markers is yours
  and survives.
- **Generic only** — the plugin ships only reusable tooling. The project name and the
  vendored directories are detected or asked for; tool sets are fixed per layer, and
  project-specific targets are out of scope entirely.

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

All four layers are implemented. Released versions live in
[`CHANGELOG.md`](CHANGELOG.md) — this page names none on purpose, so it cannot fall behind
one.

The lint/format, guards, and changelog layers are dogfooded on this repository: `make lint`,
`make check-dev-env`, `make changelog`, and the git hooks all run here. The agentic layer is
deliberately not applied here (this repo is a plugin, not a BMAD-developed project). Every
change is validated on two grounds — a repository that already carries its own equivalents
of what the plugin brings, and one that carries nothing at all — because they fail in
different ways, so a change proven on one is not proven.

## Documentation

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — working on the plugin itself.
- [`CONCEPTS.md`](CONCEPTS.md) — the vocabulary this page uses: owned and shared files,
  layers, the manifest, the preflight.
- [`docs/spine.md`](docs/spine.md) — the design spine (invariants, layers, manifest).
- [`docs/adoption.md`](docs/adoption.md) — adopting the socle in a repo that already has
  tooling: what the preflight reports, and the migration it asks for.
- [`SETUP_ENV.md`](SETUP_ENV.md) — installing the tools the generated `make` targets need.
- [`CHANGELOG.md`](CHANGELOG.md) — generated release history.

## License

[MIT](LICENSE) © Mathieu Bodin
