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
    # Normalise last, so a hand-edited manifest is covered as well as the CLI.
    seen: list[str] = []
    for d in (normalize_exclude(d) for d in dirs):
        if d and d not in seen:
            seen.append(d)
    return seen


def normalize_exclude(entry: str) -> str:
    """Strip decoration an author may reasonably type around a directory entry.

    A leading `./` or a trailing `/` is natural to write and harmless to intend, but it
    reaches the three consumers as a doubled separator (`src/generated//**`) that each one
    interprets differently: markdownlint absorbs it, `find`'s `-path` stops matching, and
    prek stops excluding — to the point of rewriting vendored files. Normalising once, here,
    is what keeps the three in agreement.
    """
    normalized = entry.strip()
    while normalized.startswith("././"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def _is_located(entry: str) -> bool:
    """Whether the entry names a *location* rather than a directory name.

    A path (`src/generated`), a glob (`build-*`) or an explicit `./` prefix is a location:
    the author said **where**, so it is matched only there. A bare name (`node_modules`) is
    matched at any depth. This is what lets someone write `./vendor` to mean the one at the
    root, and `vendor` to mean every one.
    """
    return "/" in entry or any(c in entry for c in "*?[")


def _bare(entry: str) -> str:
    """The entry without its `./` marker, which carries meaning but must not be rendered."""
    return entry[2:] if entry.startswith("./") else entry


def _find_exclude(entry: str) -> str:
    """A `find` predicate excluding one entry of the composed set."""
    e = _bare(entry)
    return f'! -path "./{e}/*"' if _is_located(entry) else f'! -path "*/{e}/*"'


def _glob_exclude(entry: str) -> str:
    """Same rule as `_find_exclude`, in the glob syntax markdownlint and prek expect."""
    e = _bare(entry)
    return f"{e}/**" if _is_located(entry) else f"**/{e}/**"


def build_mk(state: dict) -> str:
    applied = _applied(state)
    # `check-dev-env` and `help` ship with every layer set: `help` backs .DEFAULT_GOAL, so it
    # must exist even when the layer that used to carry it (lint_format) is not applied.
    main = sorted({"check-dev-env", "help", *(t for n in applied for t in LAYERS[n]["main_targets"])})
    checks = [t for n in applied for t in LAYERS[n]["check_targets"]]
    excludes = " ".join(_find_exclude(d) for d in compose_exclude_dirs(state))
    check_prereq = (" " + " ".join(checks)) if checks else ""
    parts = [
        ".PHONY: " + " ".join(main),
        ".DEFAULT_GOAL := help",
        "",
        "_MBPROJ_EXCLUDES := " + excludes,
        "",
        "check-dev-env:" + check_prereq + " ## Verify required tools are installed",
        "\t@echo \"OK check-dev-env\"",
        "",
        "help: ## Display all available targets",
        "\t@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort"
        " | awk 'BEGIN{FS=\":.*## \"}{printf \"  %-20s %s\\n\", $$1, $$2}'",
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
        "  # A generated changelog repeats the same group headings in every release",
        "  # section, so only flag duplicates within one section.",
        "  MD024:",
        "    siblings_only: true",
        "",
        "# Vendored / generated directories excluded from linting. A bare name is excluded",
        "# at any depth (node_modules, and packages/*/node_modules alike); an entry written",
        "# as a path, a glob, or with a leading ./ is excluded only where it says. Note that",
        "# `dist` therefore hides a src/dist/ holding real sources — declare such a directory",
        "# out of vendored_dirs and rename it if you need it linted.",
        "ignores:",
    ]
    lines += [f'  - "{_glob_exclude(d)}"' for d in compose_exclude_dirs(state)]
    return "\n".join(lines) + "\n"


def build_prek(state: dict) -> str:
    # `.git` must not be excluded here, however sensible it looks. prek only ever sees
    # staged paths, so the glob cannot match project files — but it *does* match
    # `.git/COMMIT_EDITMSG`, the file git hands to the commit-msg hook. Excluding it makes
    # prek report "no files to check" and skip commitlint entirely, so every commit message
    # passes unchecked while the run still looks green.
    globs = ", ".join(
        f'"{_glob_exclude(d)}"' for d in compose_exclude_dirs(state) if d != ".git"
    )
    return (
        "# prek (https://github.com/j178/prek) - Rust, standalone, no Python.\n"
        "# Content linting is owned by the Makefile: the local `lint` hook delegates to\n"
        "# `make lint`. The builtin repo only adds fast hygiene hooks. Activate once with\n"
        "# `make install-hooks` (see SETUP_ENV.md#git-hooks).\n"
        "\n"
        f"exclude = {{ glob = [{globs}] }}\n"
        "\n"
        "# Run hooks only at the pre-commit stage by default, so hygiene + `make lint` do\n"
        '# not also run at commit-msg. commitlint overrides this with stages = ["commit-msg"].\n'
        'default_stages = ["pre-commit"]\n'
        "\n"
        "[[repos]]\n"
        'repo = "builtin"\n'
        "hooks = [\n"
        '    { id = "trailing-whitespace" },\n'
        '    { id = "end-of-file-fixer", args = ["--fix"] },\n'
        '    { id = "mixed-line-ending", args = ["--fix", "lf"] },\n'
        '    { id = "check-merge-conflict" },\n'
        "]\n"
        "\n"
        "[[repos]]\n"
        'repo = "local"\n'
        "hooks = [\n"
        '    { id = "lint", name = "make lint", entry = "make lint", language = "system", shell = "bash", pass_filenames = false },\n'
        '    { id = "commitlint", name = "commitlint", entry = "commitlint --edit", language = "system", stages = ["commit-msg"], pass_filenames = false },\n'
        "]\n"
    )


def owned_plan(state: dict) -> dict[str, str]:
    """Every file mbproj owns for this state, mapped to the content it would hold.

    Single source of truth: `apply` writes exactly what this returns and the preflight
    reports on the same set, so a layer gaining an owned file cannot be written by one and
    missed by the other. It excludes `.config/mbproj.toml`, which is mbproj's own state
    rather than a project file it takes over.
    """
    applied = _applied(state)
    plan: dict[str, str] = {}
    for name in applied:
        for tpl, dest in LAYERS[name]["owned"]:
            plan[dest] = (TEMPLATES_DIR / tpl).read_text(encoding="utf-8")
    if any(LAYERS[n]["owns_markdownlint_config"] for n in applied):
        plan[".markdownlint-cli2.yaml"] = build_markdownlint(state)
    if any(LAYERS[n]["owns_prek_config"] for n in applied):
        plan["prek.toml"] = build_prek(state)
    plan["mbproj.mk"] = build_mk(state)
    return plan


def plan_state(repo: Path, target_layers, project_name=None, vendored=None) -> dict:
    """The manifest state that applying these layers would produce. Writes nothing."""
    state = manifest.read(repo)
    # The manifest keeps the version it was written with, so an upgrade would otherwise
    # freeze it at the first install and every layer would keep re-recording that stale
    # value. Applying is what stamps the running plugin's version.
    state["plugin_version"] = common.plugin_version()
    if project_name is not None:
        state["params"]["project_name"] = project_name
    if vendored is not None:
        # Normalised on the way in too, so the manifest records what will actually be used.
        state["params"]["vendored_dirs"] = [
            d for d in (normalize_exclude(v) for v in vendored) if d
        ]

    for name in target_layers:
        for dep in DEPENDS_ON[name]:
            if dep not in target_layers and not state["layers"].get(dep, {}).get("applied"):
                raise SystemExit(f"error: layer {name!r} requires {dep!r} to be applied first")
        state["layers"][name] = {"applied": True, "version": state["plugin_version"]}

    return state


def apply(repo: Path, target_layers, project_name=None, vendored=None) -> dict:
    state = plan_state(repo, target_layers, project_name, vendored)
    applied = _applied(state)

    for dest, content in owned_plan(state).items():
        writer.write_owned(repo / dest, content)

    # shared: Makefile include (a) — placed FIRST so a project that gives a generic target
    # its own recipe wins; make lets the last recipe win, so an include placed last would
    # silently override the project's.
    shared.ensure_anchor_lines(
        repo / "Makefile", ["include mbproj.mk"], r"^\s*include\s+mbproj\.mk\s*$", "prepend"
    )

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
