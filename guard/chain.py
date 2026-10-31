# SPDX-License-Identifier: Apache-2.0
"""STUB - Person B replaces log() with the real Solana logger (calls the Node bridge in chain/).
KEEP THE SIGNATURE: log(report dict) -> {'signature': str, 'explorer_url': str|None, 'simulated': bool}"""
from __future__ import annotations


def log(report: dict) -> dict:
    return {
        "cluster": "none",
        "signature": "SIMULATED-" + report["report_sha256"][:16],
        "explorer_url": None,
        "simulated": True,
    }
