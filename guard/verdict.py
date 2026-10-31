# SPDX-License-Identifier: Apache-2.0
"""Step 4: turn signals into a verdict. Pure rules - NO AI here, on purpose."""
from __future__ import annotations

from typing import List, Tuple

from .models import Reputation, Signal

BLOCK_AT = 70
REVIEW_AT = 35
_SEVERITY_WEIGHT = {"CRITICAL": 40, "HIGH": 30, "MODERATE": 20, "MEDIUM": 20, "LOW": 10}


def reputation_signals(rep: Reputation) -> List[Signal]:
    """Signals that come from Snowflake data (Person B's lookup)."""
    ids = ", ".join(rep.advisory_ids[:3]) or "no id"
    if rep.has_malware:
        return [Signal("known_malicious", 100, f"listed as MALWARE in vulnerability data ({ids})")]
    if rep.vuln_count > 0:
        weight = _SEVERITY_WEIGHT.get(rep.max_severity.upper(), 10)
        return [Signal("known_vulnerability", weight,
                       f"{rep.vuln_count} known advisories, worst severity {rep.max_severity} ({ids})")]
    return []


def decide(signals: List[Signal]) -> Tuple[int, str]:
    """Return (score 0-100, 'OK' | 'REVIEW' | 'BLOCK')."""
    score = min(100, sum(s.weight for s in signals))
    if any(s.id == "known_malicious" for s in signals) or score >= BLOCK_AT:
        return score, "BLOCK"
    if score >= REVIEW_AT:
        return score, "REVIEW"
    return score, "OK"
