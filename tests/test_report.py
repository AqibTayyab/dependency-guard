# SPDX-License-Identifier: Apache-2.0
"""The hash covers scan_id + timestamp, so two scans never match. What must hold is that
a saved report can be re-verified, and that any edit breaks the match."""
import copy

from guard.models import Manifest, PkgRef
from guard.report import attach_hash, build_report
from guard.resolver import resolve

from .helpers import mock_registry


def make_report(tmp_path, findings=()):
    reg = mock_registry(tmp_path, {"npm:a@1.0.0": {}})
    m = Manifest("app", "npm", [PkgRef("npm", "a", "1.0.0")])
    return build_report(m, "package.json", resolve(m, reg), list(findings), scanned=1)


FINDING = {"package": "npm:a@1.0.0", "path": ["app", "a@1.0.0"], "verdict": "REVIEW", "score": 40, "signals": []}


def test_hash_recomputes_to_the_stored_value(tmp_path):
    r = make_report(tmp_path)
    again = attach_hash(copy.deepcopy({k: v for k, v in r.items() if k != "report_sha256"}))
    assert again["report_sha256"] == r["report_sha256"]


def test_tampering_changes_the_hash(tmp_path):
    r = make_report(tmp_path, [FINDING])
    forged = copy.deepcopy(r)
    forged["findings"][0]["verdict"] = "OK"
    assert attach_hash(forged)["report_sha256"] != r["report_sha256"]


def test_chain_field_does_not_affect_the_hash(tmp_path):
    r = make_report(tmp_path)
    before = r["report_sha256"]
    r["chain"] = {"signature": "abc", "simulated": True}
    assert attach_hash(r)["report_sha256"] == before


def test_summary_uses_worst_verdict(tmp_path):
    block = dict(FINDING, verdict="BLOCK", score=90)
    r = make_report(tmp_path, [FINDING, block])
    assert r["summary"]["verdict"] == "BLOCK" and r["summary"]["score"] == 90
