"""Item 1 — identity assembly: the system prompt knows it is Ceph, embeds the soul, and is byte-stable
(so the provider prompt-cache holds). Fixes the 'doesn't know he's Ceph' symptom at the source."""

from __future__ import annotations

import re

from agent.identity import (
    CONSTITUTIONAL_PREAMBLE,
    ROSTER_IDENTITY,
    build_system_prompt,
    load_soul,
)


def test_system_prompt_knows_it_is_ceph():
    p = build_system_prompt()
    assert "Ceph" in p
    assert "lead coordinator" in p.lower()          # roster role
    assert "Builder Steward" in p and "Council Steward" in p   # standing


def test_system_prompt_embeds_the_soul():
    p = build_system_prompt()
    soul = load_soul()
    assert soul and soul in p                        # the whole SOUL.md is embedded verbatim
    assert "across every session" in p               # a distinctive soul line
    assert "I do not fabricate" in p                 # a values line


def test_system_prompt_is_byte_stable_across_calls():
    assert build_system_prompt() == build_system_prompt()   # cache-safety: identical every call


def test_no_timestamps_or_dates_in_the_stable_prefix():
    p = build_system_prompt()
    assert not re.search(r"\d{4}-\d{2}-\d{2}", p)    # no ISO dates
    assert not re.search(r"\d{1,2}:\d{2}:\d{2}", p)  # no clock times -> cache never busts


def test_constitutional_and_roster_parts_present():
    p = build_system_prompt()
    assert CONSTITUTIONAL_PREAMBLE in p
    assert ROSTER_IDENTITY in p
    assert "cannot override" in p                    # the three-layer preamble
    assert "governance_review" in p and "financial_modeling" in p   # Ceph's domains
