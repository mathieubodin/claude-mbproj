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


def _read_or_empty(path: str | Path) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


# --- mechanism (a): self-identifying pointer lines ------------------------
def ensure_anchor_lines(path: str | Path, desired: list[str], identify: str) -> str:
    """Reconcile mbproj-owned pointer lines in a shared file.

    `identify` is a regex; every existing line it matches is removed, then `desired`
    (order preserved) is appended after a blank separator. Idempotent; creates the file.
    """
    identify_re = re.compile(identify)
    kept = [ln for ln in _read_or_empty(path).splitlines() if not identify_re.search(ln)]
    if desired:
        separator = [""] if kept and kept[-1].strip() != "" else []
        result = kept + separator + list(desired)
    else:
        result = kept
    out = "\n".join(result) + ("\n" if result else "")
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

    p_block = sub.add_parser("block", help="regenerate the mbproj:managed block (b)")
    p_block.add_argument("path", type=Path)
    p_block.add_argument("--style", choices=("hash", "slash", "html"), required=True)
    src = p_block.add_mutually_exclusive_group(required=True)
    src.add_argument("--body-file", type=Path)
    src.add_argument("--stdin", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "anchor":
        ensure_anchor_lines(args.path, args.lines, args.identify)
    else:
        body = sys.stdin.read() if args.stdin else args.body_file.read_text(encoding="utf-8")
        ensure_block(args.path, body, args.style)
    print(args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
