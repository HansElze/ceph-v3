"""MODEL-001 — model client wrapper (env-var driven; binds a tier decision to a live call).

Resolves each tier's endpoint / api key / provider pin from ENVIRONMENT VARIABLES ONLY (never
hardcoded) via the config's `*_env` keys, and enforces the residency gate: a blocked-tag payload is
pinned to the US-hosted OpenRouter provider allowlist (`provider.only`) or diverted to the exception
path (ResidencyException).

Scope guard (MODEL-001 §4.3): the constitutional `before_tool_callback`, token-burn guard, fabrication
detector, and the Arize/Phoenix tracer live OUTSIDE this wrapper and wrap the call unchanged. This
module only selects model / endpoint / params + the residency constraint; it never judges tool calls.

`build_request()` and `resolve_endpoint()` are pure and testable with no keys and no network.
`call()` performs the live call; it takes an injectable `client_factory` (tests pass a fake; at
cutover it defaults to the OpenAI SDK against the resolved base_url). Live cutover is Navigator-run.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from agent import model_routing as mr


class ConfigError(Exception):
    """A required environment variable named by the config is unset (env-var keys only; no hardcoding)."""


def _require_env(var: str) -> str:
    val = os.environ.get(var)
    if not val:
        raise ConfigError(f"environment variable {var} is not set")
    return val


def resolve_endpoint(tier: str, config: Optional[dict] = None) -> dict:
    """Resolve a tier's model + base_url + api_key (+ optional provider_pin) from ENV via its
    `*_env` keys. The local fallback tier needs no API key."""
    config = config or mr.DEFAULT_CONFIG
    t = config["tiers"][tier]
    ep = {"tier": tier, "model": t["model"], "timeout_s": t.get("timeout_s"),
          "base_url": _require_env(t["base_url_env"])}
    ep["api_key"] = _require_env(t["api_key_env"]) if "api_key_env" in t \
        else os.environ.get("LOCAL_LLM_API_KEY", "not-needed")
    if "max_tokens" in t:
        ep["max_tokens"] = t["max_tokens"]
    if "provider_pin_env" in t:
        pin = os.environ.get(t["provider_pin_env"])          # optional until A/B ratifies it
        if pin:
            ep["provider_pin"] = pin
    return ep


def build_request(tier: str, messages: list, payload_tags=None, config: Optional[dict] = None) -> dict:
    """Assemble OpenAI-compatible call kwargs for `tier`, enforcing residency.

    - `base_url` / `api_key` come from ENV (resolve_endpoint).
    - For a blocked-tag payload, OpenRouter `provider.only` is pinned to the US-hosted allowlist so
      the PRC first-party providers are structurally excluded; a blocked payload with no allowlist
      raises ResidencyException (caller diverts to the premium exception path).
    - An explicit `provider_pin` (post-A/B) is honored; for a blocked payload it is INTERSECTED with
      the US-hosted allowlist so a pin can never widen residency.
    Raises mr.ResidencyException (divert) or ConfigError (missing env)."""
    config = config or mr.DEFAULT_CONFIG
    ep = resolve_endpoint(tier, config)
    req = {"model": ep["model"], "messages": messages,
           "base_url": ep["base_url"], "api_key": ep["api_key"], "timeout": ep.get("timeout_s")}
    if "max_tokens" in ep:
        req["max_tokens"] = ep["max_tokens"]

    # Residency (OpenRouter provider routing) applies to the hosted OpenRouter tiers only. The local
    # fallback endpoint is operator-hosted (US) and residency-safe by definition, so blocked payloads
    # are permitted there without a provider.only constraint.
    constraint = None if tier == mr.FALLBACK else mr.provider_constraint(payload_tags, config)
    provider = dict(constraint) if constraint else {}
    if ep.get("provider_pin"):
        if constraint:                                           # blocked: pin must be US-hosted
            allowed = [p for p in [ep["provider_pin"]] if p in set(constraint["only"])]
            if not allowed:
                raise mr.ResidencyException(
                    f"provider_pin {ep['provider_pin']!r} not in US-hosted allowlist for a blocked payload")
            provider["only"] = allowed
        else:
            provider["order"] = [ep["provider_pin"]]
    if provider:
        req["extra_body"] = {"provider": provider}               # OpenRouter provider routing
    return req


def call(tier: str, messages: list, payload_tags=None, config: Optional[dict] = None,
         client_factory: Optional[Callable] = None):
    """Perform the live call for `tier`. `client_factory(base_url, api_key)` returns an
    OpenAI-compatible client exposing `.chat.completions.create(**kwargs)`. Residency is enforced in
    build_request; the constitutional callbacks + tracer wrap this from OUTSIDE."""
    req = build_request(tier, messages, payload_tags, config)
    base_url, api_key = req.pop("base_url"), req.pop("api_key")
    if client_factory is None:                                   # cutover default (lazy: SDK optional)
        from openai import OpenAI
        client_factory = lambda b, k: OpenAI(base_url=b, api_key=k)
    return client_factory(base_url, api_key).chat.completions.create(**req)


def call_with_fallback(tier: str, messages: list, payload_tags=None, config: Optional[dict] = None,
                       client_factory: Optional[Callable] = None, on_fallback: Optional[Callable] = None):
    """Regression drill 6.1 fallback: try the chosen hosted tier; on a hosted-API OUTAGE (any call
    exception) engage TIER 2 (local fallback) so the agent stays live, invoking `on_fallback(tier, exc)`
    for Navigator visibility. A ResidencyException is NEVER swallowed — a blocked payload must be
    diverted to the premium exception path explicitly, not silently downgraded to the local model."""
    try:
        return call(tier, messages, payload_tags, config, client_factory)
    except mr.ResidencyException:
        raise
    except Exception as exc:                                     # hosted outage → stay live on local
        if on_fallback:
            on_fallback(tier, exc)
        return call(mr.FALLBACK, messages, payload_tags, config, client_factory)
