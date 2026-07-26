#!/usr/bin/env python3
"""Report what applying would do to a repository, without writing anything.

A repo that already carries hand-written equivalents of what mbproj brings is at risk in two
different ways, and the report keeps them apart.

An **owned** file is rewritten in full, so content is lost. That is fine for a file mbproj
itself generated — that is what re-entrancy means — but not for one a maintainer wrote. The
two are told apart by the do-not-edit banner: mbproj puts it in everything it writes, so its
absence means the file came from somewhere else.

A **shared** file is only added to, so nothing is lost; the risk is that the project ends up
stating the same thing twice — a `lint` recipe in the Makefile and in `mbproj.mk`, a tool
section written by hand and again in the managed block. What a previous run wrote is excluded
first, so an already-adopted repo does not report itself as duplicating itself.

This module only reads. Deciding what to do about a finding is the maintainer's call —
removing superseded content is an editorial act, so the tool reports and stops there.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import mbproj_apply as apply_mod
import mbproj_shared as shared
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


# What applying would find in one shared file. Nothing here loses content — mbproj appends
# to shared files rather than owning them — so these are findings to resolve, not stoppers.
CREATE_SHARED = "create"  # absent: mbproj seeds it
MERGE = "merge"  # present, and nothing it carries by hand overlaps
DUPLICATE = "duplicate"  # the project already states, by hand, what the block would add
COLLISION = "collision"  # the project defines make targets `mbproj.mk` also defines
REVIEW = "review"  # prose that plausibly covers what the imports carry — a human decides

SHARED_FINDINGS = (DUPLICATE, COLLISION, REVIEW)

_FENCE = re.compile(r"^\s*(?:```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TARGET = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.\-]*)\s*::?(?!=)")
# Words that carry no distinguishing meaning in a heading; dropping them is what lets
# "When adding a feature" recognise itself in "When Adding Features".
_STOPWORDS = frozenset({"a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "with"})


def _make_targets(text: str) -> set[str]:
    """Target names defined in a Makefile, ignoring directives and variables."""
    return {m.group(1) for line in text.splitlines() if (m := _TARGET.match(line))}


def _headings(text: str, levels: tuple[int, ...] = (2,)) -> list[str]:
    """Headings of the given levels, lower-cased, in order of appearance.

    Fenced blocks are skipped: a `## ` inside a shell snippet is a comment, and counting it
    as a heading would invent duplication out of documentation that merely shows commands.
    """
    found: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and (m := _HEADING.match(line)) and len(m.group(1)) in levels:
            found.append(m.group(2).lower())
    return found


def _tokens(title: str) -> frozenset[str]:
    """A heading reduced to the words that carry its meaning.

    Naive singularisation and stop-word removal, nothing cleverer: this decides whether to
    *ask* a maintainer to compare two headings, so a rough match that occasionally points at
    unrelated prose costs a glance, while exact comparison would miss every real case.
    """
    words = re.findall(r"[a-z0-9]+", title.lower())
    stems = {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words}
    return frozenset(stems - _STOPWORDS)


def _section_title(key: str) -> str:
    """The heading a SETUP_ENV section template actually carries, read from the template."""
    text = (apply_mod.TEMPLATES_DIR / "setup_env" / f"{key}.md").read_text(encoding="utf-8")
    titles = _headings(text)
    return titles[0] if titles else key.lower()


def _prose_overlaps(text: str, state: dict, imports: list[str]) -> list[dict]:
    """Project headings that plausibly already cover the prose the CLAUDE.md imports carry.

    The imports are one line each, so nothing can be compared literally — the question is
    whether the project already says, in its own words, what the imported file says. That is
    a judgement, and this only nominates candidates: `Code Standards & Patterns` against the
    imported `Code standards`. The maintainer decides whether the two really overlap.
    """
    present = _headings(text, levels=(1, 2, 3))
    owned = apply_mod.owned_plan(state)
    overlaps = []
    for item in imports:
        dest = item.lstrip("@")
        prose = owned.get(dest)
        if prose is None:  # an import whose satellite this layer set does not write
            continue
        for title in _headings(prose, levels=(1, 2)):
            wanted = _tokens(title)
            match = next((h for h in present if wanted and wanted <= _tokens(h)), None)
            if match:
                overlaps.append({"incoming": title, "heading": match, "from": dest})
    return overlaps


def classify_shared(repo: Path, state: dict) -> list[dict]:
    """Report what applying would add to each shared file, and what already looks present.

    Exactness differs per file and the report says which it is, rather than flattening the
    two into one confident-looking verdict. Make targets, section headings and ignore lines
    are compared literally, so a finding there is a fact. CLAUDE.md prose can only be
    compared by nomination (`_prose_overlaps`), so it is reported as `review`.
    """
    rows = []
    for path, entry in apply_mod.shared_plan(state).items():
        target = repo / path
        items = entry["items"]
        if not items:
            continue
        row = {"path": path, "kind": entry["kind"], "adds": len(items), "findings": []}
        if not target.exists():
            row["status"] = CREATE_SHARED
        else:
            text = target.read_text(encoding="utf-8", errors="replace")
            if entry["block_style"]:
                text = shared.strip_block(text, entry["block_style"])
            row["status"] = MERGE
            if path == "Makefile":
                mk = apply_mod.owned_plan(state).get("mbproj.mk", "")
                collisions = sorted(_make_targets(text) & _make_targets(mk))
                if collisions:
                    row.update(status=COLLISION, findings=collisions)
            elif path == "CLAUDE.md":
                overlaps = _prose_overlaps(text, state, items)
                if overlaps:
                    row.update(status=REVIEW, findings=overlaps)
            elif path == "SETUP_ENV.md":
                present = set(_headings(text))
                dupes = sorted(t for t in (_section_title(k) for k in items) if t in present)
                if dupes:
                    row.update(status=DUPLICATE, findings=dupes)
            elif path == ".gitignore":
                lines = {ln.strip() for ln in text.splitlines()}
                dupes = sorted(i for i in items if i in lines)
                if dupes:
                    row.update(status=DUPLICATE, findings=dupes)
        rows.append(row)
    return rows


def classify_owned(repo: Path, state: dict) -> list[dict]:
    """Classify every owned file for this state. Sorted, so the report is stable."""
    return [
        {"path": dest, "status": _classify_one(repo / dest)}
        for dest in sorted(apply_mod.owned_plan(state))
    ]


def report(repo: Path, target_layers, project_name=None, vendored=None) -> dict:
    state = apply_mod.plan_state(repo, target_layers, project_name, vendored)
    owned = classify_owned(repo, state)
    sharing = classify_shared(repo, state)
    return {
        "repo": str(repo),
        "layers": [n for n in LAYER_ORDER if state["layers"].get(n, {}).get("applied")],
        "owned": owned,
        "shared": sharing,
        "conflict_count": sum(1 for r in owned if r["status"] == OVERWRITE),
        "blocked_count": sum(1 for r in owned if r["status"] == BLOCKED),
        "shared_finding_count": sum(len(r["findings"]) for r in sharing),
    }


def _render_finding(row: dict, finding) -> str:
    if row["path"] == "CLAUDE.md":
        return f"\"{finding['heading']}\" may already cover \"{finding['incoming']}\""
    return str(finding)


def render(result: dict) -> str:
    lines = [f"Preflight for {result['repo']}", f"Layers: {', '.join(result['layers'])}", ""]
    lines.append("Owned files — rewritten in full:")
    width = max((len(r["path"]) for r in result["owned"]), default=0)
    for row in result["owned"]:
        mark = "!" if row["status"] in STOPPERS else " "
        lines.append(f"  {mark} {row['path']:<{width}}  {row['status']}")

    lines += ["", "Shared files — added to, never rewritten:"]
    width = max((len(r["path"]) for r in result["shared"]), default=0)
    for row in result["shared"]:
        mark = "!" if row["status"] in SHARED_FINDINGS else " "
        count = f" ({len(row['findings'])})" if row["findings"] else ""
        lines.append(
            f"  {mark} {row['path']:<{width}}  {row['status']}{count}"
            f"  [{row['adds']} {row['kind']}]"
        )
        # The list is the finding: "8 collisions" tells a maintainer nothing about which
        # targets to reconcile, and reconciling is the whole point of the report.
        lines += [f"      - {_render_finding(row, f)}" for f in row["findings"]]

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
    if result["shared_finding_count"]:
        lines.append(
            f"{result['shared_finding_count']} finding(s) in shared files. Nothing is lost "
            "there — mbproj adds to them — but the project would carry the same thing twice. "
            "Removing the superseded copy is an editorial call, so it is left to you."
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
    # Shared-file findings deliberately stay out of it: they lose nothing, and `review` is a
    # nomination for a human, not a fact. A caller that wants to gate on them reads --json.
    return 1 if result["conflict_count"] or result["blocked_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
