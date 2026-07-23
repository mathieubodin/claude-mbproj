#!/usr/bin/env python3
"""Read and write the mbproj manifest (`.config/mbproj.toml`).

The manifest is the single source of truth (spine invariant I4): applied layers,
the plugin version that generated each, and detected/asked parameters. It is read
with the stdlib `tomllib` and written with a fixed, deterministic serializer so a
re-run for the same state is byte-identical (I2/I7).

State shape (also the JSON exchanged with the skill):

    {
      "plugin_version": "0.1.0",
      "layers": {"lint_format": {"applied": true, "version": "0.1.0"},
                 "guards": {"applied": false}, ...},
      "params": {"project_name": "my-repo", "vendored_dirs": ["vendor"]}
    }
"""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

import mbproj_common as common

MANIFEST_REL = Path(".config") / "mbproj.toml"
LAYER_ORDER = ("lint_format", "guards", "changelog", "agentic")


def default_state() -> dict:
    return {
        "plugin_version": common.plugin_version(),
        "layers": {name: {"applied": False} for name in LAYER_ORDER},
        "params": {"project_name": "", "vendored_dirs": []},
    }


def read(repo_root: Path) -> dict:
    """Return the manifest state; a missing manifest yields the default state."""
    path = repo_root / MANIFEST_REL
    if not path.exists():
        return default_state()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    state = default_state()
    state["plugin_version"] = str(
        raw.get("mbproj", {}).get("plugin_version", state["plugin_version"])
    )
    for name in LAYER_ORDER:
        layer = raw.get("layers", {}).get(name)
        if isinstance(layer, dict):
            applied = bool(layer.get("applied", False))
            entry = {"applied": applied}
            if applied and "version" in layer:
                entry["version"] = str(layer["version"])
            state["layers"][name] = entry
    params = raw.get("params", {})
    state["params"]["project_name"] = str(params.get("project_name", ""))
    vendored = params.get("vendored_dirs", [])
    state["params"]["vendored_dirs"] = (
        [str(x) for x in vendored] if isinstance(vendored, list) else []
    )
    return state


def _toml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(_toml_str(v) for v in values) + "]"


def serialize(state: dict) -> str:
    """Deterministically serialize state to TOML (fixed section and layer order)."""
    lines = [common.render_banner("hash").rstrip("\n"), ""]
    lines += ["[mbproj]", f'plugin_version = {_toml_str(state["plugin_version"])}', ""]
    lines.append("[layers]")
    for name in LAYER_ORDER:
        layer = state["layers"].get(name, {"applied": False})
        if layer.get("applied"):
            version = layer.get("version", state["plugin_version"])
            lines.append(f"{name} = {{ applied = true, version = {_toml_str(version)} }}")
        else:
            lines.append(f"{name} = {{ applied = false }}")
    lines += ["", "[params]"]
    lines.append(f'project_name = {_toml_str(state["params"]["project_name"])}')
    lines.append(f'vendored_dirs = {_toml_array(state["params"]["vendored_dirs"])}')
    return "\n".join(lines) + "\n"


def write(repo_root: Path, state: dict) -> None:
    common.write_text_atomic(repo_root / MANIFEST_REL, serialize(state))


# --- CLI ------------------------------------------------------------------
def _print_state(state: dict) -> None:
    json.dump(state, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mbproj manifest read/write")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_read = sub.add_parser("read", help="print the manifest state as JSON")
    p_read.add_argument("repo", type=Path)

    p_ensure = sub.add_parser("ensure", help="create the manifest if absent; print state")
    p_ensure.add_argument("repo", type=Path)

    p_write = sub.add_parser("write", help="write the manifest from a JSON state on stdin")
    p_write.add_argument("repo", type=Path)

    p_layer = sub.add_parser("set-layer", help="mark a layer applied/not, then write")
    p_layer.add_argument("repo", type=Path)
    p_layer.add_argument("name", choices=LAYER_ORDER)
    p_layer.add_argument("applied", choices=("true", "false"))
    p_layer.add_argument("--version", default=None)

    p_param = sub.add_parser("set-param", help="set project_name or vendored_dirs, then write")
    p_param.add_argument("repo", type=Path)
    p_param.add_argument("key", choices=("project_name", "vendored_dirs"))
    p_param.add_argument("values", nargs="*")

    args = parser.parse_args(argv)
    repo = args.repo.resolve()

    if args.cmd == "read":
        _print_state(read(repo))
    elif args.cmd == "ensure":
        state = read(repo)
        if not (repo / MANIFEST_REL).exists():
            write(repo, state)
        _print_state(state)
    elif args.cmd == "write":
        state = json.load(sys.stdin)
        write(repo, state)
        _print_state(read(repo))
    elif args.cmd == "set-layer":
        state = read(repo)
        applied = args.applied == "true"
        entry = {"applied": applied}
        if applied:
            entry["version"] = args.version or state["plugin_version"]
        state["layers"][args.name] = entry
        write(repo, state)
        _print_state(read(repo))
    elif args.cmd == "set-param":
        state = read(repo)
        if args.key == "project_name":
            state["params"]["project_name"] = args.values[0] if args.values else ""
        else:
            state["params"]["vendored_dirs"] = list(args.values)
        write(repo, state)
        _print_state(read(repo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
