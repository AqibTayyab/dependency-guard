# SPDX-License-Identifier: Apache-2.0
"""On-chain logging bridge. Calls chain/log-validation.js (Node + Solana devnet).

KEEP THE SIGNATURE: log(report dict) -> {'signature', 'explorer_url', 'simulated', 'cluster'}

Real logging needs: Node.js, `npm install` inside chain/, and DEPGUARD_KEYPAIR_PATH pointing to a
funded devnet keypair file kept OUTSIDE the repo. If any of that is missing, or DEPGUARD_OFFLINE=1,
or the call fails, this falls back to a SIMULATED result and says so (never silently pretends).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "chain" / "log-validation.js"


def _simulated(report: dict) -> dict:
    return {
        "cluster": "none",
        "signature": "SIMULATED-" + report["report_sha256"][:16],
        "explorer_url": None,
        "simulated": True,
    }


def _why_not_real() -> str:
    if os.environ.get("DEPGUARD_OFFLINE") == "1":
        return ""  # offline is a deliberate choice, stay quiet
    if not os.environ.get("DEPGUARD_KEYPAIR_PATH"):
        return "DEPGUARD_KEYPAIR_PATH is not set"
    if not shutil.which("node"):
        return "node was not found on PATH"
    if not (_ROOT / "chain" / "node_modules").is_dir():
        return "run `npm install` inside chain/ first"
    return None  # ready


def log(report: dict) -> dict:
    reason = _why_not_real()
    if reason is not None:
        if reason:
            print(f"[chain] SIMULATED: {reason}", file=sys.stderr)
        return _simulated(report)
    try:
        proc = subprocess.run(
            [shutil.which("node"), str(_SCRIPT)],
            input=json.dumps(report), capture_output=True, text=True,
            cwd=str(_ROOT), timeout=90,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout).strip() or "node exited with an error")
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        return {
            "cluster": "devnet",
            "signature": out["signature"],
            "explorer_url": out.get("explorer_url"),
            "simulated": False,
        }
    except Exception as exc:  # network, funds, bad JSON, timeout...
        print(f"[chain] SIMULATED: real logging failed ({exc})", file=sys.stderr)
        return _simulated(report)
