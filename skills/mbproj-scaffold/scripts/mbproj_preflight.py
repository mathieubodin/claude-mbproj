#!/usr/bin/env python3
"""Report what applying would do to a repository, without writing anything.

Applying to a repo that already carries hand-written equivalents of the files mbproj owns
overwrites them with no warning. That is fine for a file mbproj itself generated — that is
what re-entrancy means — but not for one a maintainer wrote. The two are told apart by the
do-not-edit banner: mbproj puts it in everything it writes, so its absence means the file
came from somewhere else.

This module only reads. Deciding what to do about a conflict is the maintainer's call.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import mbproj_apply as apply_mod
import mbproj_writer as writer
from mbproj_layers import LAYER_ORDER

# What applying would do to one owned file.
CREATE = "create"  # absent: nothing to lose
REGENERATE = "regenerate"  # present and mbproj-generated: rewriting is the point
OVERWRITE = "overwrite-handwritten"  # present without the banner: content would be lost
BLOCKED = "blocked"  # applying would fail here, so the repo would end up half-written

# Statuses that must stop an apply.
STOPPERS = (OVERWRITE, BLOCKED)


def _classify_one(target: Path) -> str:
    # A parent that is not a directory makes the write fail mid-run, leaving the repo half
    # applied. `exists()` is false in that case, so without this check it reads as `create`
    # — a green light in front of a crash.
    for parent in target.parents:
        if parent.exists():
            if not parent.is_dir():
                return BLOCKED
            break
    if not target.exists():
        return CREATE
    try:
        # errors="replace" keeps a binary file on an owned path a conflict rather than a
        # crash; OSError covers what that cannot — a directory, or an unreadable file.
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return OVERWRITE
    return REGENERATE if writer.has_banner(text) else OVERWRITE


def classify_owned(repo: Path, state: dict) -> list[dict]:
    """Classify every owned file for this state. Sorted, so the report is stable."""
    return [
        {"path": dest, "status": _classify_one(repo / dest)}
        for dest in sorted(apply_mod.owned_plan(state))
    ]


def report(repo: Path, target_layers, project_name=None, vendored=None) -> dict:
    state = apply_mod.plan_state(repo, target_layers, project_name, vendored)
    owned = classify_owned(repo, state)
    return {
        "repo": str(repo),
        "layers": [n for n in LAYER_ORDER if state["layers"].get(n, {}).get("applied")],
        "owned": owned,
        "conflict_count": sum(1 for r in owned if r["status"] == OVERWRITE),
        "blocked_count": sum(1 for r in owned if r["status"] == BLOCKED),
    }


def render(result: dict) -> str:
    lines = [f"Preflight for {result['repo']}", f"Layers: {', '.join(result['layers'])}", ""]
    width = max((len(r["path"]) for r in result["owned"]), default=0)
    for row in result["owned"]:
        mark = "!" if row["status"] in STOPPERS else " "
        lines.append(f"  {mark} {row['path']:<{width}}  {row['status']}")
    lines.append("")
    if result["conflict_count"]:
        lines.append(
            f"{result['conflict_count']} hand-written file(s) would be overwritten. "
            "Move what you want to keep out of the way, or accept the loss, before applying."
        )
    if result["blocked_count"]:
        lines.append(
            f"{result['blocked_count']} path(s) cannot be written — a parent exists and is "
            "not a directory. Applying would fail part-way through."
        )
    if not (result["conflict_count"] or result["blocked_count"]):
        lines.append("No hand-written file would be overwritten.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="report what applying would do, without writing")
    parser.add_argument("repo", type=Path)
    parser.add_argument("--layer", dest="layers", action="append", default=[],
                        choices=LAYER_ORDER, required=True, help="layer to apply (repeatable)")
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--vendored-dir", dest="vendored", action="append", default=None)
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    # A typo in the path would otherwise produce a green, reassuring report about a
    # repository that does not exist.
    if not repo.is_dir():
        parser.error(f"{args.repo} is not a directory")

    try:
        result = report(repo, args.layers, args.project_name, args.vendored)
    except SystemExit as exc:  # a rejected layer set is a usage error, not a finding
        print(exc, file=sys.stderr)
        return 2
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(render(result))
    # 1 means "applying would lose or fail", 2 means "the question was malformed" — a caller
    # gating on the exit code must be able to tell a finding from a broken invocation.
    return 1 if result["conflict_count"] or result["blocked_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
