"""ConstitutionalExecutor — runs an agent run with full constitutional + trace wiring.

This module owns:
  - ArizeTracer initialisation and lifecycle (start_run / end_run)
  - Injection of tracer into the guard module (before_tool_callback sees it)
  - Tool call trace emission (log_tool_call on every function response)
  - LLM call trace emission (log_llm_call on final response events)

The ADK Runner + before_tool_callback in guard.py handles structural
blocking; this module handles observability and lifecycle coordination.
"""

import logging
import time
import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent.constitutional import guard as _guard
from observability.arize_client import ArizeTracer

logger = logging.getLogger(__name__)

_APP_NAME = "ceph-v3"
_USER_ID = "dev"


async def run(query: str, agent=None) -> None:
    """Execute a single agent run with constitutional enforcement and Arize tracing.

    Args:
        query: User query string.
        agent: ADK Agent instance. Defaults to root_agent from planner.
    """
    if agent is None:
        from agent.planner import root_agent
        agent = root_agent

    # --- initialise tracer and inject into guard ---
    tracer = ArizeTracer()
    run_id = str(uuid.uuid4())[:8]
    _guard.set_tracer(tracer)
    _guard.set_run_id(run_id)
    tracer.start_run(agent_run_id=run_id, mission=query)

    # --- ADK session + runner ---
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=_APP_NAME, user_id=_USER_ID
    )
    runner = Runner(
        app_name=_APP_NAME,
        agent=agent,
        session_service=session_service,
    )

    message = types.Content(role="user", parts=[types.Part(text=query)])
    print(f"[run:{run_id}] {query}\n")

    # Track in-flight calls: function_call.id -> {name, args, start_ms}
    pending: dict[str, dict] = {}
    final_text: list[str] = []
    run_status = "success"

    try:
        async for event in runner.run_async(
            user_id=_USER_ID,
            session_id=session.id,
            new_message=message,
        ):
            # --- tool call started ---
            for call in event.get_function_calls():
                pending[call.id] = {
                    "name": call.name,
                    "args": call.args,
                    "start_ms": int(time.monotonic() * 1000),
                }
                print(f"[tool call]  {call.name}({call.args})")

            # --- tool call completed ---
            for resp in event.get_function_responses():
                info = pending.pop(resp.id, {})
                output = resp.response or {}
                duration = int(time.monotonic() * 1000) - info.get("start_ms", 0)

                if output.get("halted") or output.get("status") == "blocked":
                    status = "blocked"
                elif output.get("status") == 200 or output.get("status") == "sent":
                    status = "success"
                else:
                    status = "error"

                trace_id = tracer.log_tool_call(
                    tool_name=resp.name,
                    inputs=info.get("args", {}),
                    output=output,
                    status=status,
                    duration_ms=duration,
                )
                print(
                    f"[tool resp]  {resp.name} -> "
                    f"status={output.get('status', '?')} trace={trace_id}"
                )

            # --- final LLM response ---
            if event.is_final_response() and event.content:
                parts_text = []
                for part in event.content.parts:
                    if part.text:
                        parts_text.append(part.text)
                if parts_text:
                    combined = "\n".join(parts_text)
                    final_text.append(combined)
                    print(f"\n[response]\n{combined}")
                    tracer.log_llm_call(
                        model=agent.model or "unknown",
                        prompt=query,
                        response=combined,
                        tokens={},
                    )

    except Exception as exc:
        run_status = "error"
        logger.error("executor.run failed: %s", exc)
        raise
    finally:
        summary = final_text[-1][:200] if final_text else "(no response)"
        tracer.end_run(status=run_status, summary=summary)
