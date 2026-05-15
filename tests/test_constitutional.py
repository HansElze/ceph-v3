"""Tests for constitutional hard limits — these must pass with no credentials."""

from agent.constitutional.hard_limits import HardLimits
from agent.constitutional.token_burn import TokenBurnGuard

limits = HardLimits()


# ----------------------------------------------------------------- web_fetch

def test_https_url_is_permitted():
    assert limits.check_tool_call("web_fetch", {"url": "https://example.com"}) is None


def test_http_url_is_permitted():
    assert limits.check_tool_call("web_fetch", {"url": "http://example.com"}) is None


def test_empty_url_is_blocked():
    v = limits.check_tool_call("web_fetch", {"url": ""})
    assert v is not None
    assert v.rule == "TOOL_INPUT_REQUIRED"


def test_missing_url_key_is_blocked():
    v = limits.check_tool_call("web_fetch", {})
    assert v is not None
    assert v.rule == "TOOL_INPUT_REQUIRED"


def test_ftp_scheme_is_blocked():
    v = limits.check_tool_call("web_fetch", {"url": "ftp://example.com/file"})
    assert v is not None
    assert v.rule == "HTTP_SCHEME_REQUIRED"


def test_file_scheme_is_blocked():
    v = limits.check_tool_call("web_fetch", {"url": "file:///etc/passwd"})
    assert v is not None
    assert v.rule == "HTTP_SCHEME_REQUIRED"


def test_localhost_is_blocked():
    v = limits.check_tool_call("web_fetch", {"url": "http://localhost/admin"})
    assert v is not None
    assert v.rule == "NO_PRIVATE_NETWORK"


def test_127_is_blocked():
    v = limits.check_tool_call("web_fetch", {"url": "http://127.0.0.1:8080/"})
    assert v is not None
    assert v.rule == "NO_PRIVATE_NETWORK"


def test_private_10_range_is_blocked():
    v = limits.check_tool_call("web_fetch", {"url": "https://10.0.0.1/internal"})
    assert v is not None
    assert v.rule == "NO_PRIVATE_NETWORK"


def test_private_192_168_is_blocked():
    v = limits.check_tool_call("web_fetch", {"url": "https://192.168.1.100/"})
    assert v is not None
    assert v.rule == "NO_PRIVATE_NETWORK"


def test_unknown_tool_is_permitted():
    """Unknown tools pass through — limits only apply to registered tools."""
    assert limits.check_tool_call("some_future_tool", {"data": "x"}) is None


# ----------------------------------------------------------------- token burn

def test_token_burn_under_budget():
    guard = TokenBurnGuard(budget=1000)
    guard.start_run("run-1")
    v = guard.record(prompt_tokens=100, completion_tokens=50)
    assert v is None
    assert guard.tokens_used == 150
    assert guard.tokens_remaining == 850


def test_token_burn_over_budget():
    guard = TokenBurnGuard(budget=100)
    guard.start_run("run-2")
    v = guard.record(prompt_tokens=60, completion_tokens=50)
    assert v is not None
    assert v.rule == "TOKEN_BUDGET_EXCEEDED"
    assert "110" in v.reason


def test_token_burn_cumulative():
    guard = TokenBurnGuard(budget=200)
    guard.start_run("run-3")
    assert guard.record(prompt_tokens=80, completion_tokens=40) is None  # 120 used
    v = guard.record(prompt_tokens=50, completion_tokens=40)  # 210 used
    assert v is not None
    assert v.rule == "TOKEN_BUDGET_EXCEEDED"
