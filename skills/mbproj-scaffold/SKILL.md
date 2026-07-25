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
5. **Apply the selected layers** — run the composition engine, which writes every owned file
   and shared-file contribution and updates the manifest:

   ```bash
   python3 "$SKILL_DIR/scripts/mbproj_apply.py" <repo> \
     --layer <name> [--layer <name> ...] \
     --project-name <name> [--vendored-dir <dir> ...]
   ```

   Dependencies are enforced (`lint_format → guards → changelog`; `agentic` is independent).
6. **Install the agentic tooling** *(only if the `agentic` layer was applied)* — run the guarded
   steps in the next section.

## Agentic layer — tooling install

When the `agentic` layer is applied, install its tooling after the engine has written the
files. Each step is guarded so a re-run is a no-op. Requires **Node.js 20+**.

Install compound-engineering at **project scope** (so teammates get it too):

```bash
if ! grep -q '"compound-engineering-plugin"' .claude/settings.json 2>/dev/null; then
  claude plugin marketplace add EveryInc/compound-engineering-plugin --scope project
fi
if ! grep -q 'compound-engineering@compound-engineering-plugin' .claude/settings.json 2>/dev/null; then
  claude plugin install compound-engineering@compound-engineering-plugin --scope project
fi
```

Guard on `.claude/settings.json` — the file `--scope project` writes — and **not** on
`claude plugin list`. The listing is scope-blind: it reports a plugin the developer already has
at *user* scope, so the guard would skip and the project would never declare it, silently
defeating the point of project scope (teammates cloning the repo get the tooling). Grep the
project file instead, and match the plugin id without a start-of-line anchor: the listing
indents its entries, so `^compound-engineering` never matches either.

An already-installed plugin can still be **disabled**, in which case its skills do not load.
Check the `Status:` line of `claude plugin list` and enable it if needed:

```bash
claude plugin enable compound-engineering@compound-engineering-plugin
```

Install BMAD-Method (the `bmm` module, Claude Code integration) if not already present:

```bash
if [ ! -d "<repo>/_bmad" ]; then
  npx --yes bmad-method install --directory "<repo>" --modules bmm --tools claude-code --yes
fi
```

> Status: v0.1.0 — all four layers are implemented (lint_format, guards, changelog, agentic).
