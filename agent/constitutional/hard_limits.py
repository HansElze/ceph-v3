"""Hard constitutional limits — code, not prompts.

These rules execute before any tool call reaches the tool function.
A violation blocks execution structurally. There is no prompt that
can override these rules.

This is the mechanism Ceph V1 lacked.
"""

import re
from dataclasses import dataclass
from typing import Optional


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


@dataclass(frozen=True)
class ConstitutionalViolation:
    rule: str
    reason: str
    tool_name: str
    inputs: dict


class HardLimits:
    """Deterministic constitutional rules applied before every tool call.

    Usage:
        limits = HardLimits()
        violation = limits.check_tool_call("web_fetch", {"url": "http://..."})
        if violation:
            halt_or_return_error(violation)
    """

    def check_tool_call(
        self, tool_name: str, inputs: dict
    ) -> Optional[ConstitutionalViolation]:
        """Return a ConstitutionalViolation if the call violates any hard limit.

        Returns None if the call is permitted.
        """
        checker = self._TOOL_CHECKERS.get(tool_name)
        if checker:
            return checker(self, inputs)
        return None

    def _check_web_fetch(self, inputs: dict) -> Optional[ConstitutionalViolation]:
        url = str(inputs.get("url", "")).strip()

        if not url:
            return ConstitutionalViolation(
                rule="TOOL_INPUT_REQUIRED",
                reason="web_fetch called with empty URL",
                tool_name="web_fetch",
                inputs=inputs,
            )

        scheme = url.split("://")[0].lower() if "://" in url else ""
        if scheme not in ("http", "https"):
            return ConstitutionalViolation(
                rule="HTTP_SCHEME_REQUIRED",
                reason=f"web_fetch requires http/https URL, got scheme={scheme!r} in {url!r}",
                tool_name="web_fetch",
                inputs=inputs,
            )

        # Extract hostname (strip port, path, query)
        host_part = url.split("://", 1)[-1].split("/")[0].split("?")[0]
        host = host_part.split(":")[0].lower()

        if _PRIVATE_HOST.match(host):
            return ConstitutionalViolation(
                rule="NO_PRIVATE_NETWORK",
                reason=f"web_fetch blocked: {host!r} is a private/internal address",
                tool_name="web_fetch",
                inputs=inputs,
            )

        return None

    # Register per-tool checkers here as tools are added
    _TOOL_CHECKERS: dict = {}


# Populate after class definition (avoids forward-reference issues)
HardLimits._TOOL_CHECKERS = {
    "web_fetch": HardLimits._check_web_fetch,
}
