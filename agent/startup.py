"""Startup preflight — make silent model fallback IMPOSSIBLE (item 2 safety).

The 'nerfed Ceph' failure persisted undetected because a missing OpenRouter key silently fell through to
the local Llama. This preflight resolves the hosted tiers' env at startup and raises a LOUD ConfigError if
anything is missing — the process refuses to boot rather than serve a degraded model unannounced.

Call `preflight_router()` from the runtime entry point BEFORE accepting any traffic. Fail-closed by design.
"""

from __future__ import annotations

from typing import Optional

from agent import model_client as mc
from agent import model_routing as mr

# The tiers that MUST have real hosted keys at boot. The fallback tier is local and API-keyless by design.
HOSTED_TIERS = (mr.ROUTINE, mr.ESCALATE)


def preflight_router(config: Optional[dict] = None) -> dict:
    """Resolve every hosted tier's endpoint from ENV. Raises `mc.ConfigError` LOUDLY on the first missing
    variable (never boot into silent local-Llama serving). Also confirms the fallback tier's base_url is
    configured (it needs no API key). Returns a {tier: model} summary on success."""
    config = config or mr.DEFAULT_CONFIG
    summary = {}
    for tier in HOSTED_TIERS:
        ep = mc.resolve_endpoint(tier, config)        # raises ConfigError if base_url/api_key env is unset
        summary[tier] = ep["model"]
    mc.resolve_endpoint(mr.FALLBACK, config)          # fallback must be reachable-by-config too (no key)
    return summary
