# SPDX-License-Identifier: Apache-2.0
"""One-page UI for Dependency Guard. Runs the real CLI and shows its results.

Run from the repo root:  streamlit run ui/app.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
COLORS = {"OK": "#16A34A", "REVIEW": "#D97706", "BLOCK": "#DC2626"}
EXIT_NAMES = {0: "OK", 1: "REVIEW", 2: "BLOCK"}

st.set_page_config(page_title="Dependency Guard", page_icon="🛡️", layout="wide")


def badge(text, verdict):
    color = COLORS.get(verdict, "#6B7280")
    return (f"<span style='background:{color};color:white;padding:2px 10px;"
            f"border-radius:10px;font-weight:600'>{text}</span>")


st.title("Dependency Guard")
st.caption("Rules decide, the LLM only explains. The verdict and score are the authority.")

with st.sidebar:
    st.header("Scan settings")
    path = st.text_input("Project folder or manifest", "fixtures/trap-app")
    mock = st.selectbox("Registry", ["fixtures/starter_registry.json",
                                     "fixtures/extra_registry.json",
                                     "Live npm / PyPI (limited)"])
    use_llm = st.checkbox("Use Gemma 4 explanations", value=False)
    model = st.text_input("GEMMA_MODEL", os.environ.get("GEMMA_MODEL", "gemma4:e2b"),
                          disabled=not use_llm)
    chain = st.checkbox("Log report hash (--chain)", value=False)
    st.caption("Reputation and chain output is SIMULATED unless the real modules are merged.")
    go = st.button("Scan", type="primary", use_container_width=True)

if go:
    out_file = Path(tempfile.gettempdir()) / "depguard_ui_report.json"
    cmd = [sys.executable, "-m", "guard", "scan", path, "--out", str(out_file)]
    if not mock.startswith("Live"):
        cmd += ["--mock", mock]
    if not use_llm:
        cmd.append("--no-llm")
    if chain:
        cmd.append("--chain")
    env = dict(os.environ)
    if use_llm:
        env["GEMMA_MODEL"] = model
    with st.spinner("Scanning... Gemma can take several minutes on a first run."):
        try:
            res = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                                 text=True, timeout=900)
        except subprocess.TimeoutExpired:
            st.error("Scan timed out after 15 minutes.")
            st.stop()
    # Exit codes 0/1/2 mean OK/REVIEW/BLOCK, not failure.
    if res.returncode not in EXIT_NAMES or not out_file.exists():
        st.error("The scan failed.")
        st.code((res.stderr or res.stdout or "no output").strip())
        st.stop()
    try:
        report = json.loads(out_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        st.error(f"Could not read the report: {exc}")
        st.stop()

    summ = report.get("summary", {})
    verdict = summ.get("verdict") or EXIT_NAMES[res.returncode]
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown("**Verdict**<br>" + badge(verdict, verdict), unsafe_allow_html=True)
    c2.metric("Score", summ.get("score", "-"))
    c3.metric("Packages scanned", summ.get("packages_scanned", "-"))
    c4.metric("Max depth", summ.get("max_depth", "-"))
    if summ.get("tree_truncated"):
        st.warning("The tree was truncated at the depth or node limit.")

    st.subheader("Findings")
    findings = report.get("findings", [])
    if not findings:
        st.success("No findings.")
    for f in findings:
        v = f.get("verdict", "?")
        with st.container(border=True):
            st.markdown(badge(f"{v} ({f.get('score', '?')})", v) +
                        f" &nbsp; **{f.get('package', '?')}**", unsafe_allow_html=True)
            st.caption("Path: " + " → ".join(f.get("path", [])))
            for s in f.get("signals", []):
                st.markdown(f"- `{s.get('id')}` (+{s.get('weight')}): {s.get('evidence')}")
            exp = f.get("explanation")
            if isinstance(exp, dict):
                st.markdown(f"**Explanation [{exp.get('source', '?')}]:** {exp.get('summary', '')}")
                if exp.get("what_to_do"):
                    st.markdown(f"**What to do:** {exp['what_to_do']}")

    ch = report.get("chain") or {}
    if ch:
        st.subheader("On-chain log")
        sim = ch.get("simulated")
        st.markdown(badge("SIMULATED", "BLOCK") if sim else badge("REAL", "OK"),
                    unsafe_allow_html=True)
        st.code(ch.get("signature", ""))
        if ch.get("explorer_url"):
            st.link_button("Open in explorer", ch["explorer_url"])
    st.caption(f"Report SHA-256: {report.get('report_sha256', '')}")

    with st.expander("Full scan output (dependency tree)"):
        st.code(res.stdout)
else:
    st.info("Choose settings in the sidebar and press Scan. The first Gemma run is slow; "
            "leave it off for a fast demo.")
