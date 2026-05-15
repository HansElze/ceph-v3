"""Hard constitutional limits — code, not prompts.

All rules execute before any tool call reaches the tool function.
A violated rule blocks execution structurally. There is no prompt that
can override these rules.

This is the mechanism Ceph V1 lacked.
"""

import re
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class ToolCall:
    name: str
    inputs: dict
    agent_run_id: str


@dataclass(frozen=True)
class CheckResult:
    allowed: bool
    rule_violated: Optional[str]
    reason: Optional[str]


_ALLOWED = CheckResult(allowed=True, rule_violated=None, reason=None)

# Private/internal address patterns the agent must never reach
_PRIVATE_HOST = re.compile(
    r"^(localhost"
    r"|127\.\d+\.\d+\.\d+"
    r"|10\.\d+\.\d+\.\d+"
    r"|192\.168\.\d+\.\d+"
    r"|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+"
    r"|169\.254\.\d+\.\d+"
    r"|::1"
    r"|0\.0\.0\.0"
    r")$",
    re.IGNORECASE,
)


# ------------------------------------------------------------------ rules


def _check_unauthorized_external_send(tool_call: ToolCall) -> CheckResult:
    """Block any tool whose name starts with 'send_' or contains 'external'."""
    name = tool_call.name.lower()
    if name.startswith("send_") or "external" in name:
        return CheckResult(
            allowed=False,
            rule_violated="unauthorized_external_send",
            reason="External send requires operator approval",
        )
    return _ALLOWED


def _check_private_network(tool_call: ToolCall) -> CheckResult:
    """Block web_fetch calls to private/internal network addresses."""
    if tool_call.name != "web_fetch":
        return _ALLOWED

    url = str(tool_call.inputs.get("url", "")).strip()
    if not url:
        return _ALLOWED  # empty-url caught by http_scheme_required

    host_part = url.split("://", 1)[-1].split("/")[0].split("?")[0]
    host = host_part.split(":")[0].lower()

    if _PRIVATE_HOST.match(host):
        return CheckResult(
            allowed=False,
            rule_violated="private_network_block",
            reason=f"web_fetch blocked: {host!r} is a private/internal address",
        )
    return _ALLOWED


def _check_http_scheme(tool_call: ToolCall) -> CheckResult:
    """Require http or https scheme for web_fetch; block empty URLs."""
    if tool_call.name != "web_fetch":
        return _ALLOWED

    url = str(tool_call.inputs.get("url", "")).strip()

    if not url:
        return CheckResult(
            allowed=False,
            rule_violated="tool_input_required",
            reason="web_fetch called with empty URL",
        )

    scheme = url.split("://")[0].lower() if "://" in url else ""
    if scheme not in ("http", "https"):
        return CheckResult(
            allowed=False,
            rule_violated="http_scheme_required",
            reason=f"web_fetch requires http/https URL, got scheme={scheme!r}",
        )
    return _ALLOWED


# ------------------------------------------------------------------ registry


class HardLimits:
    """Deterministic constitutional rule registry.

    Usage:
        limits = HardLimits()
        result = limits.check_tool_call(ToolCall(name="send_external", ...))
        if not result.allowed:
            halt(result.rule_violated, result.reason)

    Rules are checked in registration order; first failure wins.
    """

    def __init__(self) -> None:
        self._rules: dict[str, Callable[[ToolCall], CheckResult]] = {}
        # Default rules registered at construction
        self.register("unauthorized_external_send", _check_unauthorized_external_send)
        self.register("private_network_block", _check_private_network)
        self.register("http_scheme_required", _check_http_scheme)

    def register(
        self, rule_name: str, checker: Callable[[ToolCall], CheckResult]
    ) -> None:
        """Add or replace a rule. Rules are evaluated in insertion order."""
        self._rules[rule_name] = checker

    def check_tool_call(self, tool_call: ToolCall) -> CheckResult:
        """Run all registered rules; return first failure or ALLOWED."""
        for checker in self._rules.values():
            result = checker(tool_call)
            if not result.allowed:
                return result
        return _ALLOWED
