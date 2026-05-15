"""CLI entry point: python -m agent "your query here" """

import asyncio
import os
import sys
import traceback

from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault(
    "GOOGLE_CLOUD_LOCATION",
    os.environ.get("VERTEX_AI_LOCATION", "us-central1"),
)

from agent.executor import run

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        query = "Fetch https://example.com and summarize what you find there"
    try:
        asyncio.run(run(query))
    except Exception:
        traceback.print_exc()
        sys.exit(1)
