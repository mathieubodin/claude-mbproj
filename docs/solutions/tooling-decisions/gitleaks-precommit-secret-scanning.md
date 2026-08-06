---
title: "Blocking secret detection at commit time — making gitleaks affordable, and the four ways it silently does nothing"
date: 2026-08-06
category: tooling-decisions
module: mbproj-scaffold
problem_type: tooling_decision
component: tooling
severity: high
related_components:
  - development_workflow
  - documentation
applies_when:
  - Adding a secret scanner to a repository that already has committed history
  - Choosing between a blocking and an advisory pre-commit guard
  - A scanner config file exists and the scan reports no findings
  - Translating a project's exclude list into a second tool's path syntax
  - Deciding whether a generated config file is owned outright or shared with the project
tags:
  - gitleaks
  - secret-scanning
  - pre-commit
  - guards-layer
  - shared-file
  - allowlist-regex
  - false-negative
  - tooling-decision
---

## Context

The `guards` layer of `mbproj-scaffold` chained whitespace hygiene, `make lint` and
`commitlint`. Nothing in that chain looked for a credential. The gap surfaced during a
security review of a scaffolded project (`headscale`), and the usual mitigation was not
available: GitHub's secret scanning does not run on a private repository under the free
plan, so a local pre-commit scan is the **only** line of defence rather than a redundant
second one.

The need was preventive — the repository was clean. That framing matters, because it
sets the acceptance bar: the guard has to be cheap enough to leave on permanently in a
repository nobody is currently trying to fix.

Four candidates were weighed against one hard constraint. `prek.toml` carries the note
"prek — Rust, standalone, no Python", which rules out any Python-dependent hook:

| Tool | Runtime | Why not / why yes |
| --- | --- | --- |
| `detect-secrets` | Python | Excluded by the no-Python constraint |
| `ripsecrets` | Rust | Entropy-only; no provider catalogue |
| `trufflehog` | Go | Verifies findings over the network at commit time |
| **`gitleaks`** | **Go** | **Standalone, 222 default rules (mostly provider-prefixed), offline** |

`gitleaks` 8.30.1 was chosen, wired as a **blocking** hook ordered first in the
`pre-commit` stage, invoked as `gitleaks git --staged --redact --no-banner --verbose`.
Committed in `b2847d3`.

Most of what follows is not "how to add gitleaks". It is the set of decisions that
determine whether the guard is *sustainable* and whether it is *actually looking at
anything* — four of which fail silently, in the direction of a green scan.

## Guidance

### 1. Scan the staged diff, not the tree — that is what makes blocking affordable

`gitleaks git --staged` reads the staged **diff**. Content already committed is never
re-judged.

This is the pivot of the whole design, not a performance tweak. A scanner that judges the
tree makes a blocking hook untenable on any documentation-heavy repository: the reference
project `headscale` carries 207 Markdown files out of 311 tracked, full of token examples,
API shapes and configuration snippets. Judge the tree and every commit inherits every
finding the repository has ever accumulated, including the ones that were there before the
guard existed. The team then either disables the hook or drowns the config in allowlists —
both of which end in no detection.

Judge the diff and the guard can only ever fail on what the author is adding *right now*.
That is the finding they can act on, and the only one they are responsible for. A repo
cannot start failing on its own past.

The blocking choice follows from the same asymmetry, recorded in `build_prek`:

> a secret is the one finding whose cost survives the commit being amended, since the fix
> is a history rewrite plus a credential rotation.

Every other hook in the chain guards something an amend can repair. This one does not.

`--verbose` is load-bearing too: without it the run reports a count and no location,
leaving the author nothing to act on.

### 2. A generated config the project must extend is a *shared* file, not an owned one

`mbproj-scaffold` distinguishes owned files — rewritten in full on every re-run (I7) —
from shared files, where only a delimited `mbproj:managed` block is regenerated and
everything outside it survives (I3(b)).

`prek.toml` is owned. `.gitleaks.toml` is **shared**, and the asymmetry is deliberate.
The reasoning, from `docs/spine.md`:

> gitleaks reads one config from the repo root, and the default rule catalogue covers no
> project's own credentials. Owning the file outright would delete a project's `[[rules]]`
> on every re-run, so mbproj owns only the block.

The general rule: **a config is only ownable if the tool's defaults can plausibly be
complete for every consumer.** For a secret scanner they never are — the catalogue knows
public SaaS providers, not the credential formats a given organisation issues. A project
must be able to write `[[rules]]` that outlive a re-scaffold, or it will keep its rules
somewhere the scanner never reads.

### 3. `[extend] useDefault = true` — the line that keeps the scan looking for anything

In gitleaks, the mere **existence** of a `.gitleaks.toml` *replaces* the default rule
catalogue. It does not merge with it. Without `[extend] useDefault = true`, all 222
provider rules stop matching and the scan reports no leaks — because it is looking for
nothing.

There is no error, no warning, no reduced rule count in the output. The hook goes green on
every commit and the repository is unguarded. This is the single highest-consequence line
in the managed block, which is why it carries its own comment in the generated file:

```toml
[extend]
# Keep the default rule catalogue. Without this the mere existence of a
# .gitleaks.toml *replaces* it, and every provider rule silently stops matching -
# a scan that reports nothing because it is looking for nothing.
useDefault = true
```

Generalise it: whenever a tool's config file can *substitute* rather than *extend* its
defaults, the extend directive is a correctness requirement, and its absence produces a
false negative that looks exactly like success.

### 4. gitleaks path allowlists are regexes, not globs — and the trailing `/` is the guard

The manifest's exclude set is composed once (I8) and rendered into three syntaxes:
`find` arguments for the Makefile (`_find_exclude`), globs for markdownlint and prek
(`_glob_exclude`), and regexes for gitleaks (`_regex_exclude`). The third is a
**translation**, not a reformat, and it is the one that can silently unscan a file.

The trailing slash is what makes it safe. From `_regex_exclude`:

> Without it, the bare entry `.git` would compile to a prefix matching `.github/`, and a
> token committed to a GitHub Actions workflow would be allowlisted by the very entry
> meant to skip the object store.

`.github/workflows/` is precisely where CI secrets get pasted. The entry meant to skip
git's object store would have exempted the highest-risk directory in the repository.

The translation is asymmetric on purpose, and the direction is chosen:

> Only `*` and `?` are given glob meaning; a character class is escaped to a literal rather
> than translated. That knowingly diverges from `find` and markdownlint, and the direction
> is the reason it is acceptable: an entry gitleaks fails to exclude is scanned, which costs
> a false positive, where the reverse would cost a file silently left unscanned.

**Pin the translation as a non-regression test, and assert on match behaviour rather than
pattern text.** `check_allowlist_paths` in `skills/mbproj-scaffold/tests/brownfield_check.py`
compiles each generated pattern and checks a must-match / must-not-match path pair, because
"the question is which paths end up unscanned, and a string comparison would pass on a
pattern that is exactly wrong in the way that matters." The `.git` / `.github` case is one
of the five forms it pins.

### 5. Two exclusion mechanisms that look interchangeable and are not

The hook sets `pass_filenames = false`, because `gitleaks git --staged` reads the diff
itself. It never receives a file list — so **prek's `exclude` globs never reach it**.

A scaffolded project's exclusions therefore only take effect inside `.gitleaks.toml`. A
maintainer who adds a directory to `prek.toml`'s `exclude` and expects gitleaks to honour
it gets no error and no effect. Both mechanisms exist, both look like "the project's
exclude list", and only one of them is read by this hook — which is why the composed
exclude set is rendered into the managed block as well, and why `docs/spine.md` states it
outright: this block is *where a scaffolded project's exclusions actually take effect*.

### 6. A shared file whose duplicate breaks the file needs its own preflight check

Shared-file duplicates are normally harmless — a project restating a line mbproj also
contributes is redundant, not fatal. `.gitleaks.toml` is the exception, and the preflight
special-cases it:

> The one shared file where a duplicate is not merely redundant. TOML forbids redefining a
> table, so a hand-written `[extend]` beside the block's own makes the file stop parsing —
> and gitleaks then fails *every* commit, on a config error that reads nothing like the
> hand-written line that caused it.

`classify_shared` matches `_TOML_EXTEND` (`^[ \t]*\[extend\]`) anywhere in the file and
reports `DUPLICATE`. Worth generalising: when a generated block is injected into a
project-authored file, ask which of your contributions would be *invalid* rather than
merely repeated in the presence of a hand-written twin — and check for that specific one
before writing.

### 7. Keep provider-specific rules where the provider is used

Scaleway and Tailscale have no rule in the 222-rule default catalogue. Both were written
by hand in `headscale`, **outside** the managed block, and deliberately not promoted into
the plugin. The accepted consequence: other scaffolded projects stay blind to those two
providers until they write their own rules. The alternative — a plugin catalogue of
providers most consumers do not use — contradicts I6 (the plugin ships only generic
tooling; project-specific parameters are never hardcoded).

One known limit is worth carrying into any hand-written rule: a Scaleway *secret* key is a
plain UUID. It is only matched next to its name (`SCW_SECRET_KEY=…`). Matching a bare UUID
would flood the repository with false positives, so it is not matched — an accepted blind
spot, recorded rather than papered over.

## Why This Matters

- **Four of the failure modes here produce a green scan.** No `useDefault`, an over-broad
  allowlist regex, an exclusion written in the wrong file, a test harness that scans a lone
  file — each one ends with the hook passing and nothing being examined. A secret scanner
  is the worst possible place for a silent false negative, because its whole value is the
  absence of findings.
- **Blocking is only sustainable because of `--staged`.** Get that one flag wrong and the
  guard becomes unbearable on the first documentation-heavy repository, gets bypassed, and
  the whole layer is dead weight.
- **The cost asymmetry justifies blocking.** Every other guard in the chain protects
  something `git commit --amend` can fix. A leaked credential costs a history rewrite plus
  a rotation, and the cost starts accruing the moment it is pushed.
- **Ownership of a config file is a durability decision.** Owning `.gitleaks.toml` would
  have worked perfectly until the first re-scaffold silently deleted a project's own rules
  — the failure would surface as a missing detection months later, with nothing linking it
  to the re-run.
- **Composed excludes must be translated, not copied.** The same exclude set feeds three
  syntaxes with different semantics; the one place a mistranslation costs an unscanned
  file is the one that needed the trailing slash and the non-regression test.

## When to Apply

- Adding a secret scanner to any repository, and especially to one with substantial
  existing history or prose — decide diff versus tree before deciding blocking versus
  advisory, because the first determines whether the second is viable.
- A repository is private on a plan without hosted secret scanning: local detection is the
  only layer, not a redundant one.
- A scanner or linter config file exists and the tool reports nothing — verify the config
  extends the defaults rather than replacing them, and verify the tool actually loaded it.
- Translating one exclude list into a second tool's path syntax, particularly glob → regex.
  Check the prefix-versus-directory boundary, and pin it with a match-behaviour test.
- A hook sets `pass_filenames = false` (or otherwise reads the repository itself) — its
  runner's exclude configuration does not apply to it.
- Generating a delimited block into a project-authored config: identify which contribution
  would make the file *invalid* if the project wrote it by hand, and preflight that one.

## Examples

### The measured outcome on `headscale`

- 311 tracked files, 207 of them Markdown. Full-tree scan before the allowlist:
  **1 finding**. After: **0**.
- A real `git commit` carrying three synthetic keys (Tailscale, Scaleway access key,
  GitHub PAT) was **refused**. `HEAD` unchanged; `git log --all` empty for the probe file.
  This is the check that matters — not "the scanner reports a finding", but "the commit
  did not happen".

The single finding was a generic `generic-api-key` hit in `_bmad/_config/files-manifest.csv`,
a vendored BMAD file already inside the manifest's exclude set. Because the composed
allowlist covered it, the rule did **not** have to be disabled — detection was preserved
rather than traded away for quiet. That is the shape to aim for: resolve a false positive
by narrowing the *path*, not by removing the *rule*.

### Detour — a test harness that silently tested the wrong catalogue

The first test of the project-level rules found nothing. The cause was the invocation:

```bash
gitleaks dir probe.md                    # does NOT pick up ./.gitleaks.toml
gitleaks dir probe.md -c .gitleaks.toml  # does — the config must be named
gitleaks dir .                           # does — discovered from the scanned root
```

Given a single file path, gitleaks does not discover `.gitleaks.toml` from the repository
root; `-c/--config` is required. Scanning the root itself (`gitleaks dir .`) — or the hook's
own `gitleaks git --staged` — finds it without the flag.

The trap: a harness that scans a lone file appears to work and silently exercises the
**default** catalogue instead of the project's config. Combined with failure mode 3
(`useDefault`), this is two independent ways to test something other than what runs in
production. Always exercise the guard through the same entry point the hook uses.

### Detour — a synthetic key that was not synthetic enough

The `scaleway-access-key` rule did not fire on the first probe. The probe had 18
characters after `SCW`; the format is `SCW` plus exactly 17. A negative result from a
hand-made test key means the key is wrong at least as often as the rule is.

### Detour — a coverage number that was structurally 100 %

The first engine coverage report read 100 %, and was meaningless. `python3 -m trace --count`
does not mark unexecuted lines unless `--missing` is passed, so the "missed" count could
only ever be zero. With `--missing`, the real figure is **75.2 % (678/901 lines)**, measured
with the stdlib `trace` module because `coverage` was not installed.

Any metric whose failure mode is "structurally cannot report the bad case" belongs in the
same family as the four silent false negatives above — including when the metric is
measuring the guard itself.

## Related

- [`skills/mbproj-scaffold/scripts/mbproj_apply.py`](../../../skills/mbproj-scaffold/scripts/mbproj_apply.py)
  — `_regex_exclude` (the glob→regex translation and why it is asymmetric), `build_gitleaks`
  (the managed block), `build_prek` (hook order, `--staged`, `pass_filenames = false`),
  `shared_plan` and `apply` (the `owns_gitleaks_block` gate).
- [`skills/mbproj-scaffold/scripts/mbproj_layers.py`](../../../skills/mbproj-scaffold/scripts/mbproj_layers.py)
  — the `guards` layer entry: `setup_env_sections`, `_check_gitleaks`, `owns_gitleaks_block`.
- [`skills/mbproj-scaffold/scripts/mbproj_preflight.py`](../../../skills/mbproj-scaffold/scripts/mbproj_preflight.py)
  — `_TOML_EXTEND` and the `.gitleaks.toml` branch of `classify_shared`.
- [`skills/mbproj-scaffold/tests/brownfield_check.py`](../../../skills/mbproj-scaffold/tests/brownfield_check.py)
  — `ALLOWLIST_FORMS` / `check_allowlist_paths`, where the `.git` vs `.github` case is pinned.
- [`docs/spine.md`](../../spine.md) — I3(b) (shared-file delimited block), I7 (owned files
  are rewritten unconditionally), I8 (content composed from the manifest), and the
  `.gitleaks.toml` entry under "Shared-file contributions".
- [`skills/mbproj-scaffold/templates/setup_env/gitleaks.md`](../../../skills/mbproj-scaffold/templates/setup_env/gitleaks.md)
  — install instructions and the escalation order for clearing a false positive
  (`#gitleaks:allow` → a rule outside the managed block → `.gitleaksignore` → `--no-verify`
  last).
- [`docs/solutions/developer-experience/diagnosing-installed-but-broken-tooling.md`](../developer-experience/diagnosing-installed-but-broken-tooling.md)
  — the same shape one level up: a guard that fails *open* produces no error, so nothing
  signals the breakage.
- Issue #17, *"lint_format: vendored dirs are excluded at the repo root only"* (closed,
  fixed in `de59a65`) — the earlier instance of exclude-matching fragility in this
  codebase, and the direct ancestor of the caution in failure mode 4. An exclude that
  matches at the wrong scope has now cost this project twice.
- Commit `b2847d3` — `feat(skill): block secrets before they enter git history`.
