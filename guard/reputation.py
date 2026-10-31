# SPDX-License-Identifier: Apache-2.0
"""STUB - Person B replaces lookup() with the real Snowflake query (PKG_RISK view).
KEEP THE SIGNATURE: lookup(list of PkgRef) -> {pkg.key: Reputation}
This stub returns SIMULATED data so the rest of the pipeline can be built and demoed."""
from __future__ import annotations

from typing import Dict, List

from .models import PkgRef, Reputation

_CANNED = {
    "npm:flatmap-stream@0.1.1": Reputation(
        vuln_count=1, has_malware=True, max_severity="CRITICAL", advisory_ids=["SIMULATED-DEMO-1"]),
}


def lookup(pkgs: List[PkgRef]) -> Dict[str, Reputation]:
    return {p.key: _CANNED.get(p.key, Reputation()) for p in pkgs}
