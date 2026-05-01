"""PII redaction + restoration tests.

These tests instantiate Presidio (~5s spaCy load on first call). We use
the process-global redactor so the cost is amortized across the suite.
"""

from __future__ import annotations

import pytest

from guardrails.pii import get_redactor, restore


@pytest.fixture(scope="module")
def redactor():
    return get_redactor()


def test_email_redaction(redactor):
    r = redactor.redact("Contact aisha.patel@example.com about the refund.")
    assert "aisha.patel@example.com" not in r.redacted_text
    assert "EMAIL_ADDRESS" in r.redacted_text
    # Restoration map should be able to recover the original
    restored = restore(r.redacted_text, r.restoration_map)
    assert "aisha.patel@example.com" in restored


def test_no_pii_passthrough(redactor):
    text = "The case is about a duplicate $45 charge."
    r = redactor.redact(text)
    # No emails, names, or phones; redacted text should be effectively the
    # same (might still flag $45 as something occasionally — that's fine).
    assert "$45" in r.redacted_text


def test_salesforce_case_id_recognizer(redactor):
    r = redactor.redact("See case 5003t000XXXXXX01AAA for details.")
    assert "SF_CASE_ID" in r.redacted_text
    assert "5003t000XXXXXX01AAA" not in r.redacted_text
    restored = restore(r.redacted_text, r.restoration_map)
    assert "5003t000XXXXXX01AAA" in restored


def test_redact_dict_skips_specified_keys(redactor):
    payload = {
        "case_id": "5003t000XXXXXX01AAA",  # should pass through
        "description": "Email aisha.patel@example.com about it.",
    }
    out, mapping = redactor.redact_dict(payload, skip_keys={"case_id"})
    assert out["case_id"] == "5003t000XXXXXX01AAA"
    assert "aisha.patel@example.com" not in out["description"]
    assert mapping  # at least one restoration entry


def test_redact_dict_walks_nested(redactor):
    payload = {
        "outer": {
            "note": "Ping marcus.chen@orbital.example",
            "score": 0.5,
        }
    }
    out, mapping = redactor.redact_dict(payload)
    assert "marcus.chen@orbital.example" not in out["outer"]["note"]
    assert out["outer"]["score"] == 0.5  # numeric untouched


def test_restore_with_empty_map_is_passthrough():
    assert restore("nothing to restore", {}) == "nothing to restore"
    assert restore("", {"<X>": "y"}) == ""


def test_redact_empty_text(redactor):
    r = redactor.redact("")
    assert r.redacted_text == ""
    assert r.restoration_map == {}
