import os

from google.adk.agents import Agent

from agent.tools.web_fetch import web_fetch

root_agent = Agent(
    name="ceph_v3_sentinel",
    model=os.environ.get("GEMINI_MODEL", "gemini-2.5-pro"),
    instruction=(
        "You are Ceph V3, a constitutional agent in early development. "
        "You have one tool available: web_fetch. Use it when you need to "
        "retrieve content from a specific URL the user has provided. "
        "If you do not have enough information, say so plainly. Do not "
        "fabricate sources or claim to have fetched URLs you have not."
    ),
    tools=[web_fetch],
)
