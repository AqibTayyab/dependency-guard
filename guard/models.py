# SPDX-License-Identifier: Apache-2.0
"""Shared data shapes. Keep these stable: Person B's modules use them too."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class PkgRef:
    """A package we want to look at: ecosystem + name + version (or a range like ^1.2.0)."""
    ecosystem: str  # 'npm' or 'pypi'
    name: str
    version: str

    @property
    def key(self) -> str:
        return f"{self.ecosystem}:{self.name}@{self.version}"


@dataclass
class PackageInfo:
    """Everything we know about ONE package after asking a registry."""
    ref: PkgRef                                       # ref.version is the exact resolved version
    dependencies: dict = field(default_factory=dict)  # name -> version spec
    scripts: dict = field(default_factory=dict)       # npm scripts (preinstall, postinstall, ...)
    files: dict = field(default_factory=dict)         # path -> source text we can inspect
    package_age_days: Optional[int] = None            # days since the package was first published
    maintainer_changed: bool = False
    dormant_days_before_release: Optional[int] = None


@dataclass
class Signal:
    """One reason a package looks risky."""
    id: str
    weight: int
    evidence: str


@dataclass
class Reputation:
    """What Snowflake (OSV data) knows about a package. Person B fills this in."""
    vuln_count: int = 0
    has_malware: bool = False
    max_severity: str = "NONE"  # NONE, LOW, MODERATE, HIGH, CRITICAL
    advisory_ids: List[str] = field(default_factory=list)


@dataclass
class Node:
    """One package found in the tree, with the path that led to it."""
    ref: PkgRef
    path: List[str]               # e.g. ['trap-app', 'harmless-utils@1.0.0', 'evil@0.1.1']
    depth: int
    info: Optional[PackageInfo] = None  # None = registry did not know this package


@dataclass
class Manifest:
    """What we read from package.json / requirements.txt."""
    app_name: str
    ecosystem: str
    roots: List[PkgRef]
    pins: dict = field(default_factory=dict)  # exact versions from a lockfile: name -> version
