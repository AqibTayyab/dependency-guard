# SPDX-License-Identifier: Apache-2.0
"""Small helpers shared by the tests."""
import json
import os

from guard.models import PackageInfo, PkgRef
from guard.resolver import MockRegistry

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURES = os.path.join(ROOT, "fixtures")


def pkg(name="demo", version="1.0.0", eco="npm", **kw) -> PackageInfo:
    return PackageInfo(ref=PkgRef(eco, name, version), **kw)


def mock_registry(tmp_path, packages: dict) -> MockRegistry:
    """packages = {'npm:a@1.0.0': {'dependencies': {...}, ...}} -> MockRegistry on a temp file."""
    path = tmp_path / "reg.json"
    path.write_text(json.dumps({"packages": packages}), encoding="utf-8")
    return MockRegistry(str(path))
