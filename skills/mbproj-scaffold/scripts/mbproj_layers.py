#!/usr/bin/env python3
"""Layer registry — what each layer owns, contributes to shared files, and composes.

The composition engine (mbproj_apply) reads this to assemble owned files and shared-file
contributions from the manifest's applied layers (spine invariant I8). Make recipe blocks
use a `<TAB>` placeholder converted to a real tab, so no literal tabs live in this source.
"""
from __future__ import annotations

from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

LAYER_ORDER = ("lint_format", "guards", "changelog", "agentic")

# layer -> layers it requires (dependency chain; agentic is independent)
DEPENDS_ON = {"lint_format": (), "guards": ("lint_format",), "changelog": ("guards",), "agentic": ()}

# Generic lint-exclude directories (I8), fixed order for determinism.
GENERIC_EXCLUDE_DIRS = (".git", "node_modules", "dist", ".idea", ".vscode")


def _mk(raw: str) -> str:
    return raw.replace("<TAB>", "\t")


_LINT_FORMAT_MK = _mk(
    """\
build: ## Build project artifacts (currently a no-op placeholder)
<TAB>@echo "OK build"

clean: ## Remove build artifacts
<TAB>@rm -rf dist/ 2>/dev/null || true
<TAB>@echo "OK clean"

help: ## Display all available targets
<TAB>@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN{FS=":.*## "}{printf "  %-20s %s\\n", $$1, $$2}'

lint: _lint_markdown _lint_json _lint_yaml _lint_shell ## Lint all sources (Markdown, JSON, YAML, Shell)
<TAB>@echo "OK lint"

package: ## Package project for distribution (currently a no-op placeholder)
<TAB>@echo "OK package"

_lint_markdown: _check_markdownlint
<TAB>@markdownlint-cli2 "**/*.md"

_lint_json: _check_jq
<TAB>@find . -name '*.json' -type f $(_MBPROJ_EXCLUDES) -exec jq empty {} +

_lint_yaml: _check_yq
<TAB>@find . -type f \\( -name '*.yaml' -o -name '*.yml' \\) $(_MBPROJ_EXCLUDES) -exec yq 'true' {} + >/dev/null

_lint_shell: _check_shellcheck
<TAB>@files=$$(find . -type f -name '*.sh' $(_MBPROJ_EXCLUDES)); \\
<TAB>if [ -n "$$files" ]; then printf '%s\\n' $$files | xargs shellcheck; fi

_check_markdownlint:
<TAB>@command -v markdownlint-cli2 >/dev/null 2>&1 || { echo "markdownlint-cli2 not found - see SETUP_ENV.md#markdownlint-cli2"; exit 1; }

_check_jq:
<TAB>@command -v jq >/dev/null 2>&1 || { echo "jq not found - see SETUP_ENV.md#jq"; exit 1; }

_check_yq:
<TAB>@command -v yq >/dev/null 2>&1 || { echo "yq not found - see SETUP_ENV.md#yq"; exit 1; }

_check_shellcheck:
<TAB>@command -v shellcheck >/dev/null 2>&1 || { echo "shellcheck not found - see SETUP_ENV.md#shellcheck"; exit 1; }
"""
)


def _empty_layer() -> dict:
    return {
        "owned": [],
        "claude_imports": [],
        "setup_env_sections": [],
        "gitignore_lines": [],
        "exclude_dirs": [],
        "mk": "",
        "main_targets": [],
        "check_targets": [],
        "owns_markdownlint_config": False,
        "owns_prek_config": False,
    }


LAYERS: dict[str, dict] = {name: _empty_layer() for name in LAYER_ORDER}

LAYERS["lint_format"].update(
    {
        "owned": [
            ("rules/json.md", ".claude/rules/json.md"),
            ("rules/makefile.md", ".claude/rules/makefile.md"),
            ("rules/markdown.md", ".claude/rules/markdown.md"),
            ("rules/projects-files.md", ".claude/rules/projects-files.md"),
            ("rules/yaml.md", ".claude/rules/yaml.md"),
            ("shellcheckrc", ".shellcheckrc"),
            ("conventions.md", ".claude/mbproj/conventions.md"),
        ],
        "claude_imports": [".claude/mbproj/conventions.md"],
        "setup_env_sections": ["markdownlint-cli2", "jq", "yq", "shellcheck"],
        "mk": _LINT_FORMAT_MK,
        "main_targets": ["build", "clean", "help", "lint", "package"],
        "check_targets": ["_check_markdownlint", "_check_jq", "_check_yq", "_check_shellcheck"],
        "owns_markdownlint_config": True,
    }
)


_GUARDS_MK = _mk(
    """\
install-hooks: _check_prek _check_commitlint ## Install git hooks (prek: pre-commit + commit-msg)
<TAB>@hp=$$(git config --get core.hooksPath 2>/dev/null || true); \\
<TAB>if [ -n "$$hp" ]; then git config --local core.hooksPath .git/hooks; fi; \\
<TAB>prek install --hook-type pre-commit --hook-type commit-msg; rc=$$?; \\
<TAB>if [ -n "$$hp" ]; then git config --local --unset core.hooksPath 2>/dev/null || true; fi; \\
<TAB>if [ $$rc -eq 0 ]; then echo "OK git hooks installed"; else echo "prek install failed"; exit $$rc; fi

_check_prek:
<TAB>@command -v prek >/dev/null 2>&1 || { echo "prek not found - see SETUP_ENV.md#prek"; exit 1; }

_check_commitlint:
<TAB>@command -v commitlint >/dev/null 2>&1 || { echo "commitlint not found - see SETUP_ENV.md#commitlint"; exit 1; }
"""
)

LAYERS["guards"].update(
    {
        "owned": [("commitlint.config.js", "commitlint.config.js")],
        "setup_env_sections": ["commitlint", "prek", "git-hooks"],
        "mk": _GUARDS_MK,
        "main_targets": ["install-hooks"],
        "check_targets": ["_check_prek", "_check_commitlint"],
        "owns_prek_config": True,
    }
)
