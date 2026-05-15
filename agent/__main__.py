"""CLI entry point: python -m agent "your query here" """

import asyncio
import os
import sys
import time
import traceback
import uuid

from dotenv import load_dotenv

load_dotenv()

# google-genai reads GOOGLE_CLOUD_LOCATION; .env may use VERTEX_AI_LOCATION
os.environ.setdefault(
    "GOOGLE_CLOUD_LOCATION",
    os.environ.get("VERTEX_AI_LOCATION", "us-central1"),
)

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent.constitutional import guard as constitutional_guard
from agent.planner import root_agent
from observability.arize_client import ArizeTracer

_APP_NAME = "ceph-v3"
_USER_ID = "dev"


async def run(query: str) -> None:
    tracer = ArizeTracer()
    constitutional_guard.set_tracer(tracer)

    run_id = str(uuid.uuid4())[:8]
    tracer.start_run(agent_run_id=run_id, mission=query)

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=_APP_NAME, user_id=_USER_ID
    )

    runner = Runner(
        app_name=_APP_NAME,
        agent=root_agent,
        session_service=session_service,
    )

    message = types.Content(role="user", parts=[types.Part(text=query)])
    print(f"[run:{run_id}] {query}\n")

    # Track in-flight tool calls: function_call.id -> {name, args, start_ms}
    pending: dict[str, dict] = {}

    async for event in runner.run_async(
        user_id=_USER_ID,
        session_id=session.id,
        new_message=message,
    ):
        for call in event.get_function_calls():
            pending[call.id] = {
                "name": call.name,
                "args": call.args,
                "start_ms": int(time.monotonic() * 1000),
            }
            print(f"[tool call]  {call.name}({call.args})")

        for resp in event.get_function_responses():
            call_info = pending.pop(resp.id, {})
            output = resp.response or {}
            status = "success" if output.get("status", 0) == 200 else "error"
            if output.get("halted"):
                status = "blocked"
            duration = int(time.monotonic() * 1000) - call_info.get("start_ms", 0)

            trace_id = tracer.log_tool_call(
                tool_name=resp.name,
                inputs=call_info.get("args", {}),
                output=output,
                status=status,
                duration_ms=duration,
            )
            http_status = output.get("status", "?")
            print(f"[tool resp]  {resp.name} -> status={http_status} trace={trace_id}")

        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if part.text:
                    print(f"\n[response]\n{part.text}")

    tracer.end_run(status="success", summary=query[:200])


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        query = "Fetch https://example.com and summarize what you find there"

    try:
        asyncio.run(run(query))
    except Exception:
        traceback.print_exc()
        sys.exit(1)
