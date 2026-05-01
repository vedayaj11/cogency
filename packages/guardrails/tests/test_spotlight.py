"""Spotlight wrapper tests."""

from __future__ import annotations

from guardrails.spotlight import SYSTEM_PROMPT_PREFIX, wrap, wrap_field


def test_wrap_brackets_text():
    out = wrap("Some untrusted document content here.")
    assert "<<UNTRUSTED_DATA_START>>" in out
    assert "<<UNTRUSTED_DATA_END>>" in out
    assert "Some untrusted document content here." in out


def test_wrap_empty_passthrough():
    assert wrap("") == ""


def test_wrap_field_skips_structural_keys():
    payload = {
        "case_id": "5003t000XXXXXXAAAA",
        "score": 0.85,
        "text": "Long form retrieved chunk text here that should be wrapped because it's content",
    }
    out = wrap_field(payload)
    assert out["case_id"] == "5003t000XXXXXXAAAA"  # not wrapped
    assert out["score"] == 0.85  # numeric passthrough
    assert "<<UNTRUSTED_DATA_START>>" in out["text"]


def test_wrap_field_respects_short_strings():
    """Short strings (status names, picklist values) should NOT be wrapped
    — they're noisy and the model sees them everywhere."""
    out = wrap_field({"text": "Closed"})
    assert out["text"] == "Closed"  # not wrapped, len < 40


def test_wrap_field_walks_lists():
    payload = {"hits": [{"text": "a" * 100, "score": 0.9}]}
    out = wrap_field(payload)
    assert "<<UNTRUSTED_DATA_START>>" in out["hits"][0]["text"]


def test_system_prompt_prefix_mentions_markers():
    assert "<<UNTRUSTED_DATA_START>>" in SYSTEM_PROMPT_PREFIX
    assert "<<UNTRUSTED_DATA_END>>" in SYSTEM_PROMPT_PREFIX
