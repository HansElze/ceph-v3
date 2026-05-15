"""ArizeTracer — OpenTelemetry trace emitter targeting Arize AX.

Falls back to a no-op local provider when ARIZE_SPACE_ID / ARIZE_API_KEY
are not set, so every other module can import and call this unconditionally.
"""

import logging
import os
import time
import uuid
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import StatusCode
from openinference.semconv.trace import SpanAttributes

logger = logging.getLogger(__name__)

_TRACER: Optional[trace.Tracer] = None


def _init_tracer() -> trace.Tracer:
    global _TRACER
    if _TRACER is not None:
        return _TRACER

    space_id = os.environ.get("ARIZE_SPACE_ID", "").strip()
    api_key = os.environ.get("ARIZE_API_KEY", "").strip()
    project = os.environ.get("ARIZE_PROJECT_NAME", "ceph-v3-sentinel")

    if space_id and api_key:
        try:
            from arize.otel import register

            provider = register(
                space_id=space_id,
                api_key=api_key,
                project_name=project,
                batch=True,
            )
            trace.set_tracer_provider(provider)
            logger.info("Arize tracer registered for project=%s", project)
        except Exception as exc:
            logger.warning("Arize registration failed (%s) — using no-op tracer", exc)
            trace.set_tracer_provider(TracerProvider())
    else:
        logger.info("ARIZE credentials not set — using no-op local tracer")
        trace.set_tracer_provider(TracerProvider())

    _TRACER = trace.get_tracer("ceph-v3")
    return _TRACER


def _safe_str(value: object) -> str:
    try:
        return str(value)[:2000]
    except Exception:
        return "<unserializable>"


class ArizeTracer:
    """Thin wrapper around OTel spans targeting Arize AX.

    All public methods are safe — they never raise to the caller.
    Each call that creates a span returns a trace_id (UUID string) so the
    FabricationDetector can cross-reference claims against verified traces.
    """

    def __init__(self) -> None:
        self._tracer = _init_tracer()
        self._run_id: str = ""
        self._run_mission: str = ""
        # In-memory store: trace_id -> metadata for FabricationDetector
        self._traces: dict[str, dict] = {}

    # ------------------------------------------------------------------ run

    def start_run(self, agent_run_id: str, mission: str) -> None:
        self._run_id = agent_run_id
        self._run_mission = mission
        try:
            span = self._tracer.start_span("agent.run")
            span.set_attribute("agent.run_id", agent_run_id)
            span.set_attribute("agent.mission", mission[:500])
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "AGENT")
            span.end()
        except Exception as exc:
            logger.warning("ArizeTracer.start_run: %s", exc)

    def end_run(self, status: str, summary: str) -> None:
        try:
            span = self._tracer.start_span("agent.run.end")
            span.set_attribute("agent.run_id", self._run_id)
            span.set_attribute("agent.run.status", status)
            span.set_attribute("agent.run.summary", summary[:500])
            if status != "success":
                span.set_status(StatusCode.ERROR, status)
            span.end()
        except Exception as exc:
            logger.warning("ArizeTracer.end_run: %s", exc)

    # --------------------------------------------------------------- tool call

    def log_tool_call(
        self,
        tool_name: str,
        inputs: dict,
        output: dict,
        status: str,
        duration_ms: int,
    ) -> str:
        trace_id = str(uuid.uuid4())
        try:
            span = self._tracer.start_span(f"tool.{tool_name}")
            span.set_attribute("agent.run_id", self._run_id)
            span.set_attribute(SpanAttributes.TOOL_NAME, tool_name)
            span.set_attribute(SpanAttributes.INPUT_VALUE, _safe_str(inputs))
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, _safe_str(output))
            span.set_attribute("tool.status", status)
            span.set_attribute("tool.duration_ms", duration_ms)
            span.set_attribute("trace.id", trace_id)
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "TOOL")
            if status != "success":
                span.set_status(StatusCode.ERROR, f"{tool_name} failed: {status}")
            span.end()

            self._traces[trace_id] = {
                "type": "tool_call",
                "tool": tool_name,
                "status": status,
                "output": output,
                "run_id": self._run_id,
            }
        except Exception as exc:
            logger.warning("ArizeTracer.log_tool_call: %s", exc)

        return trace_id

    # --------------------------------------------------------------- llm call

    def log_llm_call(
        self,
        model: str,
        prompt: str,
        response: str,
        tokens: dict,
    ) -> str:
        trace_id = str(uuid.uuid4())
        try:
            span = self._tracer.start_span("llm.generate")
            span.set_attribute("agent.run_id", self._run_id)
            span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model)
            span.set_attribute(SpanAttributes.INPUT_VALUE, prompt[:2000])
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, response[:2000])
            span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_PROMPT, tokens.get("prompt", 0))
            span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_COMPLETION, tokens.get("completion", 0))
            span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_TOTAL, tokens.get("total", 0))
            span.set_attribute("trace.id", trace_id)
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "LLM")
            span.end()

            self._traces[trace_id] = {
                "type": "llm_call",
                "model": model,
                "run_id": self._run_id,
            }
        except Exception as exc:
            logger.warning("ArizeTracer.log_llm_call: %s", exc)

        return trace_id

    # ------------------------------------------------------------- violation

    def log_violation(self, rule: str, details: dict, halted: bool) -> str:
        trace_id = str(uuid.uuid4())
        try:
            span = self._tracer.start_span("constitutional.violation")
            span.set_attribute("agent.run_id", self._run_id)
            span.set_attribute("violation.rule", rule)
            span.set_attribute("violation.details", _safe_str(details))
            span.set_attribute("violation.halted", halted)
            span.set_attribute("trace.id", trace_id)
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "GUARDRAIL")
            span.set_status(StatusCode.ERROR, f"Constitutional violation: {rule}")
            span.end()

            self._traces[trace_id] = {
                "type": "violation",
                "rule": rule,
                "halted": halted,
                "run_id": self._run_id,
            }
            logger.warning("[VIOLATION] rule=%s halted=%s details=%s", rule, halted, details)
        except Exception as exc:
            logger.warning("ArizeTracer.log_violation: %s", exc)

        return trace_id

    # ---------------------------------------------------------- trace store

    def get_trace(self, trace_id: str) -> Optional[dict]:
        return self._traces.get(trace_id)

    def list_recent_traces(self, agent_run_id: str) -> list[dict]:
        return [t for t in self._traces.values() if t.get("run_id") == agent_run_id]
