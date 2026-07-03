import os

from google.adk.agents import Agent

from agent.constitutional.guard import constitutional_guard
from agent.identity import build_system_prompt
from agent.tools.send_external import send_external
from agent.tools.web_fetch import web_fetch


def _build_model():
    """MODEL-001 tiered router when CEPH_ROUTER=1 — routine deepseek-v4-flash / escalate kimi-k2.6 /
    local-llama outage fallback, via OpenRouter, with a LOUD ConfigError if keys are missing (never a
    silent local serve). Otherwise the legacy single model (GEMINI_MODEL), so existing runs are undisturbed.
    The executor calls `root_agent.model.bind_tier_for(task)` per turn to escalate (default: routine)."""
    import os as _os
    if _os.environ.get("CEPH_ROUTER") == "1":
        from agent.tiered_llm import build_router_llm
        return build_router_llm(
            on_fallback=lambda tier, exc: print(f"[ROUTER-FALLBACK] {tier} outage -> local: {exc}"))
    return _os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


# Instruction is the STABLE identity prefix (SOUL + roster + constitutional preamble). Assembled once at
# import; byte-stable so the provider prompt-cache holds. Ceph knows he is Ceph regardless of model/tier.
root_agent = Agent(
    name="ceph_v3_sentinel",
    model=_build_model(),
    instruction=build_system_prompt(),
    tools=[web_fetch, send_external],
    before_tool_callback=constitutional_guard,
)
