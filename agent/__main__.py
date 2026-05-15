"""CLI entry point: python -m agent "your query here" """

import asyncio
import os
import sys
import traceback

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

from agent.planner import root_agent

_APP_NAME = "ceph-v3"
_USER_ID = "dev"


async def run(query: str) -> None:
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

    print(f"[query] {query}\n")

    async for event in runner.run_async(
        user_id=_USER_ID,
        session_id=session.id,
        new_message=message,
    ):
        for call in event.get_function_calls():
            print(f"[tool call]  {call.name}({call.args})")
        for resp in event.get_function_responses():
            status = resp.response.get("status") if resp.response else "?"
            print(f"[tool resp]  {resp.name} -> status={status}")
        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if part.text:
                    print(f"\n[response]\n{part.text}")


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        query = "Fetch https://example.com and summarize what you find there"

    try:
        asyncio.run(run(query))
    except Exception:
        traceback.print_exc()
        sys.exit(1)
