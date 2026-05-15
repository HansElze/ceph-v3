"""ADK before_tool_callback that enforces hard constitutional limits.

Wire this into Agent(before_tool_callback=constitutional_guard) in planner.py.
The callback returns a structured error dict if a rule fires — ADK uses that
as the tool result without ever calling the actual tool function.
"""

import logging
from typing import Any, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from agent.constitutional.hard_limits import HardLimits, ToolCall

logger = logging.getLogger(__name__)

_limits = HardLimits()

# Injected by executor.py after ArizeTracer is initialised
_tracer: Any = None
# Injected run_id for ToolCall construction
_current_run_id: str = ""


def set_tracer(tracer: Any) -> None:
    global _tracer
    _tracer = tracer


def set_run_id(run_id: str) -> None:
    global _current_run_id
    _current_run_id = run_id


def constitutional_guard(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict]:
    """Return a blocked-response dict if a hard limit fires; else None.

    None  → ADK calls the real tool function.
    dict  → ADK uses this as the tool result; real tool is never called.
    """
    tool_call = ToolCall(
        name=tool.name,
        inputs=args,
        agent_run_id=_current_run_id,
    )
    result = _limits.check_tool_call(tool_call)

    if result.allowed:
        return None

    logger.warning(
        "[CONSTITUTIONAL BLOCK] rule=%s tool=%s reason=%s",
        result.rule_violated,
        tool.name,
        result.reason,
    )

    if _tracer is not None:
        try:
            _tracer.log_violation(
                rule=result.rule_violated or "unknown",
                details={"reason": result.reason, "inputs": args},
                halted=True,
            )
        except Exception as exc:
            logger.warning("guard: tracer.log_violation failed: %s", exc)

    return {
        "status": "blocked",
        "reason": result.reason,
        "rule": result.rule_violated,
        "error": f"[CONSTITUTIONAL VIOLATION: {result.rule_violated}] {result.reason}",
        "halted": True,
    }
