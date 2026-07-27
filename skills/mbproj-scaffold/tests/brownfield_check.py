#!/usr/bin/env python3
"""Prove the preflight against a brownfield repo, and the extension pattern against make.

Adopting the reference project by hand hit five classes of conflict (spine `docs/adoption.md`).
This builds a repo carrying all five and asserts the report names them — the fixture is
generated rather than committed so it cannot drift from the layer registry it is written
against, and so it never has to be excluded from the lint that runs over this repo.

The second half checks the claim `docs/adoption.md` makes about extending a generated target:
adding a prerequisite does not override the recipe. That is asserted against `make -n`
expansion rather than by reading the manual, and the counter-example — redefining the recipe —
is checked too, since a test that only confirms the happy path would pass on a broken make.

Run: python3 skills/mbproj-scaffold/tests/brownfield_check.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import mbproj_apply as apply_mod  # noqa: E402
import mbproj_preflight as preflight  # noqa: E402

LAYERS = ["lint_format", "guards", "changelog", "agentic"]

# One hand-written stand-in per owned file the four layers claim. Content is deliberately
# unlike what mbproj writes, and carries no banner: that absence is what makes it a conflict.
HANDWRITTEN = [
    ".claude/rules/json.md",
    ".claude/rules/makefile.md",
    ".claude/rules/markdown.md",
    ".claude/rules/projects-files.md",
    ".claude/rules/yaml.md",
    ".markdownlint-cli2.yaml",
    ".shellcheckrc",
    "cliff.toml",
    "commitlint.config.js",
    "prek.toml",
]

MAKEFILE = """\
.PHONY: build changelog check-dev-env clean help install-hooks lint package

build: ## Build the project
\t@echo "building"

changelog: ## Regenerate the changelog
\t@echo "changelog"

check-dev-env: ## Verify prerequisites
\t@echo "checking"

clean: ## Remove artifacts
\t@echo "cleaning"

help: ## Show targets
\t@echo "help"

install-hooks: ## Install git hooks
\t@echo "hooks"

lint: ## Lint everything
\t@echo "linting"

package: ## Package the project
\t@echo "packaging"
"""

SETUP_ENV = """\
# Environment Setup

## markdownlint-cli2

Install it.

## jq

Install it.

## yq

Install it.

## shellcheck

Install it.

## commitlint

Install it.

## prek

Install it.

## git-cliff

Install it.

## Git hooks

Install them.
"""

CLAUDE_MD = """\
# Reference Project

## Code Standards & Patterns

How we write code here.

## Agentic Workflow (BMAD + Compound Engineering)

How the agents work here.

## When Adding Features

What to do first.
"""

GITIGNORE = """\
dist/

_bmad/**/*.user.toml
_bmad/**/*.user.yaml
"""


def build_fixture(root: Path) -> None:
    """Write a repo carrying, by hand, an equivalent of everything the four layers bring."""
    for rel in HANDWRITTEN:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# hand-written {rel}\n", encoding="utf-8")
    (root / "Makefile").write_text(MAKEFILE, encoding="utf-8")
    (root / "SETUP_ENV.md").write_text(SETUP_ENV, encoding="utf-8")
    (root / "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    (root / ".gitignore").write_text(GITIGNORE, encoding="utf-8")


def _row(report: dict, path: str) -> dict:
    return next(r for r in report["shared"] if r["path"] == path)


def check_report(root: Path, fail) -> None:
    """The five collision classes, each named by the report rather than merely counted."""
    report = preflight.report(root, LAYERS, project_name="reference")

    overwritten = {r["path"] for r in report["owned"] if r["status"] == preflight.OVERWRITE}
    missing = set(HANDWRITTEN) - overwritten
    if missing:
        fail(f"hand-written owned files not reported: {sorted(missing)}")
    if report["conflict_count"] != len(HANDWRITTEN):
        fail(f"conflict_count is {report['conflict_count']}, expected {len(HANDWRITTEN)}")

    public = {"build", "changelog", "check-dev-env", "clean", "help", "install-hooks",
              "lint", "package"}
    collisions = set(_row(report, "Makefile")["findings"])
    if not public <= collisions:
        fail(f"make targets not reported as colliding: {sorted(public - collisions)}")

    sections = set(_row(report, "SETUP_ENV.md")["findings"])
    expected_sections = {"markdownlint-cli2", "jq", "yq", "shellcheck", "commitlint", "prek",
                         "git-cliff", "git hooks"}
    if sections != expected_sections:
        fail(f"SETUP_ENV sections: got {sorted(sections)}, expected {sorted(expected_sections)}")

    nominated = {f["heading"] for f in _row(report, "CLAUDE.md")["findings"]}
    expected_headings = {"code standards & patterns", "when adding features",
                         "agentic workflow (bmad + compound engineering)"}
    if nominated != expected_headings:
        fail(f"CLAUDE.md nominations: got {sorted(nominated)}, expected {sorted(expected_headings)}")

    ignores = set(_row(report, ".gitignore")["findings"])
    if ignores != {"_bmad/**/*.user.toml", "_bmad/**/*.user.yaml"}:
        fail(f"gitignore duplicates: got {sorted(ignores)}")

    # A report that finds all this and still lets the engine write would make the gate a
    # decoration, so the refusal is part of what is being proved.
    try:
        apply_mod.apply(root, LAYERS, project_name="reference")
    except apply_mod.PendingConflicts:
        pass
    else:
        fail("applying a conflicted repo was not refused")


def _expand(root: Path, target: str) -> str:
    result = subprocess.run(
        ["make", "-C", str(root), "-n", target],
        capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    return result.stdout + result.stderr


def check_extension_pattern(root: Path, fail) -> None:
    """Adding a prerequisite extends a generated target; redefining its recipe overrides it."""
    apply_mod.apply(root, ["lint_format"], project_name="extension")

    (root / "Makefile").write_text(
        "include mbproj.mk\n\ncheck-dev-env: _check_project\n\n_check_project:\n"
        '\t@echo "project check"\n',
        encoding="utf-8",
    )
    expansion = _expand(root, "check-dev-env")
    if "overriding recipe" in expansion or "ignoring old recipe" in expansion:
        fail(f"a prerequisite-only extension warned about overriding:\n{expansion}")
    if "project check" not in expansion:
        fail(f"the project's own prerequisite did not run:\n{expansion}")
    if "markdownlint-cli2 not found" not in expansion:
        fail(f"the generated checks stopped running:\n{expansion}")

    # The counter-example: without it, a make that never warns would pass the check above.
    (root / "Makefile").write_text(
        'include mbproj.mk\n\ncheck-dev-env:\n\t@echo "mine"\n', encoding="utf-8"
    )
    expansion = _expand(root, "check-dev-env")
    if "overriding recipe" not in expansion:
        fail(f"redefining a recipe was expected to warn, and did not:\n{expansion}")


def main() -> int:
    failures: list[str] = []

    def fail(message: str) -> None:
        failures.append(message)

    with tempfile.TemporaryDirectory() as tmp:
        brownfield = Path(tmp) / "brownfield"
        brownfield.mkdir()
        build_fixture(brownfield)
        check_report(brownfield, fail)

        extension = Path(tmp) / "extension"
        extension.mkdir()
        check_extension_pattern(extension, fail)

    for message in failures:
        print(f"FAIL {message}", file=sys.stderr)
    print(f"brownfield_check: {'FAILED' if failures else 'ok'} ({len(failures)} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
