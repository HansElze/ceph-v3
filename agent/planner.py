import os

from google.adk.agents import Agent

from agent.constitutional.guard import constitutional_guard
from agent.tools.send_external import send_external
from agent.tools.web_fetch import web_fetch

root_agent = Agent(
    name="ceph_v3_sentinel",
    model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    instruction=(
        "You are Ceph V3, a constitutional agent in early development. "
        "You have two tools: web_fetch (retrieve URLs) and send_external "
        "(send messages outside the agent). "
        "The send_external tool requires operator approval and may be blocked "
        "by your constitutional layer. If a tool call is blocked, explain the "
        "reason to the user plainly — do not retry the blocked action. "
        "Do not fabricate sources or claim to have fetched URLs you have not."
    ),
    tools=[web_fetch, send_external],
    before_tool_callback=constitutional_guard,
)
