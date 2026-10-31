# SPDX-License-Identifier: Apache-2.0
"""Dependency Guard - one-page Streamlit UI.

Shows a scan report (verdict, dependency path, why it was flagged, plain-language
explanation, onchain record). Rules decide the verdict; the LLM only explains.

Run from the repo root:
    python -m guard scan fixtures/trap-app --mock fixtures/starter_registry.json --no-llm --out report.json
    pip install streamlit
    streamlit run ui/app.py
"""
import json
import shlex
import subprocess
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if HERE.name == "ui" else HERE
DEFAULT_REPORT = ROOT / "report.json"
DEFAULT_CMD = "python -m guard scan fixtures/trap-app --mock fixtures/starter_registry.json --no-llm --out report.json"

COLORS = {"BLOCK": "#c62828", "REVIEW": "#ef8f00", "OK": "#2e7d32"}
ORDER = {"BLOCK": 0, "REVIEW": 1, "OK": 2}

st.set_page_config(page_title="Dependency Guard", page_icon="🛡️", layout="wide")
st.markdown(
    """
    <style>
      .verdict {padding:18px 24px;border-radius:12px;color:#fff;font-size:28px;font-weight:700;}
      .pill {display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;
             font-weight:600;color:#fff;margin-right:6px;background:#555;}
      .path {font-family:monospace;font-size:14px;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("🛡️ Dependency Guard")
st.caption("Rules decide the verdict. The LLM only explains it.")


def as_text(x):
    return x if isinstance(x, str) else ("" if x is None else str(x))


def norm_explanation(ex):
    """Accept a dict (summary/why_it_matters/what_to_do) or a plain string."""
    if isinstance(ex, str):
        return {"summary": ex}
    if isinstance(ex, dict):
        out = dict(ex)
        if "what_to_do" not in out and "what to do" in out:
            out["what_to_do"] = out["what to do"]
        return out
    return {}


def norm_path(p):
    if isinstance(p, (list, tuple)):
        return " → ".join(as_text(i) for i in p)
    return as_text(p).replace("->", "→")


def load_text(text):
    start = text.find("{")
    return json.loads(text[start:]) if start >= 0 else None


# ---------- sidebar ----------
report = None
with st.sidebar:
    st.header("Report source")
    mode = st.radio("Choose", ["report.json on disk", "Upload JSON", "Run a scan"])

    if mode == "report.json on disk":
        path = Path(st.text_input("Path", str(DEFAULT_REPORT)))
        if path.exists():
            report = load_text(path.read_text(encoding="utf-8-sig"))
        else:
            st.warning("Not found. Run a scan first (see the command below).")
            st.code(DEFAULT_CMD, language="bash")

    elif mode == "Upload JSON":
        up = st.file_uploader("Report .json", type="json")
        if up:
            report = load_text(up.read().decode("utf-8-sig"))

    else:
        cmd = st.text_input("Scan command", DEFAULT_CMD)
        st.caption("Add --chain to log onchain (needs DEPGUARD_KEYPAIR_PATH).")
        if st.button("Run scan"):
            with st.spinner("Scanning..."):
                try:
                    out = subprocess.run(shlex.split(cmd), cwd=ROOT, capture_output=True, text=True, timeout=600)
                    args = shlex.split(cmd)
                    out_file = args[args.index("--out") + 1] if "--out" in args else "report.json"
                    rp = ROOT / out_file
                    if rp.exists():
                        report = load_text(rp.read_text(encoding="utf-8-sig"))
                    else:
                        st.error("Scan finished but no report file was written.")
                        st.code(out.stdout + out.stderr)
                except Exception as e:  # noqa: BLE001
                    st.error(f"Scan failed: {e}")

if not report:
    st.info("Pick a report in the sidebar to see results.")
    st.stop()

# ---------- summary ----------
summary = report.get("summary") or {}
verdict = as_text(summary.get("verdict") or report.get("verdict") or "OK")
color = COLORS.get(verdict, "#555")
score = summary.get("score", report.get("score", 0))

c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
c1.markdown(f'<div class="verdict" style="background:{color}">Verdict: {verdict}</div>', unsafe_allow_html=True)
c2.metric("Risk score", f"{score}/100")
c3.metric("Packages scanned", summary.get("packages_scanned", "-"))
c4.metric("Max depth", summary.get("max_depth", "-"))
st.caption(f"Input: `{report.get('input_file', '-')}` · Ecosystem: {report.get('ecosystem', '-')} · {report.get('created_at', '')}")

# ---------- findings ----------
st.subheader("Findings")
findings = report.get("findings") or []
if not findings:
    st.success("No findings.")

for f in sorted(findings, key=lambda x: ORDER.get(as_text(x.get("verdict")), 3)):
    v = as_text(f.get("verdict", "OK"))
    label = f"{v} · {as_text(f.get('package', '?'))}"
    if f.get("score") is not None:
        label += f"  (score {f['score']})"
    with st.expander(label, expanded=(v == "BLOCK")):
        p = norm_path(f.get("path", ""))
        if p:
            st.markdown("**How it got in:**")
            st.markdown(f'<div class="path">{p}</div>', unsafe_allow_html=True)

        sigs = f.get("signals") or []
        if sigs:
            st.markdown("**Why it was flagged:**")
            for s in sigs:
                if isinstance(s, dict):
                    st.markdown(
                        f'<span class="pill" style="background:{COLORS.get(v, "#555")}">+{s.get("weight", 0)}</span>'
                        f'**{as_text(s.get("id"))}** — {as_text(s.get("evidence"))}',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"- {as_text(s)}")

        ex = norm_explanation(f.get("explanation"))
        if ex:
            parts = []
            if ex.get("summary"):
                parts.append(f"**In plain words:** {ex['summary']}")
            if ex.get("why_it_matters"):
                parts.append(f"**Why it matters:** {ex['why_it_matters']}")
            wtd = ex.get("what_to_do") or f.get("what_to_do")
            if wtd:
                parts.append(f"**What to do:** {wtd}")
            if parts:
                st.info("\n\n".join(parts))
                src = f.get("explanation_source") or f.get("source")
                if src:
                    st.caption(f"Explanation source: {src}")

# ---------- onchain ----------
st.subheader("Onchain record (Solana devnet)")
chain = report.get("chain") or {}
sig = as_text(chain.get("signature"))
if not chain:
    st.info("Not logged onchain. Run the scan with --chain and a funded devnet keypair.")
elif sig and not chain.get("simulated") and not sig.startswith("SIMULATED"):
    url = chain.get("explorer_url") or f"https://explorer.solana.com/tx/{sig}?cluster=devnet"
    st.success("Real devnet transaction")
    st.markdown(f"[Open in Solana Explorer]({url})")
    st.code(sig, language=None)
else:
    st.warning("SIMULATED: no real transaction was sent.")
    if sig:
        st.code(sig, language=None)

if report.get("report_sha256"):
    st.caption("Report SHA-256")
    st.code(report["report_sha256"], language=None)

with st.expander("Raw report JSON"):
    st.json(report)
