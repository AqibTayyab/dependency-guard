# SPDX-License-Identifier: Apache-2.0
"""Step 6: build the ScanReport (the shared contract) and hash it."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import List

_RANK = {"OK": 0, "REVIEW": 1, "BLOCK": 2}


def canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_report(manifest, input_file: str, tree, findings: List[dict], scanned: int) -> dict:
    worst = max((f["verdict"] for f in findings), key=lambda v: _RANK[v], default="OK")
    report = {
        "scan_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_file": input_file,
        "ecosystem": manifest.ecosystem,
        "app": manifest.app_name,
        "summary": {
            "packages_scanned": scanned,
            "max_depth": max((n.depth for n in tree.nodes), default=0),
            "tree_truncated": tree.truncated,
            "verdict": worst,
            "score": max((f["score"] for f in findings), default=0),
        },
        "findings": findings,
    }
    return attach_hash(report)


def attach_hash(report: dict) -> dict:
    """The hash covers everything EXCEPT 'chain' and 'report_sha256' (the signature comes later)."""
    body = {k: v for k, v in report.items() if k not in ("chain", "report_sha256")}
    report["report_sha256"] = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return report
