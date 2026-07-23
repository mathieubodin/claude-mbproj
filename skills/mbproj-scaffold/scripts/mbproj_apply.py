#!/usr/bin/env python3
"""Compose and apply layers into a target repo (spine invariant I8).

Given the manifest's applied layers plus parameters, this writes every owned file
(via mbproj_writer) and every shared-file contribution (via mbproj_shared), composing
the parts that depend on the applied set: the lint-exclude list, `check-dev-env`, the
`mbproj.mk` targets, the `.markdownlint-cli2.yaml` ignores, and the SETUP_ENV.md block.
Deterministic: same manifest -> byte-identical output.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import mbproj_common as common
import mbproj_manifest as manifest
import mbproj_shared as shared
import mbproj_writer as writer
from mbproj_layers import DEPENDS_ON, GENERIC_EXCLUDE_DIRS, LAYERS, LAYER_ORDER, TEMPLATES_DIR


def _applied(state: dict) -> list[str]:
    return [n for n in LAYER_ORDER if state["layers"].get(n, {}).get("applied")]


def compose_exclude_dirs(state: dict) -> list[str]:
    """Generic defaults + layer-contributed + vendored_dirs, de-duplicated, order-stable."""
    dirs: list[str] = list(GENERIC_EXCLUDE_DIRS)
    for name in _applied(state):
        for d in LAYERS[name]["exclude_dirs"]:
            if d not in dirs:
                dirs.append(d)
    for d in state["params"]["vendored_dirs"]:
        if d not in dirs:
            dirs.append(d)
    return dirs


def build_mk(state: dict) -> str:
    applied = _applied(state)
    main = sorted({"check-dev-env", *(t for n in applied for t in LAYERS[n]["main_targets"])})
    checks = [t for n in applied for t in LAYERS[n]["check_targets"]]
    excludes = " ".join(f'! -path "./{d}/*"' for d in compose_exclude_dirs(state))
    check_prereq = (" " + " ".join(checks)) if checks else ""
    parts = [
        ".PHONY: " + " ".join(main),
        ".DEFAULT_GOAL := help",
        "",
        "_MBPROJ_EXCLUDES := " + excludes,
        "",
        "check-dev-env:" + check_prereq + " ## Verify required tools are installed",
        "\t@echo \"OK check-dev-env\"",
    ]
    for name in applied:
        if LAYERS[name]["mk"]:
            parts += ["", LAYERS[name]["mk"].rstrip("\n")]
    return "\n".join(parts) + "\n"


def build_markdownlint(state: dict) -> str:
    lines = [
        "config:",
        "  # Default rule set on; MD013 (line length) off - prose is not hard-wrapped.",
        "  default: true",
        "  MD013: false",
        "",
        "# Vendored / generated directories excluded from linting.",
        "ignores:",
    ]
    lines += [f'  - "{d}/**"' for d in compose_exclude_dirs(state)]
    return "\n".join(lines) + "\n"


def apply(repo: Path, target_layers, project_name=None, vendored=None) -> dict:
    state = manifest.read(repo)
    if project_name is not None:
        state["params"]["project_name"] = project_name
    if vendored is not None:
        state["params"]["vendored_dirs"] = list(vendored)

    for name in target_layers:
        for dep in DEPENDS_ON[name]:
            if dep not in target_layers and not state["layers"].get(dep, {}).get("applied"):
                raise SystemExit(f"error: layer {name!r} requires {dep!r} to be applied first")
        state["layers"][name] = {"applied": True, "version": state["plugin_version"]}

    applied = _applied(state)

    # owned files (verbatim templates + banner)
    for name in applied:
        for tpl, dest in LAYERS[name]["owned"]:
            content = (TEMPLATES_DIR / tpl).read_text(encoding="utf-8")
            writer.write_owned(repo / dest, content)

    # composed owned files
    if any(LAYERS[n]["owns_markdownlint_config"] for n in applied):
        writer.write_owned(repo / ".markdownlint-cli2.yaml", build_markdownlint(state), style="hash")
    writer.write_owned(repo / "mbproj.mk", build_mk(state), style="hash")

    # shared: Makefile include (a)
    shared.ensure_anchor_lines(repo / "Makefile", ["include mbproj.mk"], r"^\s*include\s+mbproj\.mk\s*$")

    # shared: CLAUDE.md imports (a) — seed a title first so a fresh file has an H1
    claude = repo / "CLAUDE.md"
    if not claude.exists():
        pname = state["params"]["project_name"] or repo.name
        common.write_text_atomic(claude, f"# {pname}\n\nGuidance for AI agents working in this repository.\n")
    imports = [f"@{p}" for n in applied for p in LAYERS[n]["claude_imports"]]
    shared.ensure_anchor_lines(claude, imports, r"^@\.claude/mbproj/")

    # shared: SETUP_ENV.md tool sections (b)
    sections = [
        (TEMPLATES_DIR / "setup_env" / f"{s}.md").read_text(encoding="utf-8").rstrip("\n")
        for n in applied
        for s in LAYERS[n]["setup_env_sections"]
    ]
    if sections:
        setup = repo / "SETUP_ENV.md"
        if not setup.exists():
            pname = state["params"]["project_name"] or repo.name
            seed = f"# Environment Setup\n\nTooling required to develop on **{pname}**. Run `make check-dev-env` to verify.\n"
            common.write_text_atomic(setup, seed)
        shared.ensure_block(setup, "\n\n".join(sections) + "\n", "html")

    # shared: .gitignore lines (b) — layer-contributed only
    gi_lines = [line for n in applied for line in LAYERS[n]["gitignore_lines"]]
    if gi_lines:
        shared.ensure_block(repo / ".gitignore", "\n".join(gi_lines) + "\n", "hash")

    manifest.write(repo, state)
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="compose and apply mbproj layers into a repo")
    parser.add_argument("repo", type=Path)
    parser.add_argument("--layer", dest="layers", action="append", default=[], choices=LAYER_ORDER,
                        required=True, help="layer to apply (repeatable)")
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--vendored-dir", dest="vendored", action="append", default=None,
                        help="a vendored directory to exclude from linting (repeatable)")
    args = parser.parse_args(argv)
    apply(args.repo.resolve(), args.layers, args.project_name, args.vendored)
    print(args.repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
