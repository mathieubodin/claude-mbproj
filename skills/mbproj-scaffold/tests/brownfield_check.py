#!/usr/bin/env python3
"""Prove the preflight against a brownfield repo, and the extension pattern against make.

Four things are checked, and the split matters — each covers what the others structurally
cannot:

- **The report, end to end.** Adopting the reference project by hand hit five classes of
  conflict (`docs/adoption.md`); a repo carrying all five must have each one named. The fixture
  is generated rather than committed, so it cannot drift from the layer registry it is written
  against, and never has to be excluded from the lint that runs over this repo.
- **The gate.** That it refuses, that an unwritable path cannot be acknowledged past it, and
  that the acknowledgement survives the next run.
- **The parsers, directly.** Every shape that once produced a wrong report gets its own case.
  Routing these through the fixture would only prove them for the one shape it happens to
  carry — a fixture with no `define` block, no quoted heading and no unclosed fence passes
  just as happily with those defects restored. This half exists because a mutation run showed
  the end-to-end half catching two of thirteen.
- **make itself.** The claim `docs/adoption.md` makes about extending a generated target is
  asserted against `make -n` expansion rather than by reading the manual, counter-example
  included: a test that only confirms the happy path would pass on a make that never warns.

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
import mbproj_manifest as manifest  # noqa: E402
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

## Tools filed under a chapter

A project may nest its tool sections one level down; the anchor is the same, so the managed
block would still restate them.

### shellcheck

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


# Each entry is a defect that reached a released commit, with the form that revealed it. An
# end-to-end fixture cannot stand in for these: it would have to contain every shape at once,
# and a missing shape reads as a passing test rather than as an untested one.
MAKE_FORMS = [
    ("two targets on one line", "lint build:\n\t@echo x\n", {"lint", "build"}),
    ("backslash continuation", "lint \\\n build:\n\t@echo x\n", {"lint", "build"}),
    ("space-indented rule", "  lint:\n\t@echo x\n", {"lint"}),
    ("internal targets", "_lint_json:\n\t@echo x\n_check_jq:\n\t@echo y\n",
     {"_lint_json", "_check_jq"}),
    ("double colon", "clean::\n\t@echo x\n", {"clean"}),
    ("function call carrying a colon", "$(info build: starting)\n$(warning lint: old)\n", set()),
    ("define body", "define USAGE\n  build: compile\n  lint: check\nendef\n", set()),
    ("assignments", "VAR ::= x\nT :::= y\nQ ?= @\nlint := no\n", set()),
    ("pattern rule", "%.o: %.c\n\t@echo x\n", set()),
    ("dot directive", ".PHONY: lint build\n", set()),
    ("recipe holding a colon", "real:\n\t@echo \"checking: files\"\n", {"real"}),
]

HEADING_FORMS = [
    ("plain atx", "## jq\n", ["jq"]),
    ("closed atx", "## jq ##\n", ["jq"]),
    ("space-indented atx", "   ## jq\n", ["jq"]),
    ("setext", "jq\n--\n", ["jq"]),
    ("inside a fence", "```text\n## jq\n```\n", []),
    ("inside a tilde fence", "~~~\n## jq\n~~~\n", []),
    ("tab-indented code block", "text:\n\n\t## jq\n", []),
    ("four-space code block over a break", "text:\n\n    jq\n---\n", []),
    ("front matter", "---\ntitle: jq\n---\n", []),
    ("after an unclosed fence", "```text\nopen\n\n## jq\n", ["jq"]),
    ("closed block above an unclosed one", "```text\n## jq\n```\n\n```text\nopen\n", []),
]


def check_parsers(fail) -> None:
    """The parser behaviours, each pinned to the defect that produced it.

    Tested directly rather than through the fixture: these are properties of how a Makefile
    and a Markdown file are read, and routing them through an end-to-end report only proves
    them for the one shape the fixture happens to carry.
    """
    for label, text, expected in MAKE_FORMS:
        got = preflight._make_targets(text)
        if got != expected:
            fail(f"make parser, {label}: got {sorted(got)}, expected {sorted(expected)}")

    for label, text, expected in HEADING_FORMS:
        got = preflight._headings(text, levels=(1, 2, 3, 4, 5, 6))
        if got != expected:
            fail(f"heading parser, {label}: got {got}, expected {expected}")


def check_adopted_is_silent(root: Path, fail) -> None:
    """An adopted repo must not report itself as duplicating what mbproj wrote into it.

    The managed block is stripped before judging, and nothing else exercises that: a fixture
    built from scratch has no block to strip, so the check would pass with the stripping gone.
    """
    apply_mod.apply(root, LAYERS, project_name="adopted")
    report = preflight.report(root, LAYERS, project_name="adopted")
    noisy = [r["path"] for r in report["shared"] if r["findings"]]
    if noisy:
        fail(f"an adopted repo reports findings against itself: {noisy}")
    if report["conflict_count"] or report["blocked_count"]:
        fail(f"an adopted repo reports conflicts: {report}")

    # A directory on an owned path is a write that cannot happen, not content to weigh up.
    owned_dir = root / "prek.toml"
    owned_dir.unlink()
    owned_dir.mkdir()
    status = next(r["status"] for r in preflight.classify_owned(root, apply_mod.plan_state(
        root, LAYERS, "adopted", None)) if r["path"] == "prek.toml")
    if status != preflight.BLOCKED:
        fail(f"a directory on an owned path is classified {status!r}, expected blocked")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def check_writes(root: Path, fail) -> None:
    """What applying puts on disk — the half a report-shaped test cannot reach.

    Every case here is a defect that shipped: imports accumulating because the writer stopped
    recognising its own output, a BOM pushed off line 1 killing the project's target, a quoted
    import deleted, a second H1 seeded into a file that had one, the include anchored last and
    silently overriding a project recipe, an exclude reaching its three consumers as a doubled
    separator. None of them changes what the *report* says, which is why they survived a suite
    built entirely around it.
    """
    (root / "Makefile").write_bytes(
        "﻿all:\n\t@echo hello\n".encode()  # BOM, then the project's own target
    )
    (root / "CLAUDE.md").write_text(
        "<!-- generated notice -->\n\n# Project\n\nProse.\n\n"
        "```text\n@.claude/mbproj/conventions.md\n```\n",
        encoding="utf-8",
    )
    apply_mod.apply(root, LAYERS, project_name="writes", vendored=["src/generated/"])

    before = _snapshot(root)
    apply_mod.apply(root, LAYERS, project_name="writes", vendored=["src/generated/"])
    after = _snapshot(root)
    if before != after:
        changed = sorted(k for k in before | after.keys() if before.get(k) != after.get(k))
        fail(f"applying twice was not byte-identical: {changed}")

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    if not makefile.startswith("﻿"):
        fail("the BOM did not stay on the first line")
    # The BOM is not a line of its own — it prefixes the first one, which is where the include
    # has to be for a project recipe to win over the generic one.
    if makefile.lstrip("﻿").splitlines()[0].strip() != "include mbproj.mk":
        fail(f"the include is not anchored first: {makefile.splitlines()[:3]}")
    if "all:" not in makefile:
        fail("the project's own target did not survive")

    claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
    if claude.count("@.claude/mbproj/conventions.md") != 2:
        fail("the quoted import was not preserved beside the real anchor")
    if claude.count("\n# ") + claude.startswith("# ") != 1:
        fail(f"seeding added a second H1:\n{claude}")

    # One malformed entry, three consumers: the doubled separator each reads differently is
    # why normalisation happens once, at the source. Matched on the entry itself rather than
    # on any `//`, which also occurs in the URLs these files legitimately carry.
    for name in (".markdownlint-cli2.yaml", "prek.toml", "mbproj.mk"):
        text = (root / name).read_text(encoding="utf-8")
        if "src/generated//" in text:
            fail(f"{name} carries a doubled separator from an un-normalised exclude")
        if "src/generated" not in text:
            fail(f"{name} does not carry the vendored exclude at all")


def check_gate(root: Path, fail) -> None:
    """What acknowledgement covers, and what it must not.

    Both cases here were live defects: a blocked path could be forced past the gate, leaving
    the repo half written, and the acknowledgement was erased by the next run.
    """
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "mbproj").write_text("not a directory\n", encoding="utf-8")

    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    try:
        apply_mod.apply(root, ["lint_format"], project_name="blocked", acknowledged=True)
    except apply_mod.UnwritablePaths:
        pass
    except OSError as exc:
        # The gate let it through and the write died where the report said it would. Caught
        # so this reads as the defect it is, rather than as the check itself crashing.
        fail(f"an unwritable path got past the gate and applying died on it: {exc!r}")
    else:
        fail("an unwritable path was acknowledged past the gate")
    after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    if before != after:
        fail(f"the refused run still wrote: {sorted(set(after) - set(before))}")

    # Sticky acknowledgement: once the overwritten files carry the banner, the next run reads
    # as clean, which is exactly when the record must not be recomputed.
    adopted = root.parent / "sticky"
    adopted.mkdir()
    (adopted / "prek.toml").write_text("# hand-written\n", encoding="utf-8")
    apply_mod.apply(adopted, ["lint_format", "guards"], project_name="a", acknowledged=True)
    for run in range(2):
        apply_mod.apply(adopted, ["lint_format", "guards"], project_name="a")
        outcome = manifest.read(adopted)["adoption"]["preflight"]
        if outcome != manifest.ACKNOWLEDGED:
            fail(f"acknowledgement lost after re-run {run + 1}: recorded {outcome!r}")


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

    # The claim least likely to be true, and so the one most worth checking: prerequisites
    # merge whatever the order, unlike recipes, where last wins and the include's placement is
    # the whole reason it is anchored first.
    (root / "Makefile").write_text(
        "check-dev-env: _check_project\n\n_check_project:\n"
        '\t@echo "project check"\n\ninclude mbproj.mk\n',
        encoding="utf-8",
    )
    expansion = _expand(root, "check-dev-env")
    if "overriding recipe" in expansion or "project check" not in expansion:
        fail(f"the extension stopped working with the include placed last:\n{expansion}")

    # The counter-example: without it, a make that never warns would pass the checks above.
    # Note what it does *not* claim — the generated prerequisites still run; only the recipe
    # is replaced, which is why the warning is the signal rather than a broken build.
    (root / "Makefile").write_text(
        'include mbproj.mk\n\ncheck-dev-env:\n\t@echo "mine"\n', encoding="utf-8"
    )
    expansion = _expand(root, "check-dev-env")
    if "overriding recipe" not in expansion:
        fail(f"redefining a recipe was expected to warn, and did not:\n{expansion}")
    if "markdownlint-cli2 not found" not in expansion:
        fail(f"the generated prerequisites were expected to survive an override:\n{expansion}")


def main() -> int:
    failures: list[str] = []

    def fail(message: str) -> None:
        failures.append(message)

    with tempfile.TemporaryDirectory() as tmp:
        brownfield = Path(tmp) / "brownfield"
        brownfield.mkdir()
        build_fixture(brownfield)
        check_report(brownfield, fail)

        check_parsers(fail)

        adopted = Path(tmp) / "adopted"
        adopted.mkdir()
        check_adopted_is_silent(adopted, fail)

        writes = Path(tmp) / "writes"
        writes.mkdir()
        check_writes(writes, fail)

        gate = Path(tmp) / "gate"
        gate.mkdir()
        check_gate(gate, fail)

        extension = Path(tmp) / "extension"
        extension.mkdir()
        check_extension_pattern(extension, fail)

    for message in failures:
        print(f"FAIL {message}", file=sys.stderr)
    print(f"brownfield_check: {'FAILED' if failures else 'ok'} ({len(failures)} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
