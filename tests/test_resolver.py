# SPDX-License-Identifier: Apache-2.0
from guard.models import Manifest, PkgRef
from guard.resolver import _parse_requires_dist, exact_version, resolve

from .helpers import mock_registry


def manifest(*names):
    return Manifest("app", "npm", [PkgRef("npm", n, "1.0.0") for n in names])


def chain_registry(tmp_path, length):
    pk = {}
    for i in range(length):
        nxt = {"dependencies": {f"p{i + 1}": "1.0.0"}} if i < length - 1 else {}
        pk[f"npm:p{i}@1.0.0"] = nxt
    return mock_registry(tmp_path, pk)


def test_exact_version_parsing():
    assert exact_version("1.2.3") == "1.2.3"
    assert exact_version("=1.2.3") == "1.2.3"
    assert exact_version("^1.2.0") is None
    assert exact_version(">=2") is None


def test_depth_limit_marks_tree_truncated(tmp_path):
    tree = resolve(manifest("p0"), chain_registry(tmp_path, 8), max_depth=3)
    assert [n.depth for n in tree.nodes] == [1, 2, 3]
    assert tree.truncated is True


def test_package_four_levels_deep_is_reached(tmp_path):
    tree = resolve(manifest("p0"), chain_registry(tmp_path, 4), max_depth=4)
    assert len(tree.nodes) == 4 and tree.truncated is False


def test_cycle_terminates(tmp_path):
    reg = mock_registry(tmp_path, {"npm:a@1.0.0": {"dependencies": {"b": "1.0.0"}},
                                   "npm:b@1.0.0": {"dependencies": {"a": "1.0.0"}}})
    assert len(resolve(manifest("a"), reg).nodes) == 2


def test_diamond_keeps_first_path(tmp_path):
    reg = mock_registry(tmp_path, {
        "npm:top@1.0.0": {"dependencies": {"l": "1.0.0", "r": "1.0.0"}},
        "npm:l@1.0.0": {"dependencies": {"shared": "1.0.0"}},
        "npm:r@1.0.0": {"dependencies": {"shared": "1.0.0"}},
        "npm:shared@1.0.0": {}})
    tree = resolve(manifest("top"), reg)
    shared = [n for n in tree.nodes if n.ref.name == "shared"]
    assert len(shared) == 1 and shared[0].path == ["app", "top@1.0.0", "l@1.0.0", "shared@1.0.0"]


def test_unknown_package_becomes_node_without_info(tmp_path):
    reg = mock_registry(tmp_path, {"npm:a@1.0.0": {}})
    tree = resolve(manifest("a", "ghost"), reg)
    assert [n.info is None for n in tree.nodes] == [False, True]


def test_mock_registry_range_picks_highest_version(tmp_path):
    reg = mock_registry(tmp_path, {"npm:a@1.2.0": {}, "npm:a@1.10.0": {}, "npm:a@1.9.0": {}})
    assert reg.get("npm", "a", "^1.0.0").ref.version == "1.10.0"


def test_pypi_requires_dist_ignores_extras_and_parses_names():
    deps = _parse_requires_dist([
        "urllib3 (<3,>=1.21.1)", "PySocks (!=1.5.7,>=1.5.6) ; extra == 'socks'",
        "certifi>=2017.4.17", "idna"])
    assert deps == {"urllib3": "<3,>=1.21.1", "certifi": ">=2017.4.17", "idna": "*"}
