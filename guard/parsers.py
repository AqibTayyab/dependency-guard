# SPDX-License-Identifier: Apache-2.0
"""Step 1: read a manifest file (package.json, package-lock.json, requirements.txt)
and turn it into a list of ROOT packages (the ones the app asks for directly)."""
from __future__ import annotations

import json
import os
import re

from .models import Manifest, PkgRef

_REQ_LINE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(?:(==|>=|<=|~=|!=|>|<)\s*([^\s;,#]+))?"
)


def find_manifest_file(path: str) -> str:
    """Accept a file, or a folder (we then look for the usual manifest names)."""
    if os.path.isfile(path):
        return path
    for name in ("package-lock.json", "package.json", "requirements.txt"):
        candidate = os.path.join(path, name)
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(f"No package-lock.json, package.json or requirements.txt in {path}")


def parse_manifest(path: str, include_dev: bool = False) -> Manifest:
    file_path = find_manifest_file(path)
    base = os.path.basename(file_path)
    if base == "package.json":
        return _parse_package_json(file_path, include_dev)
    if base == "package-lock.json":
        return _parse_package_lock(file_path, include_dev)
    if base.endswith(".txt"):
        return _parse_requirements(file_path)
    raise ValueError(f"Unsupported manifest: {base}")


def _parse_package_json(file_path: str, include_dev: bool) -> Manifest:
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    deps = dict(data.get("dependencies", {}))
    if include_dev:
        deps.update(data.get("devDependencies", {}))
    roots = [PkgRef("npm", name, str(spec)) for name, spec in deps.items()]
    return Manifest(app_name=data.get("name", "app"), ecosystem="npm", roots=roots)


def _parse_package_lock(file_path: str, include_dev: bool) -> Manifest:
    """A lockfile gives EXACT versions for the whole tree, so we keep them as 'pins'."""
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    pins: dict = {}
    root_deps: dict = {}
    packages = data.get("packages")
    if packages:  # lockfile v2/v3
        for key, meta in packages.items():
            if key == "":
                root_deps = dict(meta.get("dependencies", {}))
                if include_dev:
                    root_deps.update(meta.get("devDependencies", {}))
            else:
                name = key.split("node_modules/")[-1]
                if "version" in meta:
                    pins[name] = meta["version"]
    else:  # lockfile v1 (nested 'dependencies')
        def walk(deps: dict) -> None:
            for name, meta in deps.items():
                pins[name] = meta.get("version", "*")
                walk(meta.get("dependencies", {}))
        walk(data.get("dependencies", {}))
        root_deps = {n: pins[n] for n in data.get("dependencies", {})}
    roots = [PkgRef("npm", n, pins.get(n, str(spec))) for n, spec in root_deps.items()]
    return Manifest(app_name=data.get("name", "app"), ecosystem="npm", roots=roots, pins=pins)


def _parse_requirements(file_path: str) -> Manifest:
    roots = []
    with open(file_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].strip()
            if not line or line.startswith("-") or "://" in line:
                continue  # skip comments, options like -r, and direct URLs
            m = _REQ_LINE.match(line)
            if not m:
                continue
            name = re.sub(r"[-_.]+", "-", m.group(1)).lower()
            op, ver = m.group(2), m.group(3)
            spec = ver if op == "==" else (f"{op}{ver}" if op else "*")
            roots.append(PkgRef("pypi", name, spec))
    app = os.path.basename(os.path.dirname(os.path.abspath(file_path))) or "app"
    return Manifest(app_name=app, ecosystem="pypi", roots=roots)
