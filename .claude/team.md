# Agent team

The two teammates that validate every change to `mbproj-scaffold`, and the session
configuration they require. Established empirically on 2026-07-26; the full findings behind
each rule live in MemPalace (`outillage/dev-workflow`, "ÉQUIPES D'AGENTS").

## Session prerequisites

Both are read at **startup** — neither can be set from inside a running session.

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` (a string) in the `env` block of
  `~/.claude/settings.json`.
- Each teammate's repository passed as `--add-dir`, which is what lets it work **in its own
  repo** rather than on a copy:

  ```bash
  claude --add-dir /home/mathieu/dev/github.com/claude-code-monitoring \
         --add-dir /home/mathieu/dev/github.com/headscale
  ```

Activation witness: `~/.claude/teams/session-XXXXXXXX/config.json` exists. If it does not,
the feature is off — `echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` proves nothing, since the
app reads settings.json without exporting to the shell. To enable it on a conversation
already under way, `claude --continue` restarts the process and restores the conversation.

## The two teammates

Spawned with the `Agent` tool, `subagent_type: "claude"`, no model override.

| Name | Repository | Ground it validates |
| --- | --- | --- |
| `monitoring` | `claude-code-monitoring` | brownfield — a real project, adopted at `ed8b2f9` |
| `headscale` | `headscale` | greenfield — all four layers scaffolded, project not started |

Reuse these names. A teammate is addressed by name through `SendMessage`, which resumes it
from its transcript, so a follow-up mission never needs a fresh spawn.

## What a working prompt must carry

Four clauses, each answering a failure observed on both teammates at once:

1. **Conventions.** "Read `<repo>/CLAUDE.md` and apply *its* conventions, not the current
   directory's." A teammate starts in the **lead's** cwd with the **lead's** CLAUDE.md; its
   own repo's instructions are never injected. Skills from `--add-dir` repositories *are*
   aggregated — tooling is inherited, instructions are not.
2. **Self-contained.** It inherits none of the lead's conversation. Paths, commits, expected
   results: all of it goes in the prompt.
3. **Report back.** "When you are done, send your report to `team-lead` via `SendMessage`."
   A teammate that finishes its turn goes idle and its work stays in its own transcript. The
   idle notification carries no content. Without this clause the work is simply lost.
4. **Escalate.** "If you hit a decision that is not yours, send it to `team-lead` rather than
   settling it yourself."

Keep the shape used so far: an opening line stating it is a teammate, a bold **TON REPO**,
numbered steps, a Constraints section, and a demand for concision.

## Limits worth remembering

- One team per session, not shareable across sessions; `/resume` does not restore in-process
  teammates. A new session re-spawns both.
- Mailboxes (`~/.claude/teams/{team}/inboxes/{agent}.json`) are created lazily and consumed
  on delivery — there is no readable message history afterwards.
- Two teammates editing the same file overwrite each other; keep their grounds disjoint.
- Writing inside an `--add-dir` repository raises **no** permission prompt: `--add-dir` is
  the authorisation. Constraints on what they may touch must be stated in the prompt.
- Token cost is linear in the number of running instances.
