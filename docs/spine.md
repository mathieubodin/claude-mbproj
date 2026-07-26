# mbproj-scaffold — Design Spine

Authoritative design invariants for the `mbproj-scaffold` skill (plugin `claude-mbproj`).
This document is the frozen backbone: layers, files, and re-run behaviour are derived from
it. It was grounded on the reference project (`claude-code-monitoring`), from which the
generic tooling is extracted.

## Purpose

Scaffold a reusable tooling socle — lint/format, git guards, changelog, agentic workflow —
into any repository (new **or** existing), à la carte. The skill is **idempotent**,
**re-entrant**, and **non-destructive**. Generated files are ordinary committed files: once
written, teammates and CI use them with plain `make`. Claude is only needed to initialize or
update the tooling, never to run it.

## Terminology

- **Owned file** — a file whose full content belongs to mbproj. Rewritten integrally on
  every run. Carries a "generated — do not edit" banner.
- **Shared file** — a file the target project also writes to (`Makefile`, `CLAUDE.md`,
  `.gitignore`, `SETUP_ENV.md`). mbproj may not own it wholesale; it touches it through the
  exception rule (I3).
- **Layer** — an à-la-carte unit of tooling the user opts into (`lint_format`, `guards`,
  `changelog`, `agentic`).
- **Manifest** — `.config/mbproj.toml`, the single source of truth for applied layers,
  versions, and detected/asked parameters.

## Invariants

- **I1 — Idempotent & non-destructive.** A re-run never breaks what already exists, and never
  destroys project-authored content in a shared file.
- **I2 — Re-entrancy by whole-file rewrite.** Each owned config is a dedicated file rewritten
  in full. Marked in-file blocks are **prohibited in owned files**; the only sanctioned
  delimited block is the shared-file mechanism of I3(b).
- **I3 — Shared-file exception.** For files mbproj cannot own wholesale, use one of two
  mechanisms. If the shared file is **absent** (new project), it is **created minimally**
  first, then the mechanism is applied.
  - **(a) Anchor line + owned satellite** — when the format supports indirection, mbproj
    injects a single line pointing at an owned file that holds the real content:
    - `Makefile` → one line `include mbproj.mk`, placed **first**. Placement is semantic
      here, not cosmetic: GNU make lets the *last* recipe for a target win, so an include
      placed last would silently override a project's own `build` or `package` recipe with
      the generic placeholder. Anchoring first lets project definitions take precedence;
      make then warns, but only when a project actually specializes a target — which is
      exactly when the override is intended.
    - `CLAUDE.md` → one `@import` line **per applied layer** that carries prose
      (`@.claude/mbproj/conventions.md`, `@.claude/mbproj/agentic.md`), appended.
  - **(b) Delimited owned block, regenerated in full** — when no indirection exists, mbproj
    owns a region delimited by `# >>> mbproj:managed (do not edit) >>>` …
    `# <<< mbproj:managed <<<` (the comment prefix follows the file's syntax — `<!-- … -->`
    in Markdown), **regenerated integrally on every run**; content outside the delimiters is
    never touched.
    - `.gitignore` → git has no include mechanism.
    - `SETUP_ENV.md` → the `_check_*` fix messages reference `SETUP_ENV.md#<tool>` anchors, so
      the generic tool sections **must** live inside the file (indirection would break the
      anchors).

    Regenerating the block in full (not line-appending) is what keeps it idempotent: obsolete
    entries (e.g. a removed `vendored_dirs` value) disappear instead of lingering.
- **I4 — Manifest is the source of truth.** `.config/mbproj.toml` records applied layers,
  their versions, and parameters. The re-run reads state from it.
- **I5 — Consistent `mbproj` namespace.** Skill, `mbproj.mk`, `.config/mbproj.toml`, the
  `mbproj:managed` block delimiters, and the `.claude/mbproj/` directory all share the
  namespace.
- **I6 — Strict generic/specific separation.** The plugin ships **only** generic tooling.
  Project-specific parameters are detected or asked for, never hardcoded.
- **I7 — Banner + unconditional rewrite.** Owned files (and I3(b) blocks) carry a "generated
  by mbproj-scaffold — do not edit; re-run `/mbproj-scaffold` to update" banner. The re-run
  rewrites them unconditionally; committed history (git) is the recovery net. No backups.
- **I8 — Owned content is composed from the manifest.** The content of owned files and I3(b)
  blocks is a function of the applied layers and parameters:
  - `check-dev-env` aggregates **only** the tool checks of the applied layers.
  - `SETUP_ENV.md` managed block holds **only** the tool sections of the applied layers.
  - Lint/hook excludes = generic defaults (`.git`, `node_modules`, `dist`, `.idea`,
    `.vscode`) ∪ layer-contributed (agentic ⇒ `_bmad`, `_bmad-output`,
    `.claude/skills/bmad-*`) ∪ the `vendored_dirs` parameter. Layer excludes stay **narrow**:
    `.claude/skills/bmad-*` targets BMAD's vendored skills only, so a project's own skills
    keep being linted.

## Layers

Tool sets are **fixed per layer** (grounded on the reference project), not detected from the
project language — there is no language toolchain (`cargo`, `go`, `npm`, …). `docker` is
**project-specific** (it served the reference project's OTel collector) and is **not** part
of any layer.

- **`lint_format`** (depends on: none) — owned: `.claude/rules/{json,makefile,markdown,projects-files,yaml}.md`,
  `.claude/mbproj/conventions.md`, `mbproj.mk` (build/package/clean/lint),
  `.markdownlint-cli2.yaml`, `.shellcheckrc`. Tools: `markdownlint-cli2`, `jq`, `yq`, `shellcheck`.
- **`guards`** (depends on: `lint_format`) — owned: `prek.toml`, `commitlint.config.js`,
  `mbproj.mk` (install-hooks). Tools: `prek`, `commitlint`.
- **`changelog`** (depends on: `guards`) — owned: `cliff.toml`, `mbproj.mk` (changelog).
  Tools: `git-cliff`.
- **`agentic`** (independent) — owned: `.claude/mbproj/agentic.md` (Agentic Workflow only);
  also **triggers** the BMAD + compound-engineering install (see below). Tools: none.

`mbproj.mk` always carries `check-dev-env` and `help`, whichever layers are applied — `help`
backs `.DEFAULT_GOAL`, so it must exist even when `lint_format` is not applied.

Dependency chain: `lint_format → guards → changelog` (linear); `agentic` is independent.
`guards` depends on `lint_format` because the `prek` pre-commit hook delegates to
`make lint`. `changelog` depends on `guards` because `git-cliff` relies on the conventional
commits enforced by `commitlint`.

### Shared-file contributions (via I3)

Each layer injects into shared files as follows; contributions are composed (I8):

- **`Makefile`** — I3(a): `include mbproj.mk` (once, when any `mbproj.mk`-owning layer is applied).
- **`CLAUDE.md`** — I3(a): one `@import` per applied prose layer
  (`lint_format` ⇒ `conventions.md`; `agentic` ⇒ `agentic.md`).
- **`SETUP_ENV.md`** — I3(b): tool install sections for the applied layers' tools (composed).
- **`.gitignore`** — I3(b): mbproj ignore lines, regenerated in full
  (generic defaults ∪ layer-contributed ∪ `vendored_dirs`).

### `agentic` — different nature

The other three layers write configuration. `agentic` instead **orchestrates external
installs** and writes only `.claude/mbproj/agentic.md`. The spike settled the open questions:
compound-engineering installs through the `claude plugin` CLI at project scope, BMAD through
`npx bmad-method install` (no submodule), and both steps are guarded so a re-run is a no-op.
It also encodes a **Mathieu-specific** workflow (BMAD + CE), so it is "generic-to-Mathieu"
rather than universal.

## Manifest

`.config/mbproj.toml` stores applied layers (with the plugin version that generated each),
plus parameters. The tool set is **not** stored — it is derivable from the applied layers
(single source of truth).

```toml
[mbproj]
plugin_version = "0.1.0"

[layers]
lint_format = { applied = true,  version = "0.1.0" }
guards      = { applied = false }
changelog   = { applied = false }
agentic     = { applied = false }

[params]
project_name  = "my-repo"
vendored_dirs = ["vendor", "third_party"]
```

## Re-run algorithm

1. Read the manifest (absent ⇒ fresh install).
2. Detect parameters and confirm them with the user.
3. Present the current state (which layers are applied, at which version).
4. Let the user select layers to add or update, enforcing the dependency chain.
5. **Compose** each owned file and each I3(b) block from the manifest (applied layers +
   params) and rewrite it in full; apply the shared-file exception (I3) for `Makefile`,
   `CLAUDE.md`, `SETUP_ENV.md`, `.gitignore` — creating any that are absent.
6. Rewrite the manifest.

## Parameters

- **Tool sets** — fixed per layer (see the layer list). Not detected, not asked.
- **`project_name`** — detected (git remote basename, else directory name), then confirmed.
- **`vendored_dirs`** — asked (cannot be reliably detected); feeds the composed excludes
  (I8).
- **Layer selection** — always asked; that is the à-la-carte principle.

## Generic / specific boundary

Grounded on the reference project's actual tooling.

**Generic (ships in the plugin):** the five `.claude/rules/*.md`; the five configs
(`prek.toml`, `commitlint.config.js`, `cliff.toml`, `.shellcheckrc`,
`.markdownlint-cli2.yaml`); the generic `mbproj.mk` targets (build, changelog,
check-dev-env, clean, help, install-hooks, lint, package); the generic `SETUP_ENV.md` tool
sections; the generic `CLAUDE.md` conventions — Code Standards and When Adding Features (via
`.claude/mbproj/conventions.md`, `lint_format`) and Agentic Workflow (via
`.claude/mbproj/agentic.md`, `agentic`).

**Specific (never ships):** collector targets (`start/stop-local-collector`) and
`COLLECTOR_*` variables; the OTel collector config; the `docker` check and its
`SETUP_ENV.md#docker` section; the `CLAUDE.md` Project Overview and Monitoring sections;
project `_bmad` content; `README.md` / `CONTRIBUTING.md`.

## Non-goals (v1)

- No uninstall / removal path.
- No language toolchains (content linters only).
- No project-specific targets (collector, services, …).
