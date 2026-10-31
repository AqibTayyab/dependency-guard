# SPDX-License-Identifier: Apache-2.0
"""Run the real CLI as a subprocess on the fixtures (no Gemma, no network, mock registry)."""
import json
import os
import subprocess
import sys

from .helpers import FIXTURES, ROOT


def scan(app, registry, tmp_path):
    out = tmp_path / "report.json"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop("GEMMA_MODEL", None)
    proc = subprocess.run(
        [sys.executable, "-m", "guard", "scan", os.path.join(FIXTURES, app), "--mock",
         os.path.join(FIXTURES, registry), "--no-llm", "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, env=env, timeout=60)
    return proc, json.loads(out.read_text(encoding="utf-8"))


def test_trap_app_finds_four_planted_problems_and_blocks(tmp_path):
    proc, report = scan("trap-app", "starter_registry.json", tmp_path)
    assert proc.returncode == 2
    assert {f["package"] for f in report["findings"]} == {
        "npm:acme-telemetry@3.0.0", "npm:fast-cacher@0.0.3", "npm:lodahs@1.0.0", "npm:flatmap-stream@0.1.1"}
    assert report["summary"]["max_depth"] == 4  # flatmap-stream is the 4th package down the chain
    assert report["summary"]["verdict"] == "BLOCK"


def test_pypi_example_flags_the_typosquat(tmp_path):
    proc, report = scan("trap-app-py", "starter_registry.json", tmp_path)
    assert report["ecosystem"] == "pypi"
    assert any(f["package"].startswith("pypi:requets@") for f in report["findings"])


def test_extra_app_blocks_on_the_ssh_key_reader(tmp_path):
    proc, report = scan("extra-app", "extra_registry.json", tmp_path)
    assert proc.returncode == 2
    deploy = [f for f in report["findings"] if f["package"].startswith("npm:deploy-helper")][0]
    assert deploy["path"][-2].startswith("ui-kit-core")  # found one level below its parent


def test_report_file_hash_verifies(tmp_path):
    from guard.report import attach_hash
    _, report = scan("trap-app", "starter_registry.json", tmp_path)
    stored = report["report_sha256"]
    assert attach_hash({k: v for k, v in report.items() if k != "report_sha256"})["report_sha256"] == stored
