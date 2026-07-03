"""MODEL-001 — client wrapper: env-var-only resolution + residency enforcement (no network, no keys).

The headline is test_key_material_payload_cannot_reach_a_prc_provider — the residency guarantee that a
blocked-tag payload is structurally prevented from reaching a PRC first-party provider.
"""

from __future__ import annotations

import pytest

from agent import model_routing as mr
from agent import model_client as mc

ENV = {
    "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
    "OPENROUTER_API_KEY": "sk-test-not-real",
    "LOCAL_LLM_BASE_URL": "http://localhost:11434/v1",
}


@pytest.fixture
def env(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("K26_PROVIDER_PIN", raising=False)      # pin unset by default (pre-A/B)
    return ENV


# --------------------------------------------------------------- env-var resolution (keys only)

def test_resolve_endpoint_reads_env_only(env):
    ep = mc.resolve_endpoint("escalate")
    assert ep["model"] == "moonshotai/kimi-k2.6"
    assert ep["base_url"] == ENV["OPENROUTER_BASE_URL"]
    assert ep["api_key"] == "sk-test-not-real"                 # from ENV, never hardcoded


def test_missing_env_raises_configerror(monkeypatch):
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    with pytest.raises(mc.ConfigError):
        mc.resolve_endpoint("routine")


def test_local_fallback_needs_no_api_key(env):
    ep = mc.resolve_endpoint("fallback")
    assert ep["model"] == "local/llama" and ep["base_url"] == ENV["LOCAL_LLM_BASE_URL"]


# --------------------------------------------------------------- residency enforcement

def test_unblocked_payload_has_no_provider_constraint(env):
    req = mc.build_request("routine", [{"role": "user", "content": "hi"}], payload_tags=["routine"])
    assert "extra_body" not in req
    assert req["base_url"] == ENV["OPENROUTER_BASE_URL"] and req["api_key"] == "sk-test-not-real"


def test_key_material_payload_cannot_reach_a_prc_provider(env):
    req = mc.build_request("escalate", [{"role": "user", "content": "x"}], payload_tags=["key_material"])
    only = req["extra_body"]["provider"]["only"]
    assert only == mr.us_hosted_allowlist() and only                      # pinned to US-hosted
    prc = {"moonshot", "deepseek", "api.moonshot.ai", "api.deepseek.com"}  # first-party PRC
    assert not (set(p.lower() for p in only) & prc)                        # none can serve it
    assert set(only) <= set(mr.us_hosted_allowlist())


def test_blocked_payload_with_no_allowlist_diverts(env):
    cfg = {**mr.DEFAULT_CONFIG,
           "residency": {**mr.DEFAULT_CONFIG["residency"], "us_hosted_provider_allowlist": []}}
    with pytest.raises(mr.ResidencyException):
        mc.build_request("escalate", [{"role": "user", "content": "x"}],
                         payload_tags=["key_material"], config=cfg)


def test_provider_pin_may_not_widen_residency(env, monkeypatch):
    monkeypatch.setenv("K26_PROVIDER_PIN", "Moonshot")         # PRC first-party, not US-hosted
    with pytest.raises(mr.ResidencyException):
        mc.build_request("escalate", [{"role": "user", "content": "x"}], payload_tags=["key_material"])


def test_provider_pin_honored_when_us_hosted(env, monkeypatch):
    monkeypatch.setenv("K26_PROVIDER_PIN", "Together")         # US-hosted, in allowlist
    req = mc.build_request("escalate", [{"role": "user", "content": "x"}], payload_tags=["key_material"])
    assert req["extra_body"]["provider"]["only"] == ["Together"]


def test_provider_constraint_direct(env):
    assert mr.provider_constraint(["routine"]) is None
    assert mr.provider_constraint([]) is None
    assert mr.provider_constraint(["canon_sensitive"]) == {"only": mr.us_hosted_allowlist()}


# --------------------------------------------------------------- live call plumbing (injected client)

def test_call_uses_injected_client_factory_and_strips_secrets(env):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["kwargs"] = kwargs
            return {"ok": True}

    class FakeClient:
        def __init__(self, base_url, api_key):
            captured["base_url"], captured["api_key"] = base_url, api_key
            self.chat = type("C", (), {"completions": FakeCompletions()})()

    out = mc.call("routine", [{"role": "user", "content": "hi"}], payload_tags=["routine"],
                  client_factory=lambda b, k: FakeClient(b, k))
    assert out == {"ok": True}
    assert captured["base_url"] == ENV["OPENROUTER_BASE_URL"]
    assert captured["api_key"] == "sk-test-not-real"
    assert captured["kwargs"]["model"] == "deepseek/deepseek-v4-flash"
    assert "base_url" not in captured["kwargs"] and "api_key" not in captured["kwargs"]
