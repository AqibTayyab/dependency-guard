# SPDX-License-Identifier: Apache-2.0
"""Phase 3 check: every flawed fixture trips its intended signal; every clean control scores < 35.
Run:  python -m pytest -q      (or)      python -m tests.test_extra_fixtures"""
import os

from guard.heuristics import analyze
from guard.resolver import MockRegistry
from guard.verdict import REVIEW_AT, decide

REG = os.path.join(os.path.dirname(__file__), "..", "fixtures", "extra_registry.json")

FLAWED = {  # package -> signals that MUST fire
    "deploy-helper": {"credential_access", "install_time_execution", "network_in_install"},
    "fast-resize-kit": {"obfuscation", "install_time_execution"},
    "legacy-date-fmt": {"publish_anomaly", "install_time_execution", "network_in_install"},
    "axois": {"typosquat"},
    "build-cache-helper": {"credential_access", "prompt_injection_attempt"},
}
CLEAN = ["date-fmt-lite", "node-version-check", "http-client-lite", "ui-kit-core"]


def _signals(name):
    info = MockRegistry(REG).get("npm", name, "*")
    assert info is not None, f"{name} missing from extra_registry.json"
    return analyze(info)


def test_flawed_fixtures_trip_intended_signals():
    for name, expected in FLAWED.items():
        ids = {s.id for s in _signals(name)}
        assert expected <= ids, f"{name}: expected {expected}, got {ids}"
        assert decide(_signals(name))[1] != "OK", f"{name} should not be OK"


def test_clean_controls_stay_below_review():
    for name in CLEAN:
        score, verdict = decide(_signals(name))
        assert score < REVIEW_AT and verdict == "OK", f"{name}: {score} {verdict}"


if __name__ == "__main__":
    test_flawed_fixtures_trip_intended_signals()
    test_clean_controls_stay_below_review()
    print(f"OK: {len(FLAWED)} flawed fixtures detected, {len(CLEAN)} clean controls passed")
