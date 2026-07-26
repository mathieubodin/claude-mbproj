#!/usr/bin/env python3
"""I3 shared-file primitives — touch files the project also owns, non-destructively.

Two mechanisms (spine invariant I3), both idempotent, no-orphan, and create-if-absent:

- (a) `ensure_anchor_lines` — marker-free reconciliation of *self-identifying* pointer
  lines (the file's native indirection). Used for `Makefile` (`include mbproj.mk`) and
  `CLAUDE.md` (`@.claude/mbproj/*` imports): remove every line mbproj owns, then append
  the desired set. The real content lives in owned satellite files.

- (b) `ensure_block` — a delimited `mbproj:managed` block regenerated in full. Used for
  `.gitignore` and `SETUP_ENV.md`, whose formats have no include mechanism, so the content
  lives inline between markers. Content outside the markers is never touched.

Only these two mechanisms may write inside a shared file; regenerating in full (rather than
appending) is what prevents orphaned lines when parameters change.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import mbproj_common as common


BOM = "﻿"

_FENCE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")


def _read_or_empty(path: str | Path) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def fence_mask(lines: list[str]) -> list[bool]:
    """Which lines sit inside a fenced code block — True means "quoted, not content".

    Shared here because both writing and reporting have to agree on it: a `@import` shown
    inside a code sample is documentation, and a module that reconciles anchor lines without
    knowing that deletes what a module that reads headings would have skipped.

    Only a fence of the same character and at least the opening length closes a block, so a
    ``` nested inside a ~~~~ sample does not end it. Indentation is spaces only: a leading tab
    opens an indented code block, it does not indent a fence.
    """
    mask: list[bool] = []
    fence = ""
    for line in lines:
        marker = m.group(1) if (m := _FENCE.match(line)) else ""
        if fence:
            mask.append(True)  # the closing fence belongs to the block
            if marker and marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
        elif marker:
            fence = marker
            mask.append(True)
        else:
            mask.append(False)
    return mask


# --- mechanism (a): self-identifying pointer lines ------------------------
def ensure_anchor_lines(
    path: str | Path,
    desired: list[str],
    identify: str,
    position: str = "append",
    fenced_aware: bool = False,
) -> str:
    """Reconcile mbproj-owned pointer lines in a shared file.

    `identify` is a regex; every existing line it matches is removed, then `desired`
    (order preserved) is re-inserted, separated by a blank line. Idempotent; creates the file.

    `position` decides where the lines land, and for a Makefile that choice is semantic
    rather than cosmetic: GNU make lets the *last* recipe for a target win, so an include
    placed last would override a project's own recipe instead of the reverse. Anchoring
    first lets project definitions take precedence.
    """
    identify_re = re.compile(identify)
    text = _read_or_empty(path)
    # A byte-order mark only means "byte-order mark" on the very first line. Carried along as
    # ordinary text it would be pushed down by a prepend, and make then reads it as part of
    # the target's name — the project's `all:` silently stops existing. Stripped here and put
    # back at the front, it stays where it is the only thing it can be.
    bom = BOM if text.startswith(BOM) else ""
    lines = text[len(bom):].splitlines()
    # A `@import` quoted inside a code block is documentation about the mechanism, not an
    # anchor mbproj owns. Removing it would be a shared file losing content, which is the one
    # thing the shared-file contract promises cannot happen.
    quoted = fence_mask(lines) if fenced_aware else [False] * len(lines)
    kept: list[str] = []
    orphaned = False
    for line, in_code in zip(lines, quoted):
        if identify_re.search(line) and not in_code:
            orphaned = True
            continue
        # Removing our line strands the blank separators that surrounded it: the one before
        # and the one after become adjacent. In the middle of a file that is MD012, which the
        # markdown lint this same scaffolder generates rejects — the engine would emit a file
        # its own config refuses. Exactly one blank per removal is dropped, so the project's
        # own spacing elsewhere is never normalised.
        if orphaned and not line.strip() and kept and not kept[-1].strip():
            orphaned = False
            continue
        kept.append(line)
        if line.strip():
            orphaned = False
    # Same reasoning at the end of the file, where a stranded blank fails `end-of-file-fixer`.
    while kept and not kept[-1].strip():
        kept.pop()
    # And at the start, where an anchor sitting on line 1 leaves its trailing blank leading
    # the file. `kept` is still empty when that blank is seen, so the pairwise rule above
    # cannot catch it.
    while kept and not kept[0].strip():
        kept.pop(0)
    if desired:
        if position == "prepend":
            separator = [""] if kept else []
            result = list(desired) + separator + kept
        else:
            separator = [""] if kept else []
            result = kept + separator + list(desired)
    else:
        result = kept
    out = bom + "\n".join(result) + ("\n" if result else "")
    common.write_text_atomic(path, out)
    return out


# --- mechanism (b): delimited managed block -------------------------------
def _markers(style: str) -> tuple[str, str]:
    if style == "html":
        return ("<!-- >>> mbproj:managed (do not edit) >>> -->", "<!-- <<< mbproj:managed <<< -->")
    prefix = {"hash": "# ", "slash": "// "}.get(style)
    if prefix is None:
        raise ValueError(f"unknown comment style: {style!r}")
    return (f"{prefix}>>> mbproj:managed (do not edit) >>>", f"{prefix}<<< mbproj:managed <<<")


def strip_block(text: str, style: str) -> str:
    """The text with the mbproj:managed region removed.

    What mbproj wrote on a previous run is not evidence that the project carries the same
    content by hand, so anything reading a shared file to judge what is already there must
    look outside the block — otherwise an adopted repo reports itself as duplicating itself.
    """
    start, end = _markers(style)
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.DOTALL)
    return pattern.sub("", text)


def ensure_block(path: str | Path, body: str, style: str) -> str:
    """Insert or replace the mbproj:managed block, regenerated in full.

    The region between the markers (inclusive) is replaced with the fresh block; text
    outside is preserved verbatim. If no block is present, it is appended. Idempotent;
    creates the file.
    """
    start, end = _markers(style)
    inner = (body.rstrip("\n") + "\n") if body.strip() else ""
    block = f"{start}\n{inner}{end}\n"
    text = _read_or_empty(path)
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.DOTALL)
    if pattern.search(text):
        out = pattern.sub(lambda _m: block, text, count=1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        if text:
            text += "\n"  # blank separator before an appended block
        out = text + block
    common.write_text_atomic(path, out)
    return out


# --- CLI ------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mbproj I3 shared-file primitives")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_anchor = sub.add_parser("anchor", help="reconcile self-identifying pointer lines (a)")
    p_anchor.add_argument("path", type=Path)
    p_anchor.add_argument("--identify", required=True, help="regex identifying mbproj lines")
    p_anchor.add_argument("--line", dest="lines", action="append", default=[],
                          help="a desired line (repeatable)")
    p_anchor.add_argument("--position", choices=("append", "prepend"), default="append",
                          help="where to place the lines (prepend for Makefile includes)")

    p_block = sub.add_parser("block", help="regenerate the mbproj:managed block (b)")
    p_block.add_argument("path", type=Path)
    p_block.add_argument("--style", choices=("hash", "slash", "html"), required=True)
    src = p_block.add_mutually_exclusive_group(required=True)
    src.add_argument("--body-file", type=Path)
    src.add_argument("--stdin", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "anchor":
        ensure_anchor_lines(args.path, args.lines, args.identify, args.position)
    else:
        body = sys.stdin.read() if args.stdin else args.body_file.read_text(encoding="utf-8")
        ensure_block(args.path, body, args.style)
    print(args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
