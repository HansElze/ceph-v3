"""Smoke test: agent calls web_fetch and returns a non-empty response."""

import asyncio
import os

import pytest

SKIP_REASON = "GOOGLE_CLOUD_PROJECT not set — skipping live integration test"


@pytest.mark.skipif(
    not os.environ.get("GOOGLE_CLOUD_PROJECT"), reason=SKIP_REASON
)
def test_agent_calls_web_fetch_and_responds() -> None:
    os.environ.setdefault(
        "GOOGLE_CLOUD_LOCATION",
        os.environ.get("VERTEX_AI_LOCATION", "us-central1"),
    )
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from agent.planner import root_agent

    tool_calls: list[str] = []
    final_text: list[str] = []

    async def _run() -> None:
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name="ceph-v3", user_id="test"
        )
        runner = Runner(
            app_name="ceph-v3",
            agent=root_agent,
            session_service=session_service,
        )
        message = types.Content(
            role="user",
            parts=[types.Part(text="Fetch https://example.com and tell me what you find")],
        )
        async for event in runner.run_async(
            user_id="test",
            session_id=session.id,
            new_message=message,
        ):
            for call in event.get_function_calls():
                tool_calls.append(call.name)
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if part.text:
                        final_text.append(part.text)

    asyncio.run(_run())

    assert tool_calls, "Agent never called any tool — expected at least one web_fetch call"
    assert "web_fetch" in tool_calls, f"Expected web_fetch call, got: {tool_calls}"
    assert final_text, "Agent returned no final response text"
    assert any(text.strip() for text in final_text), "Final response was empty"
