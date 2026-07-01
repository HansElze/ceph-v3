"""MODEL-001 — routing decision logic tests (no network, no keys)."""

from __future__ import annotations

from agent import model_routing as mr


# --------------------------------------------------------------- §3 escalation trigger


def test_default_task_stays_routine():
    assert mr.select_tier({"task_type": "heartbeat"}) == mr.ROUTINE


def test_high_stakes_escalates():
    assert mr.select_tier({"high_stakes": True}) == mr.ESCALATE


def test_governance_validation_report_escalates():
    assert mr.select_tier({"domain": "governance_review", "task_type": "prp_validation_report"}) == mr.ESCALATE
    assert mr.select_tier({"domain": "financial_modeling", "task_type": "council_panel"}) == mr.ESCALATE


def test_domain_without_matching_task_type_stays_routine():
    # governance domain but a routine task type -> not escalated by §3.2
    assert mr.select_tier({"domain": "governance_review", "task_type": "status_reply"}) == mr.ROUTINE


def test_tier0_failure_escalates():
    assert mr.select_tier({"schema_fail_count": 2}) == mr.ESCALATE            # failed twice
    assert mr.select_tier({"confidence": 0.4}) == mr.ESCALATE                 # below threshold
    assert mr.select_tier({"acceptance_passed": False}) == mr.ESCALATE        # acceptance failed
    assert mr.select_tier({"schema_fail_count": 1, "confidence": 0.9}) == mr.ROUTINE


def test_navigator_override_escalates():
    assert mr.select_tier({"navigator_override": True}) == mr.ESCALATE


def test_never_burn_list_stays_routine():
    for t in ("heartbeat", "inbox_poll", "status_reply", "role_ack", "swarm_bus", "outreach_tracking"):
        assert mr.select_tier({"task_type": t}) == mr.ROUTINE


# --------------------------------------------------------------- §4.1 residency gate


def test_residency_blocks_sensitive_tags():
    assert mr.residency_blocked(["canon_sensitive"]) is True
    assert mr.residency_blocked(["investor_sensitive", "routine"]) is True
    assert mr.residency_blocked(["routine"]) is False
    assert mr.residency_blocked([]) is False


def test_endpoint_allowed_respects_residency():
    # a key-material payload may not hit a first-party PRC endpoint...
    assert mr.endpoint_allowed("api.deepseek.com", ["key_material"]) is False
    # ...but may go via a non-blocked endpoint (e.g. OpenRouter / US-hosted)
    assert mr.endpoint_allowed("openrouter.ai", ["key_material"]) is True
    # a clean payload can go anywhere
    assert mr.endpoint_allowed("api.moonshot.ai", ["routine"]) is True


# --------------------------------------------------------------- §4.2 tool-call schema validation


_SCHEMA = {"required": ["path"], "properties": {"path": {"type": "string"}, "count": {"type": "integer"}}}


def test_validate_tool_call_ok():
    ok, err = mr.validate_tool_call({"path": "a.txt", "count": 3}, _SCHEMA)
    assert ok and err is None


def test_validate_tool_call_missing_required():
    ok, err = mr.validate_tool_call({"count": 3}, _SCHEMA)
    assert not ok and "missing required" in err


def test_validate_tool_call_wrong_type():
    ok, err = mr.validate_tool_call({"path": "a.txt", "count": "three"}, _SCHEMA)
    assert not ok and "count" in err


def test_escalate_after_two_failures():
    assert mr.escalate_after_failures(1) is False
    assert mr.escalate_after_failures(2) is True


def test_span_attrs_shape():
    a = mr.tool_call_span_attrs(schema_valid=False, retry_count=2)
    assert a == {"tool_call.schema_valid": False, "tool_call.retry_count": 2}


def test_load_config_has_expected_shape():
    c = mr.load_config()
    assert set(c) >= {"tiers", "routing", "residency"}
    assert c["tiers"]["routine"]["model"] == "deepseek/deepseek-v4-flash"
