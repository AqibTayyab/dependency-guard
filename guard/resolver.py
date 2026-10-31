# SPDX-License-Identifier: Apache-2.0
"""Step 2: walk the dependency tree (dependencies of dependencies of ...).

A 'Registry' answers one question: 'tell me about package X at version Y'.
  - MockRegistry reads a local JSON file  -> safe, fast, deterministic (tests + demo)
  - LiveNpmRegistry / LivePyPIRegistry    -> real registries (TODO: write with Copilot, see below)
"""
from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional

from .models import Manifest, Node, PackageInfo, PkgRef

_EXACT = re.compile(r"^v?(\d+(?:\.\d+){0,2}(?:[-+][0-9A-Za-z.-]+)?)$")


def exact_version(spec: str) -> Optional[str]:
    """'1.2.3' or '=1.2.3' -> '1.2.3'.  Ranges like '^1.2.0' or '>=2' -> None."""
    m = _EXACT.match(spec.strip().lstrip("="))
    return m.group(1) if m else None


def _version_key(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v))


class Registry:
    def get(self, ecosystem: str, name: str, spec: str) -> Optional[PackageInfo]:
        raise NotImplementedError


class MockRegistry(Registry):
    """Reads fixtures/*.json. Format: {"packages": {"npm:name@1.0.0": {...}}}"""

    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self._items: dict = {}
        for key, raw in data["packages"].items():
            eco_name, version = key.rsplit("@", 1)  # rsplit so '@scope/name@1.0.0' works
            eco, name = eco_name.split(":", 1)
            info = PackageInfo(
                ref=PkgRef(eco, name, version),
                dependencies=raw.get("dependencies", {}),
                scripts=raw.get("scripts", {}),
                files=raw.get("files", {}),
                package_age_days=raw.get("package_age_days"),
                maintainer_changed=raw.get("maintainer_changed", False),
                dormant_days_before_release=raw.get("dormant_days_before_release"),
            )
            self._items.setdefault((eco, name), {})[version] = info

    def get(self, ecosystem: str, name: str, spec: str) -> Optional[PackageInfo]:
        versions = self._items.get((ecosystem, name))
        if not versions:
            return None
        wanted = exact_version(spec)
        if wanted:
            return versions.get(wanted)  # exact version we do not know -> unknown package
        return versions[max(versions, key=_version_key)]  # a range: take the highest we have


class LiveNpmRegistry(Registry):
    """TODO (Copilot task A1b): real npm registry lookups.

    Copilot prompt idea:
      'Implement get(ecosystem, name, spec) using https://registry.npmjs.org/<name>/<version>
       with urllib (no extra libs). If spec is not an exact version use "latest". Return a
       PackageInfo with dependencies and scripts. Handle 404 by returning None, add a 10 s
       timeout and a small in-memory cache.'
    """

    def get(self, ecosystem: str, name: str, spec: str) -> Optional[PackageInfo]:
        raise NotImplementedError("LiveNpmRegistry is not written yet - use --mock for now")


class LivePyPIRegistry(Registry):
    """TODO (Copilot task A1b): real PyPI lookups via https://pypi.org/pypi/<name>/<version>/json
    (dependencies are in info.requires_dist - ignore entries with 'extra ==' markers)."""

    def get(self, ecosystem: str, name: str, spec: str) -> Optional[PackageInfo]:
        raise NotImplementedError("LivePyPIRegistry is not written yet - use --mock for now")


@dataclass
class Tree:
    nodes: List[Node] = field(default_factory=list)
    truncated: bool = False  # True if we stopped early (depth or node cap)


def resolve(manifest: Manifest, registry: Registry, max_depth: int = 4, max_nodes: int = 300) -> Tree:
    """Breadth-first walk. Every package is visited once; we remember the FIRST path to it."""
    tree = Tree()
    seen: set = set()
    queue: deque = deque((ref, [manifest.app_name], 1) for ref in manifest.roots)

    while queue:
        ref, parent_path, depth = queue.popleft()
        spec = manifest.pins.get(ref.name, ref.version)  # lockfile pin beats a range
        info = registry.get(ref.ecosystem, ref.name, spec)
        resolved = info.ref if info else PkgRef(ref.ecosystem, ref.name, spec)
        if resolved.key in seen:
            continue
        if len(tree.nodes) >= max_nodes:
            tree.truncated = True
            break
        seen.add(resolved.key)

        path = parent_path + [f"{resolved.name}@{resolved.version}"]
        tree.nodes.append(Node(ref=resolved, path=path, depth=depth, info=info))

        if info and info.dependencies:
            if depth >= max_depth:
                tree.truncated = True  # there is more below, but we stop here
            else:
                for dep_name, dep_spec in info.dependencies.items():
                    queue.append((PkgRef(ref.ecosystem, dep_name, str(dep_spec)), path, depth + 1))
    return tree
