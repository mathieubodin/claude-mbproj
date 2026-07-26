#!/usr/bin/env python3
"""Write an *owned* file: do-not-edit banner + content, byte-identically.

An owned file is one whose full content belongs to mbproj and is rewritten in
full on every run (spine invariants I2/I7). The banner is rendered in the file's
comment style; the content is written verbatim, with LF endings and a single
trailing newline, so repeated runs produce identical bytes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import mbproj_common as common


def render_owned(target: str | Path, content: str, style: str | None = None) -> str:
    """Return the exact bytes (as text) an owned file should hold.

    A leading YAML frontmatter block (`---` ... `---`) must stay on line 1 for Claude
    Code to parse a rule's `paths`, so the banner is inserted *after* it.
    """
    if style is None:
        style = common.style_for(target)
    banner = common.render_banner(style)
    body = content if content.endswith("\n") else content + "\n"
    if body.startswith("---\n"):
        close = body.find("\n---\n", 4)
        if close != -1:
            split = close + len("\n---\n")
            frontmatter = body[:split]
            rest = body[split:].lstrip("\n")
            return f"{frontmatter}\n{banner}\n{rest}" if rest else f"{frontmatter}\n{banner}"
    return f"{banner}\n{body}"


def has_banner(text: str) -> bool:
    """Whether the banner sits where `render_owned` puts it — not merely somewhere.

    This is the inverse of `render_owned` and lives beside it on purpose: the code that
    decides where the banner goes is the code that decides where to look for it.

    Searching the whole file would mistake a hand-written document that *quotes* the banner
    for a generated one — and a conventions file explaining "do not edit generated files" is
    exactly the document that quotes it. The banner proves authorship only at the top, after
    a YAML frontmatter block when there is one.
    """
    lines = text.splitlines(keepends=True)
    start = 0
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                start = index + 1
                break
        else:
            return False
    # Match the rendered block exactly rather than looking for the marker nearby: a quote
    # of the banner in the opening prose of a hand-written document would land inside any
    # tolerant window.
    body = "".join(lines[start:]).lstrip("\n")
    return any(body.startswith(common.render_banner(s)) for s in ("hash", "slash", "html"))


def write_owned(target: str | Path, content: str, style: str | None = None) -> str:
    text = render_owned(target, content, style)
    common.write_text_atomic(target, text)
    return text


# --- CLI ------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="write an owned file with the mbproj banner")
    parser.add_argument("target", type=Path, help="path of the owned file to write")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--content-file", type=Path, help="read content from this file")
    src.add_argument("--stdin", action="store_true", help="read content from stdin")
    parser.add_argument("--style", choices=("hash", "slash", "html"), default=None)
    args = parser.parse_args(argv)

    if args.stdin:
        content = sys.stdin.read()
    else:
        content = args.content_file.read_text(encoding="utf-8")

    write_owned(args.target, content, args.style)
    print(args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
