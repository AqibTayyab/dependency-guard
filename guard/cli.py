# SPDX-License-Identifier: Apache-2.0
"""Command line:  python -m guard scan <folder-or-file> --mock fixtures/starter_registry.json"""
from __future__ import annotations

import argparse
import json
import sys

from . import chain, reputation
from .explain import explain
from .heuristics import analyze, relevant_snippet
from .parsers import parse_manifest
from .report import build_report
from .resolver import LiveNpmRegistry, LivePyPIRegistry, MockRegistry, resolve
from .verdict import decide, reputation_signals
from .models import Reputation


def _pick_registry(manifest, mock_path):
    if mock_path:
        return MockRegistry(mock_path)
    return LiveNpmRegistry() if manifest.ecosystem == "npm" else LivePyPIRegistry()


def scan(args) -> int:
    manifest = parse_manifest(args.path, include_dev=args.include_dev)
    registry = _pick_registry(manifest, args.mock)
    tree = resolve(manifest, registry, max_depth=args.max_depth)

    resolved = [n.info.ref for n in tree.nodes if n.info]
    reps = reputation.lookup(resolved)  # <- Person B's Snowflake lookup (stub for now)

    print(f"\nDependency Guard - {manifest.app_name} ({manifest.ecosystem}) - {len(tree.nodes)} packages\n")
    findings = []
    for node in tree.nodes:
        signals = []
        if node.info:
            signals += analyze(node.info)
            signals += reputation_signals(reps.get(node.info.ref.key, Reputation()))
        else:
            print(f"  [note] {node.ref.key} not found in registry (skipped)")
        score, verdict = decide(signals)
        print(f"{'  ' * (node.depth - 1)}{node.ref.name}@{node.ref.version}  ->  {verdict} ({score})")
        if verdict == "OK":
            continue
        finding = {
            "package": node.ref.key, "path": node.path, "verdict": verdict, "score": score,
            "signals": [vars(s) for s in signals],
        }
        finding["explanation"] = explain(finding, relevant_snippet(node.info), use_llm=not args.no_llm)
        findings.append(finding)

    if tree.truncated:
        print("\n  [note] tree was cut at the depth/size limit; raise --max-depth to look deeper")
    print("\n=== FINDINGS ===")
    if not findings:
        print("Nothing suspicious found.")
    for f in findings:
        print(f"\n[{f['verdict']}] {f['package']}  (score {f['score']})")
        print("  path: " + " -> ".join(f["path"]))
        for s in f["signals"]:
            print(f"  - {s['id']} (+{s['weight']}): {s['evidence']}")
        e = f["explanation"]
        print(f"  explanation [{e['source']}]: {e['summary']}")
        print(f"  what to do: {e['what_to_do']}")

    report = build_report(manifest, args.path, tree, findings, scanned=len(tree.nodes))
    if args.chain:
        report["chain"] = chain.log(report)  # <- Person B's Solana logger (stub for now)
        print(f"\nOnchain record: {report['chain']['signature']}"
              + ("  (SIMULATED)" if report["chain"].get("simulated") else ""))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nVerdict: {report['summary']['verdict']}   report: {args.out}   sha256: {report['report_sha256'][:16]}...")
    return {"OK": 0, "REVIEW": 1, "BLOCK": 2}[report["summary"]["verdict"]]


def main() -> None:
    parser = argparse.ArgumentParser(prog="guard")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("scan", help="scan a manifest and its whole dependency tree")
    p.add_argument("path", help="folder or file (package.json, package-lock.json, requirements.txt)")
    p.add_argument("--mock", help="use a mock registry JSON instead of the real registries")
    p.add_argument("--out", default="report.json")
    p.add_argument("--max-depth", type=int, default=4)
    p.add_argument("--include-dev", action="store_true")
    p.add_argument("--no-llm", action="store_true", help="skip Gemma, use template explanations")
    p.add_argument("--chain", action="store_true", help="log the report onchain (stub until Person B is done)")
    args = parser.parse_args()
    sys.exit(scan(args))
