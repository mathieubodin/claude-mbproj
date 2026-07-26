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
import mbproj_common as common
from mbproj_layers import LAYER_ORDER

# What applying would do to one owned file.
CREATE = "create"  # absent: nothing to lose
REGENERATE = "regenerate"  # present and mbproj-generated: rewriting is the point
OVERWRITE = "overwrite-handwritten"  # present without the banner: content would be lost

BANNER_MARK = common.BANNER_LINES[0]


def classify_owned(repo: Path, state: dict) -> list[dict]:
    """Classify every owned file for this state. Sorted, so the report is stable."""
    rows = []
    for dest in sorted(apply_mod.owned_plan(state)):
        target = repo / dest
        if not target.exists():
            status = CREATE
        else:
            # errors="replace" so a binary file sitting on an owned path is reported as a
            # conflict rather than crashing the preflight.
            text = target.read_text(encoding="utf-8", errors="replace")
            status = REGENERATE if BANNER_MARK in text else OVERWRITE
        rows.append({"path": dest, "status": status})
    return rows


def report(repo: Path, target_layers, project_name=None, vendored=None) -> dict:
    state = apply_mod.plan_state(repo, target_layers, project_name, vendored)
    owned = classify_owned(repo, state)
    conflicts = [r for r in owned if r["status"] == OVERWRITE]
    return {
        "repo": str(repo),
        "layers": [n for n in LAYER_ORDER if state["layers"].get(n, {}).get("applied")],
        "owned": owned,
        "conflict_count": len(conflicts),
    }


def render(result: dict) -> str:
    lines = [f"Preflight for {result['repo']}", f"Layers: {', '.join(result['layers'])}", ""]
    width = max((len(r["path"]) for r in result["owned"]), default=0)
    for row in result["owned"]:
        mark = "!" if row["status"] == OVERWRITE else " "
        lines.append(f"  {mark} {row['path']:<{width}}  {row['status']}")
    lines.append("")
    if result["conflict_count"]:
        lines.append(
            f"{result['conflict_count']} hand-written file(s) would be overwritten. "
            "Move what you want to keep out of the way, or accept the loss, before applying."
        )
    else:
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

    result = report(args.repo.resolve(), args.layers, args.project_name, args.vendored)
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(render(result))
    # Non-zero on conflicts, so a caller can gate on it.
    return 1 if result["conflict_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
