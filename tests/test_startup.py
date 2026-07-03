"""Item 2 (safety slice) — startup preflight fails LOUD on missing router env, so a degraded/local model
can never be served silently. This is the guard that makes the 'nerfed Ceph' failure undetectable-no-more."""

from __future__ import annotations

import pytest

from agent import model_client as mc
from agent import startup

ENV = {
    "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
    "OPENROUTER_API_KEY": "sk-preflight",
    "LOCAL_LLM_BASE_URL": "http://localhost:11434/v1",
}


def _set_all(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)


def test_preflight_passes_and_reports_hosted_models(monkeypatch):
    _set_all(monkeypatch)
    summary = startup.preflight_router()
    assert summary["routine"] == "deepseek/deepseek-v4-flash"
    assert summary["escalate"] == "moonshotai/kimi-k2.6"


def test_preflight_fails_loud_on_missing_hosted_api_key(monkeypatch):
    _set_all(monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)     # the exact silent-nerf trigger
    with pytest.raises(mc.ConfigError):
        startup.preflight_router()


def test_preflight_fails_loud_on_missing_base_url(monkeypatch):
    _set_all(monkeypatch)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    with pytest.raises(mc.ConfigError):
        startup.preflight_router()


def test_preflight_fails_when_local_fallback_unconfigured(monkeypatch):
    _set_all(monkeypatch)
    monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
    with pytest.raises(mc.ConfigError):
        startup.preflight_router()
