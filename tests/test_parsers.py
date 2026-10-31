# SPDX-License-Identifier: Apache-2.0
import json

import pytest

from guard.parsers import parse_manifest


def write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return str(tmp_path)


def test_package_json_dev_dependencies_only_with_flag(tmp_path):
    folder = write(tmp_path, "package.json",
                   {"name": "app", "dependencies": {"a": "1.0.0"}, "devDependencies": {"b": "2.0.0"}})
    assert [r.name for r in parse_manifest(folder).roots] == ["a"]
    assert [r.name for r in parse_manifest(folder, include_dev=True).roots] == ["a", "b"]


def test_requirements_comments_extras_options_and_urls(tmp_path):
    folder = write(tmp_path, "requirements.txt",
                   "# a comment\n-r other.txt\nRequests[security]==2.31.0  # inline\n"
                   "git+https://example.invalid/x.git\nSome_Pkg>=1.2\nplain\n")
    roots = {r.name: r.version for r in parse_manifest(folder).roots}
    assert roots == {"requests": "2.31.0", "some-pkg": ">=1.2", "plain": "*"}


def test_lockfile_v3_pins_exact_versions(tmp_path):
    folder = write(tmp_path, "package-lock.json", {
        "name": "app", "lockfileVersion": 3,
        "packages": {"": {"dependencies": {"a": "^1.0.0"}},
                     "node_modules/a": {"version": "1.4.2"},
                     "node_modules/a/node_modules/b": {"version": "0.9.0"}}})
    m = parse_manifest(folder)
    assert m.pins == {"a": "1.4.2", "b": "0.9.0"}
    assert m.roots[0].version == "1.4.2"


def test_lockfile_v1_nested_dependencies(tmp_path):
    folder = write(tmp_path, "package-lock.json", {
        "name": "app", "lockfileVersion": 1,
        "dependencies": {"a": {"version": "1.0.0", "dependencies": {"b": {"version": "2.0.0"}}}}})
    m = parse_manifest(folder)
    assert m.pins == {"a": "1.0.0", "b": "2.0.0"}
    assert [r.name for r in m.roots] == ["a"]


def test_folder_without_manifest_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_manifest(str(tmp_path))
