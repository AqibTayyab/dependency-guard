# Person A - phased work plan (handoff-ready)

Rules for working through this file
- One phase at a time. At the end of each phase: run its "Done when" command, `git commit`, tick it in `docs/STATUS.md`.
- If Claude (or any assistant) hits a usage limit: open a new chat, attach the repo (public link or the zip) AND this file,
  paste the handoff prompt below, and fill in the phase number.

## Handoff prompt (copy-paste into a new Claude chat)

```
I am Person A in a 2-person, 2-hour hackathon team (challenge: "Dependency Trap Code Guard").
I attached our repo (dependency-guard) and docs/PERSON_A_PHASES.md. Read both first.
Current phase: <N>. Do ONLY this phase.
Rules: Python 3.9+, standard library only (except where the phase says otherwise); do not change the
contracts in this file; put `# SPDX-License-Identifier: Apache-2.0` at the top of new files; keep fixtures
inert (never executed, only .invalid domains); never put keys or tokens in files.
Tell me exactly which commands to run to verify. Say clearly what you could NOT verify. We are short on time: be fast.
```

## Project context (for any assistant reading this)

What it is: an autonomous agent that scans a manifest (package.json / package-lock.json / requirements.txt), walks the
whole recursive dependency tree, scores every package with RULES + Snowflake (OSV) reputation data, has Gemma 4 explain
findings in plain language, and logs a hash of each report on Solana. Design rule: **rules decide, the LLM only explains.**

Pipeline (files in guard/):
1. parsers.py   manifest file -> Manifest(app_name, ecosystem, roots, pins)
2. resolver.py  Registry.get(ecosystem, name, spec) -> PackageInfo; resolve() walks the tree (depth<=4, 300 nodes), keeps first path
3. heuristics.py  analyze(PackageInfo) -> [Signal]; all weights in WEIGHTS
4. verdict.py   reputation_signals(Reputation) + decide(signals) -> (score, OK|REVIEW|BLOCK); REVIEW>=35, BLOCK>=70, known_malicious always BLOCK
5. explain.py   explain(finding, snippet) -> {summary, why_it_matters, what_to_do, source}; Gemma via Ollama, template fallback
6. report.py    build_report(...) + sha256 over everything except `chain` and `report_sha256`
7. cli.py       `python -m guard scan <path> [--mock FILE] [--no-llm] [--chain] [--out FILE]`; exit code 0/1/2 = OK/REVIEW/BLOCK

Contracts (Person B owns the real versions; DO NOT change names or shapes):
```
reputation.lookup(pkgs: list[PkgRef]) -> dict[str, Reputation]      key = "ecosystem:name@version"
   Reputation(vuln_count, has_malware, max_severity, advisory_ids)
chain.log(report: dict) -> {"signature": str, "explorer_url": str|None, "simulated": bool, "cluster": str}
explain.explain(finding: dict, snippet: str, use_llm: bool) -> {summary, why_it_matters, what_to_do, source}
finding = {package, path[], verdict, score, signals:[{id, weight, evidence}]}
ScanReport = {scan_id, created_at, input_file, ecosystem, app, summary{packages_scanned, max_depth, tree_truncated, verdict, score},
              findings[], report_sha256, chain{...}}
```

Verified state of the starter (tested in a sandbox, no real Ollama, no real registries):
- WORKS: scan of fixtures/trap-app (finds 4 planted problems, incl. a package 4 levels deep), PyPI example, lockfile parsing,
  report hashing, graceful fallback to template text when Gemma is unreachable.
- NOT YET VERIFIED: the real Ollama call (only the failure path was tested), anything involving real registries.
- NOT WRITTEN: LiveNpmRegistry / LivePyPIRegistry, test suite, UI. Reputation and chain are SIMULATED stubs until Person B replaces them.
- KNOWN LIMITS: rules only catch known patterns; typosquat list is ~45 names per ecosystem; weights differ slightly from the
  playbook doc (typosquat is 35 in code, 30 in the doc - code wins).

Honesty rules: the starter skeleton was drafted with Claude. Only log in COPILOT_LOG.md what GitHub Copilot really did.
Anything simulated must be labelled SIMULATED in output and README.

## Phases

### Phase 0 - Repo + first run (10 min)
- Create the public GitHub repo (Apache-2.0), push the starter, invite Person B, run the first scan.
- Files: none new. Copilot: no.
- Done when: `python -m guard scan fixtures/trap-app --mock fixtures/starter_registry.json --no-llm` prints 4 findings and the repo is public with LICENSE.

### Phase 1 - Gemma 4 switched on (10 min)
- `ollama pull` Gemma 4, find the exact tag with `ollama list` (do not guess), set `GEMMA_MODEL=<tag>`.
- Run the scan WITHOUT `--no-llm`. Fix anything in `explain.py` that breaks against the real server (e.g. wrong JSON keys, timeouts).
- Done when: output shows `explanation [gemma]` for findings, a second run shows `[cache]`, and `.cache/explanations.json` exists.
- Fallback: if Gemma is too slow, try a smaller variant; keep `[template]` as the demo fallback and say so honestly.

### Phase 2 - Live registries (15 min) - USE COPILOT
- Implement `LiveNpmRegistry` and `LivePyPIRegistry` in `resolver.py` (prompts are in the code docstrings). stdlib `urllib` only,
  10 s timeout, small in-memory cache, 404 -> None.
- Compute `package_age_days` if cheaply possible (optional; skip if it slows you down).
- Done when: with a tiny package.json containing `{"dependencies": {"chalk": "4.1.2"}}`, `python -m guard scan <folder> --no-llm` (no --mock)
  lists the tree without crashing. Log the Copilot prompt and result in COPILOT_LOG.md.
- Fallback: keep MockRegistry as the demo path; say in README that live mode is limited.

### Phase 3 - More fixtures (10 min) - USE COPILOT
- Ask Copilot for 3-5 more INERT flawed fixtures (e.g. SSH-key reader, base64+eval loader, dormant-then-updated package) plus 3 clean controls,
  added to `fixtures/` (a second mock registry file is fine, e.g. `fixtures/extra_registry.json`).
- Done when: every flawed fixture trips its intended signal, every clean control scores below 35. Log it in COPILOT_LOG.md.
- Safety: never real payloads; domains end in `.invalid`; the scanner never executes fixture code.

### Phase 4 - Integration with Person B (20 min)  [team gate G2]
- Replace the stubs' use with Person B's real `reputation.py` and `chain.py` (same signatures). Pull their changes, run end-to-end.
- Check: `--chain` returns a real signature; reputation shows real advisory IDs; `DEPGUARD_OFFLINE=1` still works with stubs/cache.
- Run 3 live scans for Person B's evidence file (`docs/EVIDENCE.md`).
- Done when: `python -m guard scan fixtures/trap-app --mock fixtures/starter_registry.json --chain` ends with a real signature and exit code 2.
- If B is late: demo with the SIMULATED stubs, label clearly, keep going.

### Phase 5 - Test suite (25 min) - USE COPILOT  [team gate G3 = feature freeze at ~1:40]
- `pip install pytest`. Create `tests/` with at least 15 tests: one per signal, negative controls (clean packages), verdict thresholds,
  parser edge cases (comments, extras, lockfile v1/v3), tree depth/cycle handling, end-to-end on trap-app, report hash stays stable.
- Done when: `python -m pytest -q` is green. Put a small detection table in the README (flawed fixtures found / clean controls passed).
- Log the prompts in COPILOT_LOG.md.

### Phase 6 - One-page UI (OPTIONAL, 15 min) - USE COPILOT
- Only if Phase 5 is done before the freeze. Streamlit page: path input, tree, verdict colours, explanation, explorer link.
  Streamlit is the only extra dependency (put it in `requirements-ui.txt`).
- Done when: `streamlit run ui/app.py` shows the trap-app scan. Fallback: terminal screenshots in the README.

### Phase 7 - README + ship (15 min)
- README sections you own: overview, architecture, how Gemma is used, tests + detection table, Copilot section (from COPILOT_LOG.md), limitations.
- Final checks: LICENSE present, SPDX header on every source file, no secrets in git history, fresh clone runs the quick start.
- Done when: a teammate clones the repo to a new folder and the quick start works without edits.
