# SPDX-License-Identifier: Apache-2.0
"""Step 2: walk the dependency tree (dependencies of dependencies of ...).

A 'Registry' answers one question: 'tell me about package X at version Y'.
  - MockRegistry reads a local JSON file  -> safe, fast, deterministic (tests + demo)
  - LiveNpmRegistry / LivePyPIRegistry    -> real registries (stdlib urllib, 10 s timeout, in-memory cache)
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
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


_TIMEOUT = 10  # seconds per registry request
_UA = {"User-Agent": "dependency-guard/0.1 (hackathon scanner)", "Accept": "application/json"}


def _fetch_json(url: str) -> Optional[dict]:
    """GET a JSON document. 404 -> None. Network problems -> None plus a note on stderr."""
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        print(f"  [registry] HTTP {exc.code} for {url}", file=sys.stderr)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        print(f"  [registry] could not reach {url}: {exc}", file=sys.stderr)
    return None


class LiveNpmRegistry(Registry):
    """Real npm lookups: https://registry.npmjs.org/<name>/<version>.

    Limits (say so in the README): a range such as ^1.2.0 is resolved to "latest", not to the
    highest version inside the range; package source files and publish history are not
    fetched, so file-based rules and publish_anomaly do not fire in live mode."""

    def __init__(self):
        self._cache: dict = {}

    def get(self, ecosystem: str, name: str, spec: str) -> Optional[PackageInfo]:
        wanted = exact_version(spec) or "latest"
        key = (name, wanted)
        if key not in self._cache:
            url = f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@')}/{wanted}"
            data = _fetch_json(url)
            info = None
            if data and data.get("version"):
                info = PackageInfo(
                    ref=PkgRef("npm", name, str(data["version"])),
                    dependencies=dict(data.get("dependencies") or {}),
                    scripts=dict(data.get("scripts") or {}),
                )
            self._cache[key] = info
        return self._cache[key]


_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _parse_requires_dist(entries) -> dict:
    """'urllib3 (<3,>=1.21.1)' -> {'urllib3': '<3,>=1.21.1'}; entries for extras are ignored."""
    deps: dict = {}
    for line in entries or []:
        req, _, marker = line.partition(";")
        if "extra" in marker:
            continue
        m = _REQ_NAME.match(req)
        if not m:
            continue
        rest = req[m.end():].strip().strip("()").strip()
        if rest.startswith("["):  # 'name[extra]>=1.0' -> drop the [extra] part
            rest = rest.split("]", 1)[-1].strip().strip("()").strip()
        deps[m.group(1)] = rest or "*"
    return deps


class LivePyPIRegistry(Registry):
    """Real PyPI lookups: https://pypi.org/pypi/<name>/<version>/json (deps = info.requires_dist).
    Same limits as npm: a range resolves to the latest release; no source files are fetched."""

    def __init__(self):
        self._cache: dict = {}

    def get(self, ecosystem: str, name: str, spec: str) -> Optional[PackageInfo]:
        wanted = exact_version(spec)  # '==2.31.0' and '2.31.0' both work
        key = (name.lower(), wanted or "latest")
        if key not in self._cache:
            path = f"{wanted}/json" if wanted else "json"
            data = _fetch_json(f"https://pypi.org/pypi/{urllib.parse.quote(name)}/{path}")
            info = None
            if data and data.get("info", {}).get("version"):
                info = PackageInfo(
                    ref=PkgRef("pypi", name, str(data["info"]["version"])),
                    dependencies=_parse_requires_dist(data["info"].get("requires_dist")),
                )
            self._cache[key] = info
        return self._cache[key]


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
