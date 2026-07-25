---
title: "Installed is not working — diagnosing silently broken CLI tools and plugins"
date: 2026-07-25
category: developer-experience
module: developer-tooling
problem_type: developer_experience
component: tooling
severity: high
related_components:
  - development_workflow
  - documentation
applies_when:
  - A tool reports success or is listed as installed yet behaves wrongly
  - An error message names a different tool than the one you invoked
  - A hook or wrapper rewrites commands before they reach the shell
  - Writing a shell guard that greps another tool's human-facing output
  - About to ship a local workaround or file an upstream bug
symptoms:
  - npx invocations fail with an Unknown command error and an npm help footer, an npm error for an npx call
  - claude plugin details lists the skill but the slash command resolves to Unknown skill
  - claude plugin list shows the plugin disabled while its cache directory is fully populated
  - An anchored grep idempotency guard never matches the real indented CLI output, so the install step re-runs every pass
  - A config workaround restores the happy path while hiding that upstream already shipped the real fix
root_cause: incomplete_setup
resolution_type: workflow_improvement
tags:
  - rtk
  - npx-hook
  - claude-code-plugins
  - stale-dependency
  - plugin-enablement
  - guard-regex
  - diagnosis-checklist
  - environment-state
---

## Context

Three separate incidents in a single day shared one shape: a third-party CLI or plugin
was *present*, so it was assumed to be *working*, and the first reflex was to write a
workaround around the strange behaviour instead of establishing what the tool was
actually doing and which version it was.

- An `npx` invocation failed with an **npm** error message. The tool was installed; a
  hook was silently running the wrong binary. The installed version was three months
  behind a release that fixed exactly this.
- A slash command was "Unknown skill" while the plugin's own detail command listed it
  and its files sat in the plugin cache. The plugin was installed but disabled.
- A shell guard meant to make an install step idempotent never matched, because it was
  written against an imagined `claude plugin list` output format. Its test exercised a
  paraphrase of the guard rather than the string that shipped.

In all three cases the cheap, decisive check — *what actually ran*, *what version is
actually installed*, *what does the command actually print* — was skipped, and the
expensive path (workaround, duplicate bug report, broken idempotency) was taken first.

## Guidance

### 1. Prove which binary actually ran (identity check, not presence check)

"The command exists" and "the package is installed" prove nothing about what executed.
Wrappers, hooks, shims, shell aliases, and `PATH` order can all substitute a different
binary. The one reliable probe is an **identity check**: run the tool and compare the
version it reports against the version that tool is known to have.

The npx incident resolved in two commands:

```bash
rtk npx cowsay --version              # -> 11.12.1  (that is npm's version, not cowsay's)
rtk proxy npx --yes cowsay --version  # -> 1.6.0    (the real cowsay)
```

`cowsay` is not at 11.12.1 and never was. The mismatch identified the running binary as
npm, which turned a vague "the command fails" into a precise, one-line root cause. The
original error message carried the same clue and it was almost missed:

```text
Unknown command: "bmad-method"
To see a list of supported npm commands, run: npm help
```

An **npm** error surfacing from an **npx** invocation is a substitution signal. When an
error message names a different tool than the one you invoked, stop and identify the
binary before doing anything else.

Pick a probe package whose version you can predict and that differs from the suspected
impostor's — a probe whose version could plausibly belong to either tool proves nothing.

### 2. Compare the installed version to upstream *before* writing any workaround

Once the misbehaviour is characterised, the next step is not a fix — it is three
questions about upstream:

1. What version is installed, and what is the latest release?
2. Does the upstream CHANGELOG mention this behaviour between the two?
3. Is there already an open issue describing it?

In the npx case: installed `0.37.2`, latest `0.43.0`. The CHANGELOG entry
`fix(npx): dispatch unknown tools to npx instead of npm` shipped in **0.38.0**
(2026-04-29, closes #815) — the installed version was the last one *before* the fix, three
months stale. The correct fix was an upgrade through the project's official,
checksum-verified installer, not a config hack. And an open upstream issue (#1849)
already described the identical bug on 0.37.2, so searching first avoided filing a
duplicate.

### 3. Treat a workaround as temporary, and actually revert it

A workaround that masks a stale version is a liability, not a fix. The first response to
the npx failure was to disable the rewrite entirely:

```toml
[hooks]
exclude_commands = ["npx"]
```

It worked — and it permanently forfeited the tool's `npx` output filtering, a token-cost
regression, while leaving the buggy version installed. Workarounds like this outlive the
bug they route around because nothing ever prompts anyone to revisit them.

So: when you apply a workaround, record what it works around and what condition retires
it. When the upstream fix lands, upgrade, re-test the original symptom **and** the
behaviour the workaround suppressed, then delete the workaround. In this case that meant
re-checking `rtk npx cowsay --version` → `1.6.0`, confirming known-tool routing still
worked, and removing the `exclude_commands` entry to recover the filtering.

### 4. Human-readable CLI output is not a stable contract

When you must parse a CLI's text output, assume only that the meaningful token appears
somewhere on the line. Do not assume where.

The scaffolder guarded its install step with:

```bash
claude plugin list 2>/dev/null | grep -q '^compound-engineering'
```

Real output indents each entry and prefixes it with a status marker, so the entry line is
not flush-left and `^` never matched. The guard silently always fell through — meaning
`claude plugin install` re-ran on *every* application, destroying the idempotency the
guard existed to provide. A failing guard that fails *open* produces no error, so nothing
signals the breakage.

Practical rules:

- Avoid `^` anchors and column/field-position assumptions on human-readable output.
- Match the most specific unambiguous token you can — here the fully qualified plugin id
  `compound-engineering@compound-engineering-plugin`, not a bare prefix.
- Prefer a machine-readable mode when the tool offers one (`--json`, `--porcelain`,
  `--format=…`) and parse that instead.
- Remember that appearing in a listing does not mean the thing is active. **Installed is
  not enabled**, and a details command will happily describe a component that is not
  loaded.

### 5. Test the exact string you ship, never a paraphrase

The broken guard had been verified — with an *unanchored* variant of the command rather
than the exact line committed to `SKILL.md`. The test passed and the shipped text was
broken. A verification that retypes the artifact tests the retyping, not the artifact.

For any shell snippet, regex, or command embedded in a document or template, extract the
literal string from the file and execute *that*, or assert on the file's byte content.
Never hand-copy it into the test.

## Why This Matters

- **A workaround costs more than it looks like.** The npx `exclude_commands` entry
  silently gave up the filtering that was the reason for using the proxy at all. The
  visible symptom disappeared; a quiet, permanent regression replaced it.
- **Stale versions accumulate invisibly.** The fix shipped in the very next release, three
  months earlier, and the installed build sat five releases behind the latest. Nothing in
  the failure said "you are out of date" — only a deliberate version-versus-upstream
  comparison surfaced it.
- **Guards that fail open are worse than no guard.** The `^`-anchored `grep` looked like
  idempotency protection while providing none, and it produced no error to notice.
- **Duplicate effort is the default outcome.** Upstream had already filed and fixed the
  npx bug. Ten seconds of searching replaced a debugging session and a duplicate issue.
- **Presence checks give false confidence.** "The plugin is listed", "the command
  exists", "the files are in the cache" were all true while the thing was disabled or
  substituted. Only identity and state checks distinguish present from working.

## When to Apply

Apply this before writing any workaround, and specifically when:

- A command fails with an error message that names a **different** tool than the one you
  invoked.
- A tool is installed and on `PATH`, yet behaves as if it were not, or produces output
  the documentation does not describe.
- A plugin, extension, or skill is "not found" while inspection commands list it.
- Any wrapper, proxy, hook, shim, or alias sits between your command and the real binary
  — that is exactly where substitutions hide.
- You are about to add a config exclusion, an environment variable, a `|| true`, or a
  retry to make a symptom go away.
- You are writing a shell guard that parses another tool's human-readable output.
- You are writing a test for a command string that lives inside a document or template.

## Examples

### Instance A — stale version, fix already upstream

Symptom, with the substitution clue in plain sight:

```text
$ npx --yes bmad-method install --directory . --modules bmm --tools claude-code --yes
Unknown command: "bmad-method"
To see a list of supported npm commands, run: npm help
```

Mechanism: a `PreToolUse` hook rewrote every `npx …` into `rtk npx …`. In rtk 0.37.2 the
`npx` subcommand routed only known tools (tsc, eslint, prisma) to specialized filters and
**silently fell back to `npm`** for anything else — running the wrong binary instead of
failing loudly.

Identity check that settled it:

```bash
rtk npx cowsay --version              # 11.12.1  -> npm's version
rtk proxy npx --yes cowsay --version  # 1.6.0    -> the real cowsay
```

Version check that replaced the workaround with a fix: installed `0.37.2`, latest
`0.43.0`, CHANGELOG entry `fix(npx): dispatch unknown tools to npx instead of npm` in
`0.38.0` (2026-04-29, closes #815); upstream issue #1849 already described the bug on
0.37.2. Resolution: upgrade via the official checksum-verified installer, re-test, then
**remove** the `exclude_commands = ["npx"]` workaround to recover the npx filtering.

### Instance B — installed, but disabled

`/ce-compound` was "Unknown skill" for both human and agent, while
`claude plugin details compound-engineering` listed 29 skills including `ce-compound`
and the files sat in the plugin cache. The state check found it:

```bash
claude plugin list          # Status: disabled
```

`~/.claude/settings.json` confirmed it:

```json
{
  "enabledPlugins": {
    "compound-engineering@compound-engineering-plugin": false
  }
}
```

Fix, in order — enabling alone is not enough, since plugins load at session start:

```bash
claude plugin enable compound-engineering@compound-engineering-plugin
# then, in-session:
/reload-plugins
```

Note that "disabled" is not necessarily an accident: `claude plugin details` reports the
per-component token cost, and this plugin adds roughly **2,292 always-on tokens to every
session**. Someone may have turned it off deliberately, so confirm intent before
re-enabling something shared.

Reusable ordering when a plugin skill is missing:

1. **Disabled?** `claude plugin list` → check Status, then
   `claude plugin enable <plugin>@<marketplace>`.
2. **Stale session?** `/reload-plugins`, or restart the session.
3. **Actually absent?** `claude plugin marketplace add <owner/repo>`, then
   `claude plugin install <plugin>@<marketplace>`.

### Instance C — a guard written against imagined output

Broken guard in `skills/mbproj-scaffold/SKILL.md`:

```bash
claude plugin list 2>/dev/null | grep -q '^compound-engineering'
```

The real listing indents entries behind a status marker, so the `^` anchor never matched,
the "skip when already installed" branch never fired, and the install re-ran on every
application. Fixed in commit `34d7f70` by matching the fully qualified id anywhere on the
line:

```bash
claude plugin list 2>/dev/null | grep -q 'compound-engineering@compound-engineering-plugin'
```

The installed-but-disabled case from Instance B was documented alongside it, in both
`SKILL.md` and the generated `SETUP_ENV.md` section, so the guard's remaining blind spot
is at least visible to a reader.

Why it shipped broken: the unit's verification ran an **unanchored variant** of the guard
instead of the exact string committed to `SKILL.md`. Green test, broken artifact.

One thing did work as designed — the repo's pre-commit hook (`make lint`) rejected the fix
commit for an unrelated Markdown violation (MD038, spaces inside a code span). Automated
guard chains catch what review misses, which is precisely why a guard that silently fails
open is so costly.

## Related

- [`skills/mbproj-scaffold/SKILL.md`](../../../skills/mbproj-scaffold/SKILL.md) — carries
  the corrected guard, the note on why an anchored `^` never matches indented
  `claude plugin list` output, and the `claude plugin enable` remedy.
- [`skills/mbproj-scaffold/templates/setup_env/agentic-tooling.md`](../../../skills/mbproj-scaffold/templates/setup_env/agentic-tooling.md)
  — the user-facing counterpart of the same guidance; a reader fixing one must check the
  other, since the guard string itself lives only in `SKILL.md`.
- [`.claude/rules/markdown.md`](../../../.claude/rules/markdown.md) — the repo's existing
  "verify before declaring done" rule; this learning generalizes it from linters to
  third-party CLIs, version checks, and shell guards.
- [`CONTRIBUTING.md`](../../../CONTRIBUTING.md) — the verification contract, which
  currently exercises the Python engine's idempotency but not the shell guards embedded in
  `SKILL.md`.
- [`docs/spine.md`](../../spine.md) — invariant I1 (idempotent and non-destructive) is what
  the broken guard violated; the `agentic` section is the design context for a layer that
  orchestrates external installs.
- [`SETUP_ENV.md`](../../../SETUP_ENV.md) — documents the external hook layer (a global
  `core.hooksPath`) that made the npx interception possible.
- [`.claude/rules/makefile.md`](../../../.claude/rules/makefile.md) — ranks `npx` last for
  tool acquisition; this incident is concrete evidence for why, since an npx invocation can
  be intercepted and silently redispatched.
- Issue [#7](https://github.com/mathieubodin/claude-mbproj/issues/7) — the unit that
  produced the defective guard; its acceptance criterion "applying `agentic` is idempotent
  (no double-install)" was marked met while the shipped guard never matched.
