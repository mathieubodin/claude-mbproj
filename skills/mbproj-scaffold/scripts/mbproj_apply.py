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


def shared_plan(state: dict) -> dict[str, dict]:
    """What applying would add to each *shared* file, keyed by path.

    Shared files are never rewritten, so the risk here is not loss but duplication: the
    project may already carry, by hand, what mbproj is about to contribute. Same reason as
    `owned_plan` for existing: `apply` adds exactly these items and the preflight reports on
    them, so the two cannot drift apart.
    """
    applied = _applied(state)
    # `block_style` names the I3(b) comment syntax, or is None for the I3(a) files. Both
    # mechanisms are described here rather than at the call sites: the preflight has to strip
    # a previous run's own block before judging what a project carries by hand, and reading
    # that style from anywhere else is how the two would come to disagree about which region
    # of a file belongs to mbproj.
    return {
        "Makefile": {
            "kind": "make include",
            "items": ["include mbproj.mk"],
            "block_style": None,
        },
        "CLAUDE.md": {
            "kind": "imports",
            "items": [f"@{p}" for n in applied for p in LAYERS[n]["claude_imports"]],
            "block_style": None,
        },
        "SETUP_ENV.md": {
            "kind": "tool sections",
            "items": [s for n in applied for s in LAYERS[n]["setup_env_sections"]],
            "block_style": "html",
        },
        ".gitignore": {
            "kind": "ignore lines",
            "items": [line for n in applied for line in LAYERS[n]["gitignore_lines"]],
            "block_style": "hash",
        },
    }


def _is_empty(path: Path) -> bool:
    """Whether a shared file needs seeding — absent, or present with nothing in it.

    `touch CLAUDE.md` is an ordinary reflex, and a template `git init` leaves such files
    behind. Testing existence alone skips the seed, and the file then opens on an `@import`
    or a block marker with no H1 above it — which the markdown lint this scaffolder generates
    rejects (MD041).
    """
    return not path.exists() or not path.read_text(encoding="utf-8", errors="replace").strip()


def plan_state(repo: Path, target_layers, project_name=None, vendored=None) -> dict:
    """The manifest state that applying these layers would produce. Writes nothing."""
    state = manifest.read(repo)
    # The manifest keeps the version it was written with, so an upgrade would otherwise
    # freeze it at the first install and every layer would keep re-recording that stale
    # value. Applying is what stamps the running plugin's version.
    state["plugin_version"] = common.plugin_version()
    if project_name is not None:
        state["params"]["project_name"] = project_name
    # The manifest has to record the name actually used, not the flag that was passed: with
    # I4 making it the source of truth, a blank entry beside a CLAUDE.md seeded from the
    # directory name means the two disagree about what the project is called.
    if not state["params"]["project_name"]:
        state["params"]["project_name"] = repo.name
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
    if _is_empty(claude):
        pname = state["params"]["project_name"]
        common.write_text_atomic(claude, f"# {pname}\n\nGuidance for AI agents working in this repository.\n")
    plan = shared_plan(state)
    shared.ensure_anchor_lines(claude, plan["CLAUDE.md"]["items"], r"^@\.claude/mbproj/")

    # shared: SETUP_ENV.md tool sections (b)
    sections = [
        (TEMPLATES_DIR / "setup_env" / f"{s}.md").read_text(encoding="utf-8").rstrip("\n")
        for s in plan["SETUP_ENV.md"]["items"]
    ]
    if sections:
        setup = repo / "SETUP_ENV.md"
        if _is_empty(setup):
            pname = state["params"]["project_name"]
            seed = f"# Environment Setup\n\nTooling required to develop on **{pname}**. Run `make check-dev-env` to verify.\n"
            common.write_text_atomic(setup, seed)
        shared.ensure_block(setup, "\n\n".join(sections) + "\n", plan["SETUP_ENV.md"]["block_style"])

    # shared: .gitignore lines (b) — layer-contributed only
    gi_lines = plan[".gitignore"]["items"]
    if gi_lines:
        shared.ensure_block(
            repo / ".gitignore", "\n".join(gi_lines) + "\n", plan[".gitignore"]["block_style"]
        )

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

    repo = args.repo.resolve()
    # Scaffolding tooling into a repository that does not exist is a typo, not a greenfield
    # install: creating the directory turns a mistyped path into a plausible-looking tree
    # nobody asked for. The preflight refuses the same way, for the same reason.
    if not repo.is_dir():
        parser.error(f"{args.repo} is not a directory")

    try:
        apply(repo, args.layers, args.project_name, args.vendored)
    except SystemExit as exc:  # a rejected layer set is a usage error, not a failed apply
        # Same convention as the preflight: 2 means the question was malformed. Left as the
        # default 1, a caller could not tell a rejected dependency chain from a run that
        # broke part-way through — one wrote nothing, the other may have written half.
        print(exc, file=sys.stderr)
        return 2
    print(args.repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
