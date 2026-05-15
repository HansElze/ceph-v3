"""ADK before_tool_callback that enforces hard constitutional limits.

Wire this into Agent(before_tool_callback=constitutional_guard) in planner.py.
The callback returns a structured error dict if a limit fires — ADK uses that
as the tool result without ever calling the actual tool function.
"""

import logging
from typing import Any, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from agent.constitutional.hard_limits import HardLimits

logger = logging.getLogger(__name__)

_limits = HardLimits()

# Module-level tracer reference — set by __main__.py after ArizeTracer is init'd
_tracer = None


def set_tracer(tracer: Any) -> None:
    """Inject the ArizeTracer instance so violations are logged to Arize."""
    global _tracer
    _tracer = tracer


def constitutional_guard(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict]:
    """Return a blocked-response dict if a hard limit fires; else None.

    Returning None tells ADK to proceed with the real tool call.
    Returning a dict tells ADK to use that as the tool result and skip the tool.
    """
    violation = _limits.check_tool_call(tool.name, args)
    if violation is None:
        return None

    logger.warning(
        "[CONSTITUTIONAL BLOCK] rule=%s tool=%s reason=%s",
        violation.rule,
        violation.tool_name,
        violation.reason,
    )

    if _tracer is not None:
        try:
            _tracer.log_violation(
                rule=violation.rule,
                details={"reason": violation.reason, "inputs": violation.inputs},
                halted=True,
            )
        except Exception as exc:
            logger.warning("guard: tracer.log_violation failed: %s", exc)

    return {
        "status": 0,
        "content": "",
        "error": f"[CONSTITUTIONAL VIOLATION: {violation.rule}] {violation.reason}",
        "halted": True,
    }
