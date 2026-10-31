# SPDX-License-Identifier: Apache-2.0
"""Step 3: rule-based detection. Each check looks at ONE package and returns a Signal or None.
All weights are in WEIGHTS - tune them in one place."""
from __future__ import annotations

import re
from typing import List, Optional

from .data import POPULAR
from .models import PackageInfo, Signal

WEIGHTS = {
    "install_time_execution": 25,
    "credential_access": 30,
    "network_in_install": 25,
    "obfuscation": 25,
    "typosquat": 35,
    "publish_anomaly": 15,
    "prompt_injection_attempt": 20,
}
INSTALL_HOOKS = ("preinstall", "install", "postinstall")

_PY_EXEC = re.compile(r"subprocess|os\.system|\bexec\s*\(|\beval\s*\(|__import__")
_CRED = [
    ("reads .npmrc", re.compile(r"\.npmrc")),
    ("reads AWS credentials", re.compile(r"\.aws/credentials")),
    ("reads SSH keys", re.compile(r"id_rsa|\.ssh/")),
    ("dumps ALL environment variables", re.compile(
        r"\bprocess\.env\b(?!\.|\[)|os\.environ\.(?:items|copy)\(|dict\(\s*os\.environ\s*\)")),
]
_NET = re.compile(
    r"https?://|\bfetch\s*\(|http\.request|https\.request|XMLHttpRequest|\bcurl\b|\bwget\b"
    r"|requests\.(?:get|post)|urllib|socket\.connect|net\.connect")
_OBF_EXEC = re.compile(r"\beval\s*\(|new\s+Function\s*\(|\bexec\s*\(")
_OBF_DECODE = re.compile(r"base64|atob\s*\(|fromCharCode|\\x[0-9a-fA-F]{2}|b64decode")
_BLOB = re.compile(r"[A-Za-z0-9+/=]{200,}")
_INJECTION = re.compile(
    r"ignore (?:all |any )?(?:previous|prior|above) instructions"
    r"|(?:mark|classify|report|label) (?:this|the) (?:package|code) as (?:safe|benign|clean)"
    r"|do not (?:flag|report) this", re.IGNORECASE)


def _short(text: str, n: int = 110) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 3] + "..."


def _all_texts(info: PackageInfo) -> List[str]:
    return list(info.scripts.values()) + list(info.files.values())


def install_texts(info: PackageInfo) -> List[str]:
    """Code that runs when the package is INSTALLED (hooks + files the hooks point at)."""
    hooks = [info.scripts[h] for h in INSTALL_HOOKS if h in info.scripts]
    texts = list(hooks)
    for path, content in info.files.items():
        if any(path in cmd for cmd in hooks):
            texts.append(content)
    if info.ref.ecosystem == "pypi" and "setup.py" in info.files:
        texts.append(info.files["setup.py"])
    return texts


def relevant_snippet(info: PackageInfo, max_lines: int = 40) -> str:
    """The code we show Gemma: install-time code first, otherwise the first file."""
    texts = install_texts(info) or list(info.files.values())[:1]
    return "\n".join("\n".join(texts).splitlines()[:max_lines])


def check_install_time_execution(info: PackageInfo) -> Optional[Signal]:
    w = WEIGHTS["install_time_execution"]
    if info.ref.ecosystem == "npm":
        for hook in INSTALL_HOOKS:
            if hook in info.scripts:
                return Signal("install_time_execution", w, f"{hook} script runs: {_short(info.scripts[hook])}")
    elif info.ref.ecosystem == "pypi":
        m = _PY_EXEC.search(info.files.get("setup.py", ""))
        if m:
            return Signal("install_time_execution", w, f"setup.py runs code at install time ({m.group(0)})")
    return None


def check_credential_access(info: PackageInfo) -> Optional[Signal]:
    text = "\n".join(_all_texts(info))
    for label, rx in _CRED:
        if rx.search(text):
            return Signal("credential_access", WEIGHTS["credential_access"], label)
    return None


def check_network_in_install(info: PackageInfo) -> Optional[Signal]:
    for text in install_texts(info):
        m = _NET.search(text)
        if m:
            return Signal("network_in_install", WEIGHTS["network_in_install"],
                          f"install-time code makes a network call ({m.group(0).rstrip('( ')})")
    return None


def check_obfuscation(info: PackageInfo) -> Optional[Signal]:
    text = "\n".join(_all_texts(info))
    if _OBF_EXEC.search(text) and _OBF_DECODE.search(text):
        return Signal("obfuscation", WEIGHTS["obfuscation"], "decodes hidden data and executes it (eval/exec + base64)")
    if _BLOB.search(text):
        return Signal("obfuscation", WEIGHTS["obfuscation"], "very long encoded string (possible hidden payload)")
    return None


def check_prompt_injection(info: PackageInfo) -> Optional[Signal]:
    m = _INJECTION.search("\n".join(_all_texts(info)))
    if m:
        return Signal("prompt_injection_attempt", WEIGHTS["prompt_injection_attempt"],
                      f"text aimed at AI reviewers: '{_short(m.group(0), 60)}'")
    return None


def edit_distance(a: str, b: str) -> int:
    """Edit distance where swapping two neighbouring letters counts as 1 (lodash vs lodahs)."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def check_typosquat(info: PackageInfo) -> Optional[Signal]:
    name = re.sub(r"[-_.]+", "-", info.ref.name.lower())
    popular = POPULAR.get(info.ref.ecosystem, frozenset())
    if name.startswith("@") or name in popular:
        return None
    limit = 1 if len(name) <= 4 else 2
    best = None
    for p in popular:
        if abs(len(p) - len(name)) > limit:
            continue
        d = edit_distance(name, p)
        if 0 < d <= limit and (best is None or d < best[1]):
            best = (p, d)
    if best:
        return Signal("typosquat", WEIGHTS["typosquat"], f"name is very close to popular package '{best[0]}'")
    return None


def check_publish_anomaly(info: PackageInfo) -> Optional[Signal]:
    reasons = []
    if info.package_age_days is not None and info.package_age_days < 14:
        reasons.append(f"package first published only {info.package_age_days} days ago")
    if info.maintainer_changed:
        reasons.append("maintainer changed before this release")
    if info.dormant_days_before_release and info.dormant_days_before_release >= 365:
        reasons.append(f"dormant for {info.dormant_days_before_release} days, then a new release")
    if reasons:
        return Signal("publish_anomaly", WEIGHTS["publish_anomaly"], "; ".join(reasons))
    return None


CHECKS = [
    check_install_time_execution, check_credential_access, check_network_in_install,
    check_obfuscation, check_typosquat, check_publish_anomaly, check_prompt_injection,
]


def analyze(info: PackageInfo) -> List[Signal]:
    """Run every check on one package."""
    return [s for s in (check(info) for check in CHECKS) if s]
