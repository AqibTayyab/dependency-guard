# SPDX-License-Identifier: Apache-2.0
"""Thresholds are the contract: REVIEW >= 35, BLOCK >= 70, known_malicious always BLOCK."""
from guard.models import Reputation, Signal
from guard.verdict import decide, reputation_signals


def sig(weight, id="x"):
    return Signal(id, weight, "test")


def test_thresholds():
    assert decide([]) == (0, "OK")
    assert decide([sig(34)])[1] == "OK"
    assert decide([sig(35)])[1] == "REVIEW"
    assert decide([sig(69)])[1] == "REVIEW"
    assert decide([sig(70)])[1] == "BLOCK"


def test_score_is_capped_at_100():
    assert decide([sig(60), sig(60)]) == (100, "BLOCK")


def test_known_malicious_is_always_block():
    assert decide([Signal("known_malicious", 5, "forced low weight")])[1] == "BLOCK"


def test_reputation_signals_mapping():
    assert reputation_signals(Reputation()) == []
    mal = reputation_signals(Reputation(vuln_count=1, has_malware=True, advisory_ids=["MAL-1"]))
    assert [s.id for s in mal] == ["known_malicious"]
    vuln = reputation_signals(Reputation(vuln_count=2, max_severity="HIGH", advisory_ids=["A", "B"]))
    assert vuln[0].id == "known_vulnerability" and vuln[0].weight == 30
