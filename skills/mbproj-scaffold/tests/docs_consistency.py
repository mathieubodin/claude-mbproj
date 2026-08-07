#!/usr/bin/env python3
"""Hold the human-facing documentation against the engine, so it cannot drift silently.

The other checks prove the engine behaves. This one proves the documents that describe it
still say what it does — a different failure, and the one nothing else catches: a release can
be correct, tested, and lint-clean while `README.md` describes the version before it.

That is not hypothetical. Shipping gitleaks touched the engine, the generated `SETUP_ENV.md`
and the design spine, and left `README.md` and `docs/adoption.md` describing a socle without
it. Every guard the project had stayed green, because each one looks at the diff, the tests or
the lint, and a stale document is wrong in none of those ways.

So the facts checked here are only the ones derivable from the engine itself. A document is
compared against the layer registry and the preflight's own constants, never against a second
copy of the truth — a checklist that has to be kept in step with the code is the very thing
that failed.

What this cannot catch: prose that is wrong without being incomplete. `README.md` naming every
shared file and still describing what they do incorrectly passes here. Reviewing remains a
human job; this only removes the class of drift a machine can see.

Run: python3 skills/mbproj-scaffold/tests/docs_consistency.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import mbproj_apply as apply_mod  # noqa: E402
import mbproj_manifest as manifest  # noqa: E402
import mbproj_preflight as preflight  # noqa: E402

ADOPTION = REPO / "docs" / "adoption.md"
README = REPO / "README.md"

# A semantic version written out in full. The README used to carry one, and nothing kept it in
# step with `plugin.json`: it sat two releases behind for weeks. Versions belong in the
# manifests and the changelog, which are generated from the release itself.
_SEMVER = re.compile(r"\bv?\d+\.\d+\.\d+\b")


def full_state() -> dict:
    """Every layer applied — the widest set of files the engine can ever write."""
    state = manifest.default_state()
    for name in manifest.LAYER_ORDER:
        state["layers"][name] = {"applied": True, "version": state["plugin_version"]}
    state["params"]["project_name"] = "docs-consistency"
    return state


def check_statuses_documented(text: str, fail) -> None:
    """Every status a report can hand a maintainer is explained where they will look."""
    statuses = set(preflight.STOPPERS) | set(preflight.SHARED_FINDINGS) | {preflight.UNREADABLE}
    missing = sorted(s for s in statuses if s not in text)
    if missing:
        fail(f"docs/adoption.md names no finding status {missing} the preflight can report")


def check_shared_files_have_a_cost(state: dict, fail) -> None:
    """A shared file the engine writes to can collide, and a collision costs something.

    `SHARED_CONSEQUENCES` is what the report prints to say what. A file missing from it is
    reported with a bare status and no consequence — which is how a duplicate that breaks
    every commit read exactly like one that costs nothing.
    """
    for path in sorted(apply_mod.shared_plan(state)):
        if path not in preflight.SHARED_CONSEQUENCES:
            fail(f"{path} is written as a shared file but has no entry in SHARED_CONSEQUENCES")


def check_shared_files_documented(state: dict, text: str, fail) -> None:
    """Adopting a repository means reconciling its shared files, one by one.

    A file absent from `docs/adoption.md` is one the maintainer is never told to look at.
    """
    missing = sorted(p for p in apply_mod.shared_plan(state) if p not in text)
    if missing:
        fail(f"docs/adoption.md never mentions the shared file(s) {missing}")


def check_readme_states_no_version(text: str, fail) -> None:
    """Released versions live in the changelog, which the release itself regenerates."""
    for match in sorted(set(_SEMVER.findall(text))):
        fail(f"README.md pins the version {match!r}; nothing keeps it in step with plugin.json")


def main() -> int:
    failures: list[str] = []

    def fail(message: str) -> None:
        failures.append(message)

    state = full_state()
    adoption = ADOPTION.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    check_statuses_documented(adoption, fail)
    check_shared_files_have_a_cost(state, fail)
    check_shared_files_documented(state, adoption, fail)
    check_readme_states_no_version(readme, fail)

    for message in failures:
        print(f"FAIL {message}", file=sys.stderr)
    print(f"docs_consistency: {'FAILED' if failures else 'ok'} ({len(failures)} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
