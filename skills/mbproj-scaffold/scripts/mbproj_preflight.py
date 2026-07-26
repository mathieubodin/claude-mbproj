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
    # A directory on an owned path is not content to weigh up but a write that cannot happen:
    # applying dies on it and leaves a `.mbproj-tmp` orphan behind. Reporting it as content
    # that would be overwritten tells the maintainer to accept a loss that never occurs, and
    # hides the one thing that matters — the run stops here, half applied.
    if target.is_dir():
        return BLOCKED
    try:
        # errors="replace" keeps a binary file on an owned path a conflict rather than a
        # crash; OSError covers what that cannot — an unreadable file.
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

UNREADABLE = "unreadable"  # a shared file applying cannot read, so applying stops there

# Up to three *spaces* of indent, never a tab: in CommonMark a leading tab opens an indented
# code block, so `\s` here would read a heading inside a code sample as a real one. Fence
# tracking itself lives in mbproj_shared, shared with the writer.
# ATX headings, closing hashes stripped: `## jq ##` is the same heading as `## jq`.
_HEADING = re.compile(r"^[ ]{0,3}(#{1,6})\s+(.+?)(?:\s+#+)?\s*$")
# The underline of a setext heading — `jq` over `--` is an H2, and carries the same anchor.
_SETEXT = re.compile(r"^[ ]{0,3}(=+|-+)[ \t]*$")
# An assignment, in every flavour make accepts. Recognised first and skipped, so `VAR ::= x`
# is never mistaken for a rule on a target named VAR.
_ASSIGN = re.compile(r"^\s*[^:=#]+\s*(?::{1,3}=|[?+!]=)")
# The left-hand side of a rule: everything before the colon, on a line that is not a recipe
# (recipes are tab-indented) and not a directive.
_RULE = re.compile(r"^ {0,7}([^:=#]+?)\s*::?(?!=)")
_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*\Z")
# Words that carry no distinguishing meaning in a heading; dropping them is what lets
# "When adding a feature" recognise itself in "When Adding Features".
_STOPWORDS = frozenset({"a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "with"})


def _logical_lines(text: str) -> list[str]:
    """Makefile lines with backslash continuations joined, as make itself reads them."""
    lines: list[str] = []
    pending = ""
    for raw in text.splitlines():
        if raw.endswith("\\"):
            pending += raw[:-1].rstrip() + " "
            continue
        lines.append(pending + raw)
        pending = ""
    if pending:
        lines.append(pending)
    return lines


def _make_targets(text: str) -> set[str]:
    """Target names defined in a Makefile, ignoring directives, variables and patterns.

    Reads the left-hand side whole rather than the first word: `lint build:` defines *two*
    targets, and `build package:` is a common enough idiom that missing it would hide exactly
    the collisions this report exists to surface. Only what a rule can actually collide on is
    kept — pattern rules (`%.o`), variable references and `.PHONY`-style dot-directives name
    nothing `mbproj.mk` defines.

    Two things are read literally rather than evaluated, and both are deliberate. Targets a
    third-party `include` brings in are not resolved — beyond the cost of following variabled
    and optional includes, an adopted repo's Makefile is often just `include mbproj.mk`, so
    resolving it would report every generic target as colliding with itself. And a rule
    guarded by a false `ifeq` is still reported, since knowing it is dead means evaluating the
    variables. The first errs towards missing a collision, the second towards naming one that
    make would never reach; neither misreports what the file literally says.
    """
    found = set()
    in_define = False
    for line in _logical_lines(text):
        head = line.strip().split(None, 1)[0] if line.strip() else ""
        if in_define:
            in_define = head != "endef"
            continue
        if head == "define":
            # A `define USAGE … endef` block routinely holds help text whose lines read
            # `build: compile everything`. make stores that as a variable's value; treating
            # the body as rules invents a collision on every target the help mentions.
            in_define = True
            continue
        if line.startswith("\t") or _ASSIGN.match(line):
            continue
        match = _RULE.match(line)
        if not match:
            continue
        left = match.group(1)
        # `$(info build: starting)` is a function call make evaluates, not a rule — but it
        # carries a colon, so the left-hand side splits into something that looks like a
        # target name. Anything with a variable reference in it is beyond what can be read
        # without evaluating the makefile, so it is skipped rather than guessed at.
        if "$" in left:
            continue
        found.update(n for n in left.split() if _NAME.match(n))
    return found


def _headings(text: str, levels: tuple[int, ...] = (2,)) -> list[str]:
    """Headings of the given levels, lower-cased, in order of appearance.

    Fenced blocks are skipped: a `## ` inside a shell snippet is a comment, and counting it
    as a heading would invent duplication out of documentation that merely shows commands.
    """
    found: list[str] = []
    lines = text.splitlines()
    # Same mask the writer uses, from the same function: a heading the report skips as quoted
    # must be a line the writer leaves alone, or one of them acts on what the other ignores.
    quoted = shared.fence_mask(lines)
    start = 0
    # A YAML front matter's closing `---` would otherwise underline the line above it into a
    # setext heading — `title: x` is not a section a project wrote by hand.
    if lines and lines[0].strip() == "---":
        start = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
    for index in range(start, len(lines)):
        line = lines[index]
        if quoted[index]:
            continue
        if (m := _HEADING.match(line)) and len(m.group(1)) in levels:
            found.append(m.group(2).lower())
        elif line.strip() and not line.startswith("\t") and index + 1 < len(lines):
            # Setext: the text is on one line and its level on the next. Rarer than ATX, but
            # it produces the same anchor, so a section written that way duplicates the
            # managed block just as literally.
            underline = _SETEXT.match(lines[index + 1])
            if underline and (1 if underline.group(1)[0] == "=" else 2) in levels:
                found.append(line.strip().lower())
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
            # A one-word title is not specific enough to nominate anything: `Conventions`, the
            # H1 that merely names the satellite file, would flag every project carrying a
            # heading that ends in "conventions". Two words are what make the guess worth a
            # maintainer's glance.
            if len(wanted) < 2:
                continue
            match = next((h for h in present if wanted <= _tokens(h)), None)
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
            try:
                # A shared file mbproj cannot read — a directory on the path, a permission
                # denied — is not a question about duplication: applying will die on it. It
                # has to be reported as the stopper it is, not crash the report and hand a
                # caller an exit code that reads as a finding with no output to explain it.
                text = target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                row["status"] = UNREADABLE
                rows.append(row)
                continue
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
                # Any heading level counts: a project that files its tools as `### jq` under
                # a `## Tools` chapter states the same thing the managed block would, and
                # both produce the same `SETUP_ENV.md#jq` anchor the fix messages point at.
                present = set(_headings(text, levels=(1, 2, 3, 4, 5, 6)))
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
        # An unreadable shared file stops an apply exactly as a blocked owned path does, so
        # it belongs to the same count — the caller's question is "will this run through?".
        "blocked_count": (
            sum(1 for r in owned if r["status"] == BLOCKED)
            + sum(1 for r in sharing if r["status"] == UNREADABLE)
        ),
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
        mark = "!" if row["status"] in SHARED_FINDINGS or row["status"] == UNREADABLE else " "
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
            f"{result['blocked_count']} path(s) cannot be written or read — a directory or an "
            "unreadable file sits where a file is expected. Applying would fail part-way "
            "through, leaving the repo half written."
        )
    if result["shared_finding_count"]:
        lines.append(
            f"{result['shared_finding_count']} finding(s) in shared files. Nothing is lost "
            "there — mbproj adds to them — but the project would carry the same thing twice."
        )
        # What "twice" costs differs per file, and lumping the three together undersells the
        # first: a duplicated tool section is not a matter of taste, it turns the generated
        # lint red (MD024) — the very failure this scaffolder is meant not to produce.
        consequences = {
            DUPLICATE: "duplicated sections and ignore lines: `make lint` fails on them (MD024)",
            COLLISION: "colliding targets: make warns, and the project's recipe wins (by design)",
            REVIEW: "nominated headings: prose only you can compare — purely editorial",
        }
        seen = {r["status"] for r in result["shared"]}
        lines += [f"  - {text}" for status, text in consequences.items() if status in seen]
        lines.append("Removing what is superseded is an editorial call, so it is left to you.")
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
