# Agentic Workflow

This project's agentic development uses a spec-first backbone (BMAD-Method) with a
knowledge-capture layer (compound engineering).

## Backbone: BMAD-Method

Plan spec-first at **milestone granularity**: run `bmad-prd` + `bmad-architecture` once per
milestone or epic, then `bmad-create-story` then `bmad-dev-story` per unit. Small fixes
short-circuit the chain (direct implementation, or `bmad-quick-dev`). Do not use `bmad-loop`
(autonomy orchestration) unless explicitly chosen.

## Capture: compound engineering

After implementation, run `ce-compound` then `ce-kg` to distill the solution into memory.
Compound engineering is a **capture layer only** — not planning. Do not use `ce-brainstorm`
or `ce-plan`; the BMAD chain covers the WHAT and HOW.

## Artifact policy

BMAD planning artifacts under `_bmad-output/` are committed for traceability — a project-level
override of the global "plan/brainstorm files are never committed" rule. Memory retains only
the durable decisions and `ce-kg` triplets, not a copy of the BMAD documents.
