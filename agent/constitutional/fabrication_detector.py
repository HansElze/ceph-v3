"""
fabrication_detector.py

Constitutional rule: every claim in agent output must trace back to a verified
tool call result. If the agent asserts a fact without a corresponding successful
tool call, the assertion is a fabrication and the agent must halt.

This is the rule that would have caught Ceph V1's decommissioning failure.

Contract:
    detector = FabricationDetector(trace_store)
    result = detector.check(agent_output, claimed_sources)
    if result.violated:
        halt_agent(reason=result.reason)
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FabricationCheckResult:
    violated: bool
    reason: str
    unverified_claims: list[str]
    trace_ids_checked: list[str]


class TraceStore(Protocol):
    """Abstraction over the observability layer (Arize MCP in production)."""

    def get_trace(self, trace_id: str) -> dict | None: ...
    def list_recent_traces(self, agent_run_id: str) -> list[dict]: ...


class FabricationDetector:
    """
    Detects fabricated claims in agent output by cross-referencing every
    cited source against the trace store.

    A claim is fabricated if:
      1. It cites a source (URL, document, tool result) that has no
         corresponding successful trace in this agent run, OR
      2. It cites a trace_id that exists but failed (error, timeout, refused), OR
      3. It asserts a specific factual claim that no tool call could have
         produced (heuristic — runs Gemini-as-judge in week 3)

    Rules 1 and 2 are deterministic and ship in week 2.
    Rule 3 is LLM-as-judge and ships in week 3 if time permits.
    """

    def __init__(self, trace_store: TraceStore):
        self._traces = trace_store

    def check(
        self,
        agent_output: str,
        claimed_sources: list[str],
        agent_run_id: str,
    ) -> FabricationCheckResult:
        # TODO(day-6): implement deterministic source verification
        # TODO(day-15): add LLM-as-judge for unstated claims
        raise NotImplementedError("Stub — implement day 6 per WEEK_1_PLAN.md")

    def _verify_source(self, source: str, agent_run_id: str) -> bool:
        """Return True if `source` corresponds to a successful trace."""
        raise NotImplementedError
