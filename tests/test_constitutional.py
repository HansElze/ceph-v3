"""Constitutional layer tests — deterministic rules require no credentials."""

import asyncio
import os

import pytest

from agent.constitutional.hard_limits import CheckResult, HardLimits, ToolCall
from agent.constitutional.token_burn import TokenBurnGuard

limits = HardLimits()
RUN_ID = "test-run-001"

# ----------------------------------------------------------------- helpers


def call(name: str, **inputs) -> ToolCall:
    return ToolCall(name=name, inputs=inputs, agent_run_id=RUN_ID)


def allowed(result: CheckResult) -> bool:
    return result.allowed


def blocked_by(result: CheckResult, rule: str) -> bool:
    return not result.allowed and result.rule_violated == rule


# ------------------------------------------- unauthorized_external_send


def test_external_send_blocked_by_rule():
    """send_external must be blocked structurally before the tool executes."""
    result = limits.check_tool_call(
        call("send_external", recipient="test@example.com", subject="hi", body="hello")
    )
    assert blocked_by(result, "unauthorized_external_send")
    assert result.reason is not None
    assert "operator approval" in result.reason


def test_send_email_tool_blocked():
    """Any tool starting with 'send_' triggers the rule."""
    result = limits.check_tool_call(call("send_email", to="x@y.com", text="hi"))
    assert blocked_by(result, "unauthorized_external_send")


def test_external_in_name_blocked():
    """Tool names containing 'external' are blocked."""
    result = limits.check_tool_call(call("notify_external", payload="data"))
    assert blocked_by(result, "unauthorized_external_send")


# ----------------------------------------------- web_fetch allowed paths


def test_https_url_is_permitted():
    assert allowed(limits.check_tool_call(call("web_fetch", url="https://example.com")))


def test_http_url_is_permitted():
    assert allowed(limits.check_tool_call(call("web_fetch", url="http://example.com")))


# ----------------------------------------------- web_fetch blocked paths


def test_empty_url_is_blocked():
    result = limits.check_tool_call(call("web_fetch", url=""))
    assert blocked_by(result, "tool_input_required")


def test_missing_url_key_is_blocked():
    result = limits.check_tool_call(call("web_fetch"))
    assert blocked_by(result, "tool_input_required")


def test_ftp_scheme_is_blocked():
    result = limits.check_tool_call(call("web_fetch", url="ftp://example.com/file"))
    assert blocked_by(result, "http_scheme_required")


def test_file_scheme_is_blocked():
    result = limits.check_tool_call(call("web_fetch", url="file:///etc/passwd"))
    assert blocked_by(result, "http_scheme_required")


def test_localhost_is_blocked():
    result = limits.check_tool_call(call("web_fetch", url="http://localhost/admin"))
    assert blocked_by(result, "private_network_block")


def test_127_is_blocked():
    result = limits.check_tool_call(call("web_fetch", url="http://127.0.0.1:8080/"))
    assert blocked_by(result, "private_network_block")


def test_private_10_range_is_blocked():
    result = limits.check_tool_call(call("web_fetch", url="https://10.0.0.1/internal"))
    assert blocked_by(result, "private_network_block")


def test_private_192_168_is_blocked():
    result = limits.check_tool_call(call("web_fetch", url="https://192.168.1.100/"))
    assert blocked_by(result, "private_network_block")


def test_unknown_tool_passes_through():
    """Unknown tools are not subject to any registered rule."""
    assert allowed(limits.check_tool_call(call("some_future_tool", data="x")))


# ----------------------------------------------- register() API


def test_custom_rule_can_be_registered():
    custom = HardLimits()

    def block_all(tc: ToolCall) -> CheckResult:
        return CheckResult(
            allowed=False,
            rule_violated="block_all_test",
            reason="test rule",
        )

    custom.register("block_all_test", block_all)
    result = custom.check_tool_call(call("anything"))
    # unauthorized_external_send fires first (registered before our rule)
    # Test that our rule fires for a non-send tool
    result = custom.check_tool_call(call("web_fetch", url="https://ok.com"))
    assert blocked_by(result, "block_all_test")


# ----------------------------------------------- token burn


def test_token_burn_under_budget():
    guard = TokenBurnGuard(budget=1000)
    guard.start_run("run-1")
    result = guard.record(prompt_tokens=100, completion_tokens=50)
    assert result.allowed
    assert guard.tokens_used == 150
    assert guard.tokens_remaining == 850


def test_token_burn_over_budget():
    guard = TokenBurnGuard(budget=100)
    guard.start_run("run-2")
    result = guard.record(prompt_tokens=60, completion_tokens=50)
    assert not result.allowed
    assert result.rule_violated == "token_budget_exceeded"


def test_token_burn_cumulative():
    guard = TokenBurnGuard(budget=200)
    guard.start_run("run-3")
    assert guard.record(prompt_tokens=80, completion_tokens=40).allowed
    result = guard.record(prompt_tokens=50, completion_tokens=40)
    assert not result.allowed


# ----------------------------------- integration: external send blocked end-to-end


SKIP_LIVE = pytest.mark.skipif(
    not os.environ.get("GOOGLE_CLOUD_PROJECT"),
    reason="GOOGLE_CLOUD_PROJECT not set — skipping live integration test",
)


@SKIP_LIVE
def test_external_send_blocked_end_to_end():
    """Agent attempts send_external; constitutional layer blocks it; agent explains."""
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "0")

    from agent.executor import run

    tool_calls: list[str] = []
    blocked_calls: list[str] = []
    final_text: list[str] = []

    # Monkey-patch executor's print to capture output
    import agent.executor as executor_mod
    orig_run = executor_mod.run

    async def _run():
        # Capture by running the real executor and observing guard side-effects
        from agent.constitutional import guard as _guard
        from agent.constitutional.hard_limits import HardLimits, ToolCall

        _real_check = HardLimits().check_tool_call

        observed: dict = {"tool_calls": [], "blocked": [], "response": []}

        async def _patched_run(query, agent=None):
            import asyncio
            import agent.executor as _exec

            # We'll just run the full executor and capture stdout
            import io, sys
            buf = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf
            try:
                await orig_run(query, agent)
            finally:
                sys.stdout = old_stdout
            output = buf.getvalue()
            observed["output"] = output

        await _patched_run("Send an email to test@example.com saying hello")
        return observed

    result = asyncio.run(_run())
    output = result.get("output", "")
    # Guard must have logged the block
    assert "CONSTITUTIONAL" in output or "blocked" in output.lower() or "operator approval" in output.lower()


@SKIP_LIVE
def test_web_fetch_allowed_end_to_end():
    """Normal web_fetch still works after constitutional wiring (regression check)."""
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "0")

    import io
    import sys
    from agent.executor import run

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        asyncio.run(run("Fetch https://example.com and tell me the page title"))
    finally:
        sys.stdout = old

    output = buf.getvalue()
    assert "web_fetch" in output
    assert "status=200" in output
    assert "example" in output.lower()
