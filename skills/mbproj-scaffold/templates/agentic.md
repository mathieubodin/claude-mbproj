# Agentic Workflow

This project's agentic development uses a spec-first backbone (BMAD-Method) with a
knowledge-capture layer (compound engineering).

## Backbone: BMAD-Method

Plan spec-first at **milestone granularity**: run `bmad-prd` + `bmad-architecture` once per
milestone or epic, then `bmad-create-story` then `bmad-dev-story` per unit. Small fixes
short-circuit the chain (direct implementation, or `bmad-quick-dev`). Do not use `bmad-loop`
(autonomy orchestration) unless explicitly chosen.

## Gate: documentation review

**Always review the documentation before pushing.** Run `bmad-review-adversarial-general` over
the human-facing documents — `README.md`, `CONTRIBUTING.md`, `SETUP_ENV.md`, `docs/**` — with
`also_consider` set to: every checkable claim is verified against the code, not against another
document; the documents the diff did *not* touch are the priority, since that is where drift
lives; hand-written version numbers and feature lists are the two recurring failures. Then run
`bmad-editorial-review-prose` on whatever you rewrote — it never challenges content, so it is
the readability pass and not the accuracy one.

This is a gate, not a step: a change whose documentation was not reviewed does not leave the
repository. Nothing else in this chain covers it — BMAD plans what to build, compound
engineering records what was learned; neither asks whether the README still tells the truth.

## Capture: compound engineering

After implementation, run `ce-compound` then `ce-kg` to distill the solution into memory.
Compound engineering is a **capture layer only** — not planning. Do not use `ce-brainstorm`
or `ce-plan`; the BMAD chain covers the WHAT and HOW.

## Artifact policy

BMAD planning artifacts under `_bmad-output/` are committed for traceability — a project-level
override of the global "plan/brainstorm files are never committed" rule. Memory retains only
the durable decisions and `ce-kg` triplets, not a copy of the BMAD documents.
