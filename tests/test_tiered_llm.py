"""Item 2 — TieredRouterLlm routing + outage fallback. Logic tested with fake submodels (no network,
no keys, no litellm calls). The live ADK/LiteLlm binding is validated at item-6 acceptance (needs keys)."""

from __future__ import annotations

import asyncio

import pytest

from agent import model_routing as mr
from agent.tiered_llm import TieredRouterLlm


class _FakeSub:
    """A fake submodel: yields one tagged response, or raises before yielding to simulate an outage."""

    def __init__(self, tag, raise_before_yield=False):
        self.tag = tag
        self.raise_before_yield = raise_before_yield
        self.calls = 0

    async def generate_content_async(self, llm_request, stream=False):
        self.calls += 1
        if self.raise_before_yield:
            raise ConnectionError(f"{self.tag} outage")
        yield f"resp-from-{self.tag}"


def _router(routine, escalate, fallback, on_fallback=None):
    r = TieredRouterLlm()
    r._tiers = {mr.ROUTINE: routine, mr.ESCALATE: escalate, mr.FALLBACK: fallback}
    r._on_fallback = on_fallback
    return r


def _collect(router):
    async def _run():
        return [x async for x in router.generate_content_async("req")]
    return asyncio.run(_run())


# --------------------------------------------------------------- tier selection

def test_bind_tier_default_routine():
    r = _router(_FakeSub("routine"), _FakeSub("escalate"), _FakeSub("local"))
    assert r.bind_tier_for({"task_type": "chat"}) == mr.ROUTINE


def test_bind_tier_escalates_on_governance():
    r = _router(_FakeSub("routine"), _FakeSub("escalate"), _FakeSub("local"))
    assert r.bind_tier_for({"domain": "governance_review",
                            "task_type": "prp_validation_report"}) == mr.ESCALATE


def test_bind_tier_escalates_on_high_stakes():
    r = _router(_FakeSub("routine"), _FakeSub("escalate"), _FakeSub("local"))
    assert r.bind_tier_for({"high_stakes": True}) == mr.ESCALATE


# --------------------------------------------------------------- delegation

def test_routes_to_the_bound_tier():
    routine, escalate, local = _FakeSub("routine"), _FakeSub("escalate"), _FakeSub("local")
    r = _router(routine, escalate, local)
    r.bind_tier_for({"high_stakes": True})            # -> escalate
    assert _collect(r) == ["resp-from-escalate"]
    assert escalate.calls == 1 and routine.calls == 0 and local.calls == 0


# --------------------------------------------------------------- outage fallback

def test_outage_before_output_falls_back_to_local_and_alerts():
    alerts = []
    routine = _FakeSub("routine", raise_before_yield=True)     # hosted outage
    local = _FakeSub("local")
    r = _router(routine, _FakeSub("escalate"), local,
                on_fallback=lambda t, e: alerts.append((t, str(e))))
    r.bind_tier_for({"task_type": "chat"})            # routine
    assert _collect(r) == ["resp-from-local"]         # stayed live on TIER 2
    assert local.calls == 1
    assert alerts and alerts[0][0] == mr.ROUTINE      # Navigator alerted (never silent)


def test_local_fallback_outage_raises_no_infinite_loop():
    local = _FakeSub("local", raise_before_yield=True)
    r = _router(_FakeSub("routine"), _FakeSub("escalate"), local)
    r._current_tier = mr.FALLBACK
    with pytest.raises(ConnectionError):
        _collect(r)
