import os

from google.adk.agents import Agent

from agent.constitutional.guard import constitutional_guard
from agent.identity import build_system_prompt
from agent.tools.send_external import send_external
from agent.tools.web_fetch import web_fetch

# Instruction is the STABLE identity prefix (SOUL + roster + constitutional preamble). Assembled once at
# import; byte-stable so the provider prompt-cache holds. Ceph knows he is Ceph regardless of model/tier.
root_agent = Agent(
    name="ceph_v3_sentinel",
    model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    instruction=build_system_prompt(),
    tools=[web_fetch, send_external],
    before_tool_callback=constitutional_guard,
)
