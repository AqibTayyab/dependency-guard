# SPDX-License-Identifier: Apache-2.0
"""These test OUR fallback and cache logic. They do not call a real Gemma; Ollama is replaced by a stub."""
from guard import explain as ex

FINDING = {"package": "npm:x@1.0.0", "path": ["app", "x@1.0.0"], "verdict": "BLOCK", "score": 80,
           "signals": [{"id": "credential_access", "weight": 30, "evidence": "reads SSH keys"}]}
FAKE = {"summary": "s", "why_it_matters": "w", "what_to_do": "t"}


def test_no_llm_flag_gives_template(monkeypatch):
    monkeypatch.setenv("GEMMA_MODEL", "some-model")
    assert ex.explain(FINDING, "", use_llm=False)["source"] == "template"


def test_offline_env_gives_template(monkeypatch):
    monkeypatch.setenv("GEMMA_MODEL", "some-model")
    monkeypatch.setenv("DEPGUARD_OFFLINE", "1")
    assert ex.explain(FINDING, "", use_llm=True)["source"] == "template"


def test_unreachable_ollama_falls_back_to_template(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMMA_MODEL", "some-model")
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:9")  # nothing listens here
    monkeypatch.setattr(ex, "CACHE_PATH", str(tmp_path / "c" / "e.json"))
    assert ex.explain(FINDING, "", use_llm=True)["source"] == "template"


def test_second_call_is_served_from_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMMA_MODEL", "some-model")
    monkeypatch.setattr(ex, "CACHE_PATH", str(tmp_path / "c" / "e.json"))
    monkeypatch.setattr(ex, "_ask_ollama", lambda model, finding, snippet: dict(FAKE))
    assert ex.explain(FINDING, "", use_llm=True)["source"] == "gemma"
    assert ex.explain(FINDING, "", use_llm=True)["source"] == "cache"
