"""MODEL-001 — Ceph v3 three-tier model routing (decision logic).

Pure, dependency-light logic for tier selection, the residency gate, and tool-call schema
validation/retry. It makes NO network calls and holds NO keys — the live client wrapper (LiteLLM /
OpenAI SDK, env-var driven) binds these decisions to actual model calls at cutover.

Scope guard (MODEL-001 §4.3): this module adds routing only. It does NOT touch the constitutional
`before_tool_callback` (agent/constitutional/guard.py), the token-burn guard, the fabrication
detector, or the Arize/Phoenix tracer — those wrap the model call unchanged.

Config is `ceph_model_routing.yaml` (loaded if PyYAML is present); an equivalent DEFAULT_CONFIG is
embedded so this module and its tests run with no dependencies.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Embedded mirror of ceph_model_routing.yaml (keep in sync).
DEFAULT_CONFIG = {
    "tiers": {
        "routine": {"model": "deepseek/deepseek-v4-flash", "base_url_env": "OPENROUTER_BASE_URL",
                    "api_key_env": "OPENROUTER_API_KEY", "max_tokens": 4096, "timeout_s": 60},
        "escalate": {"model": "moonshotai/kimi-k2.6", "base_url_env": "OPENROUTER_BASE_URL",
                     "api_key_env": "OPENROUTER_API_KEY", "provider_pin_env": "K26_PROVIDER_PIN",
                     "max_tokens": 8192, "timeout_s": 180},
        "fallback": {"model": "local/llama", "base_url_env": "LOCAL_LLM_BASE_URL", "timeout_s": 120},
    },
    "routing": {
        "escalate_domains": ["governance_review", "financial_modeling"],
        "escalate_task_types": ["prp_validation_report", "council_panel", "dispute", "appeal"],
        "max_tier0_retries": 2,
        "confidence_threshold": 0.6,
    },
    "residency": {
        "blocked_payload_tags": ["canon_sensitive", "investor_sensitive", "key_material"],
        "blocked_first_party_endpoints": ["api.moonshot.ai", "api.deepseek.com"],
        "us_hosted_provider_allowlist": ["Together", "Fireworks", "DeepInfra"],
    },
}

ROUTINE, ESCALATE, FALLBACK = "routine", "escalate", "fallback"


def load_config(path: Optional[str] = None) -> dict:
    """Load ceph_model_routing.yaml if PyYAML is available, else DEFAULT_CONFIG."""
    p = Path(path) if path else Path(__file__).resolve().parent.parent / "ceph_model_routing.yaml"
    if p.exists():
        try:
            import yaml  # optional
            return yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return DEFAULT_CONFIG


# --------------------------------------------------------------- §3 escalation trigger

def tier0_failed(schema_fail_count: int = 0, confidence: Optional[float] = None,
                 acceptance_passed: bool = True, config: Optional[dict] = None) -> bool:
    """§3.3 — a TIER 0 attempt is 'failed' if schema validation failed twice, OR self-reported
    confidence is below threshold, OR the caller's acceptance check failed."""
    config = config or DEFAULT_CONFIG
    r = config["routing"]
    if schema_fail_count >= r["max_tier0_retries"]:
        return True
    if confidence is not None and confidence < r["confidence_threshold"]:
        return True
    if not acceptance_passed:
        return True
    return False


def select_tier(task: dict, config: Optional[dict] = None) -> str:
    """§3 — choose TIER 0 (routine) or TIER 1 (escalate). Returns ROUTINE or ESCALATE.
    TIER 2 (fallback) is engaged by the client wrapper on hosted-API outage, not selected by task."""
    config = config or DEFAULT_CONFIG
    r = config["routing"]
    if task.get("navigator_override"):                                   # §3.4
        return ESCALATE
    if task.get("high_stakes"):                                          # §3.1
        return ESCALATE
    if task.get("domain") in r["escalate_domains"] and \
            task.get("task_type") in r["escalate_task_types"]:           # §3.2
        return ESCALATE
    if task.get("tier0_failed") or tier0_failed(                         # §3.3
            schema_fail_count=task.get("schema_fail_count", 0),
            confidence=task.get("confidence"),
            acceptance_passed=task.get("acceptance_passed", True),
            config=config):
        return ESCALATE
    return ROUTINE


# --------------------------------------------------------------- §4.1 residency gate

def residency_blocked(payload_tags, config: Optional[dict] = None) -> bool:
    """§4.1 / A4 — True if the payload carries a tag that must not reach first-party PRC endpoints.
    A blocked payload routes via a US-hosted open-weight provider or the premium exception path."""
    config = config or DEFAULT_CONFIG
    blocked = set(config["residency"]["blocked_payload_tags"])
    return bool(set(payload_tags or []) & blocked)


def endpoint_allowed(endpoint: str, payload_tags, config: Optional[dict] = None) -> bool:
    """A blocked-tag payload may not go to a blocked first-party endpoint."""
    config = config or DEFAULT_CONFIG
    if residency_blocked(payload_tags, config):
        return endpoint not in set(config["residency"]["blocked_first_party_endpoints"])
    return True


class ResidencyException(Exception):
    """A blocked-tag payload cannot be routed within residency policy — caller must divert to the
    premium exception path (a US-hosted dedicated endpoint) rather than send it at all."""


def us_hosted_allowlist(config: Optional[dict] = None) -> list:
    config = config or DEFAULT_CONFIG
    return list(config["residency"].get("us_hosted_provider_allowlist", []))


def provider_constraint(payload_tags, config: Optional[dict] = None) -> Optional[dict]:
    """§4.1 / A4 — the OpenRouter `provider` routing constraint for a payload.

    For a blocked-tag payload (e.g. key_material), return `{"only": [<US-hosted providers>]}` so
    OpenRouter serves the model ONLY from the US-hosted allowlist — the PRC first-party providers
    (moonshot / deepseek) are structurally excluded. For an unblocked payload, return None (no
    constraint). If a payload is blocked but no US-hosted allowlist is configured, raise
    ResidencyException so the caller diverts to the premium exception path instead of leaking it."""
    config = config or DEFAULT_CONFIG
    if not residency_blocked(payload_tags, config):
        return None
    allow = us_hosted_allowlist(config)
    if not allow:
        raise ResidencyException(
            "blocked-tag payload but no us_hosted_provider_allowlist configured; divert to exception path")
    return {"only": list(allow)}


# --------------------------------------------------------------- §4.2 tool-call schema validation

_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool,
          "object": dict, "array": list}


def validate_tool_call(args: dict, schema: dict) -> tuple[bool, Optional[str]]:
    """Minimal JSON-schema check before dispatch (required fields + declared types).
    TODO(PROGRAMMER): swap in `jsonschema` for full Draft-2020-12 coverage in production."""
    if not isinstance(args, dict):
        return False, "arguments must be an object"
    for req in schema.get("required", []):
        if req not in args:
            return False, f"missing required field: {req}"
    for key, spec in schema.get("properties", {}).items():
        if key in args and "type" in spec:
            expected = _TYPES.get(spec["type"])
            if expected and not isinstance(args[key], expected):
                return False, f"field '{key}' must be {spec['type']}"
    return True, None


def escalate_after_failures(schema_fail_count: int, config: Optional[dict] = None) -> bool:
    """§4.2 — after the second schema failure, escalate one tier (TIER 0 -> TIER 1)."""
    config = config or DEFAULT_CONFIG
    return schema_fail_count >= config["routing"]["max_tier0_retries"]


# --------------------------------------------------------------- Phoenix span attributes (extend only)

def tool_call_span_attrs(schema_valid: bool, retry_count: int) -> dict:
    """§4.2 — the cutover metric attributes to attach to the existing Phoenix tool-call span.
    (Extension only; the tracer itself is untouched — arize_client.log_tool_call adds these.)"""
    return {"tool_call.schema_valid": bool(schema_valid), "tool_call.retry_count": int(retry_count)}
