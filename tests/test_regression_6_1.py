"""MODEL-001 regression drill 6.1 — model routing is ORTHOGONAL to constitutional enforcement.

The guarantee: `HardLimits.check_tool_call` takes only a ToolCall — no tier, no model — so its verdict
cannot vary by routing tier. These tests pin that invariant, prove all three tiers build a servable
request while the guard verdict stays identical, and drill the TIER 2 fallback on a hosted outage
(agent stays live; guard still applies; residency diversions are never silently downgraded).
"""

from __future__ import annotations

import dataclasses

import pytest

from agent import model_routing as mr
from agent import model_client as mc
from agent.constitutional.hard_limits import HardLimits, ToolCall

TIERS = [mr.ROUTINE, mr.ESCALATE, mr.FALLBACK]
ENV = {
    "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
    "OPENROUTER_API_KEY": "sk-x",
    "LOCAL_LLM_BASE_URL": "http://localhost:11434/v1",
}


@pytest.fixture
def env(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("K26_PROVIDER_PIN", raising=False)


def _verdict(name, inputs):
    return HardLimits().check_tool_call(ToolCall(name=name, inputs=inputs, agent_run_id="r1"))


def test_guard_blocks_identically_across_all_tiers(env):
    verdicts = []
    for tier in TIERS:
        mc.build_request(tier, [{"role": "user", "content": "x"}], payload_tags=None)   # all 3 serve
        v = _verdict("send_external", {"url": "https://evil.example"})
        verdicts.append((v.allowed, v.rule_violated))
    assert verdicts == [(False, "unauthorized_external_send")] * 3


def test_guard_allows_identically_across_all_tiers(env):
    verdicts = []
    for tier in TIERS:
        mc.build_request(tier, [{"role": "user", "content": "x"}], payload_tags=None)
        verdicts.append(_verdict("web_fetch", {"url": "https://openrouter.ai"}).allowed)
    assert verdicts == [True, True, True]


def test_toolcall_carries_no_tier_or_model_field():
    fields = {f.name for f in dataclasses.fields(ToolCall)}
    assert "tier" not in fields and "model" not in fields          # guard is structurally tier-blind


def test_fallback_drill_stays_live_and_preserves_guard(env):
    served = []

    def factory(base_url, api_key):
        served.append(base_url)

        class Completions:
            def create(self, **kw):
                if base_url == ENV["OPENROUTER_BASE_URL"]:
                    raise ConnectionError("hosted outage")
                return {"served_by": base_url}

        return type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()

    alerts = []
    out = mc.call_with_fallback(
        mr.ESCALATE, [{"role": "user", "content": "x"}], payload_tags=None,
        client_factory=factory, on_fallback=lambda t, e: alerts.append((t, str(e))))

    assert out == {"served_by": ENV["LOCAL_LLM_BASE_URL"]}          # stayed live on TIER 2
    assert served == [ENV["OPENROUTER_BASE_URL"], ENV["LOCAL_LLM_BASE_URL"]]
    assert alerts and alerts[0][0] == mr.ESCALATE                  # Navigator alerted
    assert _verdict("send_external", {}).allowed is False          # guard verdict unchanged


def test_fallback_never_swallows_a_residency_diversion(env):
    cfg = {**mr.DEFAULT_CONFIG,
           "residency": {**mr.DEFAULT_CONFIG["residency"], "us_hosted_provider_allowlist": []}}
    with pytest.raises(mr.ResidencyException):
        mc.call_with_fallback(mr.ESCALATE, [{"role": "user", "content": "x"}],
                              payload_tags=["key_material"], config=cfg, client_factory=lambda b, k: None)
