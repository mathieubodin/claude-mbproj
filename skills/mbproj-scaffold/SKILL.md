---
name: mbproj-scaffold
description: "Scaffold reusable project tooling (lint/format, git guards, changelog, agentic workflow) into any repo — new or existing, à la carte. Idempotent, re-entrant, non-destructive. Run to initialize or update the tooling."
version: 0.1.0
user-invocable: true
---

# mbproj-scaffold

Scaffold a reusable tooling socle into the current repository — new **or** existing — **à la
carte**. The skill is **idempotent**, **re-entrant**, and **non-destructive**: a re-run never
breaks what already exists. It writes ordinary committed files; once written, teammates and CI
use them with plain `make`. You (Claude) are only needed to initialize or update the tooling,
never to run it.

The authoritative design lives in the plugin repo's `docs/spine.md` (invariants I1–I8, layers,
manifest, re-run algorithm). Read it before extending this skill.

## Engine

Mechanical file operations are handled by deterministic Python scripts so re-runs are
**byte-identical** — a guarantee an LLM cannot provide (I2/I7). Resolve the skill directory
first, and re-set it in **every** Bash call (shell variables do not persist between calls):

```bash
SKILL_DIR="${CLAUDE_SKILL_DIR:-$CLAUDE_PLUGIN_ROOT/skills/mbproj-scaffold}"
```

Scripts in `$SKILL_DIR/scripts/`:

- `mbproj_manifest.py` — read/write the `.config/mbproj.toml` manifest (source of truth).
- `mbproj_writer.py` — write an owned file with the do-not-edit banner.

## Flow

1. **Locate the target repo root** — the git top-level of the current working directory
   (`git rev-parse --show-toplevel`).
2. **Read the manifest** — `python3 "$SKILL_DIR/scripts/mbproj_manifest.py" read <repo>` prints
   the JSON state (applied layers, versions, params). A missing manifest means a fresh install
   (default state, all layers `applied = false`).
3. **Detect & confirm parameters** — `project_name` (git remote basename, else directory name);
   `vendored_dirs` (ask the user). Persist with the `set-param` subcommand.
4. **Present the current state** and let the user pick which layers to add or update, enforcing
   the dependency chain `lint_format → guards → changelog` (`agentic` is independent).
5. **Apply the selected layers** — *handled by the per-layer logic (forthcoming units).*
6. **Write the manifest back** — `set-layer` / `set-param` subcommands, or pipe an updated JSON
   state to `mbproj_manifest.py write <repo>`.

> Status: v0.1.0 — this unit (U1) delivers the engine core: manifest read/write, the owned-file
> writer, and the banner. The I3 shared-file primitives, the `lint_format` content, and
> composition land in later units.
