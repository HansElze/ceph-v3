"""Item 2 — TieredRouterLlm: Ceph's ADK model that routes per MODEL-001 and falls back on outage.

Composes three ADK `LiteLlm` submodels behind one `BaseLlm` the agent uses:
  routine  = deepseek-v4-flash (TIER 0, chat/routine)
  escalate = kimi-k2.6         (TIER 1, §3 triggers: high-stakes / governance_review / financial_modeling)
  fallback = local llama       (TIER 2, engaged ONLY on hosted-API outage)

Per turn the executor calls `bind_tier_for(task)` (default routine). On a hosted-tier outage *before any
output*, generation transparently switches to the local fallback and fires an alert — never silent. ADK
still owns the session + `before_tool_callback`, so the constitutional layer fires unchanged on every tier.

Item 3 is handled here too: the local tier is addressed as `openai/<model>` against its base_url, so litellm
uses the `/chat/completions` (chat-template) endpoint — the fallback answers a prompt instead of echoing it.
"""

from __future__ import annotations

from typing import AsyncGenerator, Callable, Optional

from google.adk.models.base_llm import BaseLlm
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from pydantic import PrivateAttr

from agent import model_client as mc
from agent import model_routing as mr


def _lite_for(tier: str, ep: dict) -> LiteLlm:
    """Build the LiteLlm for a tier from a resolved endpoint (env-var driven)."""
    if tier == mr.FALLBACK:
        # local OpenAI-compatible server -> chat/completions (chat template), NOT /completions (item 3)
        model = f"openai/{ep['model'].split('/', 1)[-1]}"
    else:
        model = f"openrouter/{ep['model']}"          # litellm OpenRouter addressing
    kwargs = {"api_base": ep["base_url"]}
    if ep.get("api_key") and ep["api_key"] != "not-needed":
        kwargs["api_key"] = ep["api_key"]
    return LiteLlm(model=model, **kwargs)


class TieredRouterLlm(BaseLlm):
    """One BaseLlm that routes to per-tier submodels with outage fallback. Submodels live in a private
    map so ADK/pydantic treats this as a normal model; `build_router_llm` populates it."""

    model: str = "ceph-tiered-router"

    _tiers: dict = PrivateAttr(default_factory=dict)     # tier -> BaseLlm submodel
    _current_tier: str = PrivateAttr(default=mr.ROUTINE)
    _on_fallback: Optional[Callable] = PrivateAttr(default=None)

    def bind_tier_for(self, task: Optional[dict]) -> str:
        """Select the tier for the upcoming turn (MODEL-001 §3). Default routine; escalate on triggers."""
        self._current_tier = mr.select_tier(task or {})
        return self._current_tier

    @property
    def current_tier(self) -> str:
        return self._current_tier

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        tier = self._current_tier
        yielded = False
        try:
            async for resp in self._tiers[tier].generate_content_async(llm_request, stream=stream):
                yielded = True
                yield resp
            return
        except Exception as exc:                          # hosted-API outage
            if tier == mr.FALLBACK or yielded:
                raise                                     # already local, or mid-stream -> cannot safely switch
            if self._on_fallback:
                self._on_fallback(tier, exc)              # loud alert (Navigator visibility)
        # outage before any output -> stay live on the local fallback tier
        async for resp in self._tiers[mr.FALLBACK].generate_content_async(llm_request, stream=stream):
            yield resp


def build_router_llm(config: Optional[dict] = None, on_fallback: Optional[Callable] = None) -> TieredRouterLlm:
    """Construct the tiered router from config. Resolves every tier's endpoint from ENV via `*_env` keys —
    raises `mc.ConfigError` LOUDLY on any missing var (never boots into silent local serving)."""
    config = config or mr.DEFAULT_CONFIG
    router = TieredRouterLlm()
    for tier in (mr.ROUTINE, mr.ESCALATE, mr.FALLBACK):
        router._tiers[tier] = _lite_for(tier, mc.resolve_endpoint(tier, config))
    router._on_fallback = on_fallback
    return router
