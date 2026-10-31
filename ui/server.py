# SPDX-License-Identifier: Apache-2.0
"""Dependency-free local UI for Dependency Guard (standard library only).

Run from the repo root:  python ui/server.py   then open http://localhost:8000
It runs the real CLI and shows the report. It listens on 127.0.0.1 only.
"""
import html
import json
import os
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("PORT", "8000"))
MOCKS = ["fixtures/starter_registry.json", "fixtures/extra_registry.json", "live"]
COLORS = {"OK": "#16A34A", "REVIEW": "#D97706", "BLOCK": "#DC2626"}
EXIT = {0: "OK", 1: "REVIEW", 2: "BLOCK"}
e = html.escape

CSS = """body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#F3F5F8;color:#1F2937}
header{background:#0B1F3A;color:#fff;padding:18px 32px}header h1{margin:0;font-size:24px}
header p{margin:4px 0 0;color:#14B8A6}main{max-width:960px;margin:24px auto;padding:0 16px}
.card{background:#fff;border-radius:8px;padding:16px 20px;margin-bottom:14px;box-shadow:0 1px 3px #0002}
form{display:flex;gap:12px;flex-wrap:wrap;align-items:end}label{font-size:13px;color:#6B7280;display:block}
input[type=text],select{padding:7px;min-width:220px}button{background:#0B1F3A;color:#fff;border:0;
padding:9px 22px;border-radius:6px;cursor:pointer;font-size:15px}
.b{color:#fff;padding:2px 10px;border-radius:10px;font-weight:600;font-size:13px}
.big{font-size:22px;font-weight:700}.mut{color:#6B7280;font-size:13px}pre{background:#0B1F3A;color:#E5E7EB;
padding:12px;border-radius:6px;overflow:auto;font-size:12px}code{background:#EEF2F7;padding:1px 5px;border-radius:4px}"""


def badge(text, verdict, color=None):
    c = color or COLORS.get(verdict, "#6B7280")
    return f'<span class="b" style="background:{c}">{e(str(text))}</span>'


def form(q):
    def val(k, d):
        return e(q.get(k, [d])[0])
    opts = "".join(f'<option value="{m}"{" selected" if q.get("mock", [MOCKS[0]])[0] == m else ""}>'
                   f'{"Live npm / PyPI (limited)" if m == "live" else m}</option>' for m in MOCKS)
    return f"""<div class="card"><form method="get" action="/">
<div><label>Project folder or manifest</label><input type="text" name="path" value="{val('path', 'fixtures/trap-app')}"></div>
<div><label>Registry</label><select name="mock">{opts}</select></div>
<div><label><input type="checkbox" name="llm" value="1"{" checked" if "llm" in q else ""}> Gemma explanations (slow on first run)</label>
<label><input type="checkbox" name="chain" value="1"{" checked" if "chain" in q else ""}> Log report hash (--chain)</label></div>
<button type="submit">Scan</button></form>
<p class="mut">Reputation and chain output is SIMULATED unless the real modules are merged.</p></div>"""


def run_scan(q):
    path = q["path"][0]
    mock = q.get("mock", [MOCKS[0]])[0]
    if mock not in MOCKS:
        return "<div class='card'>Unknown registry option.</div>"
    out = Path(tempfile.gettempdir()) / "depguard_ui_report.json"
    try:
        out.unlink()
    except OSError:
        pass
    cmd = [sys.executable, "-m", "guard", "scan", path, "--out", str(out)]
    if mock != "live":
        cmd += ["--mock", mock]
    if "llm" not in q:
        cmd.append("--no-llm")
    if "chain" in q:
        cmd.append("--chain")
    try:
        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return "<div class='card'>Scan timed out after 15 minutes.</div>"
    if res.returncode not in EXIT or not out.exists():
        return f"<div class='card'><b>The scan failed.</b><pre>{e((res.stderr or res.stdout or 'no output').strip())}</pre></div>"
    try:
        rep = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"<div class='card'>Could not read the report: {e(str(exc))}</div>"
    s = rep.get("summary", {})
    v = s.get("verdict") or EXIT[res.returncode]
    h = [f"""<div class="card"><span class="big">Verdict {badge(v, v)}</span>
&nbsp; score {e(str(s.get('score', '-')))} &middot; {e(str(s.get('packages_scanned', '-')))} packages
&middot; max depth {e(str(s.get('max_depth', '-')))}</div>"""]
    if s.get("tree_truncated"):
        h.append("<div class='card'>The tree was truncated at the depth or node limit.</div>")
    for f in rep.get("findings", []):
        fv = f.get("verdict", "?")
        sig = "".join(f"<li><code>{e(str(x.get('id')))}</code> (+{e(str(x.get('weight')))}): {e(str(x.get('evidence')))}</li>"
                      for x in f.get("signals", []))
        ex = f.get("explanation")
        exh = ""
        if isinstance(ex, dict):
            exh = (f"<p><b>Explanation [{e(str(ex.get('source', '?')))}]:</b> {e(str(ex.get('summary', '')))}</p>"
                   f"<p><b>What to do:</b> {e(str(ex.get('what_to_do', '')))}</p>")
        h.append(f"""<div class="card">{badge(f"{fv} ({f.get('score', '?')})", fv)} &nbsp;<b>{e(str(f.get('package', '?')))}</b>
<div class="mut">Path: {e(' -> '.join(f.get('path', [])))}</div><ul>{sig}</ul>{exh}</div>""")
    if not rep.get("findings"):
        h.append("<div class='card'>No findings.</div>")
    ch = rep.get("chain") or {}
    if ch:
        sim = ch.get("simulated")
        link = f' <a href="{e(ch["explorer_url"])}" target="_blank">explorer</a>' if ch.get("explorer_url") else ""
        h.append(f"<div class='card'><b>On-chain log</b> {badge('SIMULATED' if sim else 'REAL', '', '#DC2626' if sim else '#16A34A')}"
                 f"<br><code>{e(str(ch.get('signature', '')))}</code>{link}</div>")
    h.append(f"<p class='mut'>Report SHA-256: {e(str(rep.get('report_sha256', '')))}</p>")
    h.append(f"<div class='card'><b>Full scan output (dependency tree)</b><pre>{e(res.stdout)}</pre></div>")
    return "".join(h)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path != "/":
            self.send_error(404)
            return
        q = parse_qs(u.query)
        body = form(q) + (run_scan(q) if "path" in q else
                          "<div class='card'>Choose settings and press Scan. Leave Gemma off for a fast demo.</div>")
        page = (f"<!doctype html><meta charset='utf-8'><title>Dependency Guard</title><style>{CSS}</style>"
                "<header><h1>Dependency Guard</h1><p>Rules decide, the LLM only explains.</p></header>"
                f"<main>{body}</main>")
        data = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"Dependency Guard UI: http://localhost:{PORT}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
