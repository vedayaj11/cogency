"""Tests for the CDC payload → CaseRepository row mapper.

We exercise the mapper directly without spinning up gRPC; the consumer's
`subscribe()` is mocked elsewhere. These tests confirm:
- CREATE payloads route to a row dict matching CaseRepository's input shape.
- DELETE payloads set IsDeleted=true.
- GAP_* payloads are dropped (returns None).
- Missing recordIds drops the event.
"""

from __future__ import annotations

from worker.activities.cdc import _cdc_to_case_row


def test_create_event_yields_full_row():
    payload = {
        "ChangeEventHeader": {
            "changeType": "CREATE",
            "recordIds": ["5003t000XXXXXXAAA"],
            "changeOrigin": "client=Web",
        },
        "CaseNumber": "00001234",
        "Subject": "Need help",
        "Status": "New",
        "Priority": "Medium",
        "Origin": "Email",
        "ContactId": "0033t000XXXXXXC0AAA",
        "AccountId": "0013t000XXXXXXA0AAA",
        "OwnerId": "005000000000001AAA",
    }
    row = _cdc_to_case_row(payload)
    assert row is not None
    assert row["Id"] == "5003t000XXXXXXAAA"
    assert row["CaseNumber"] == "00001234"
    assert row["Status"] == "New"
    assert row["IsDeleted"] is False


def test_delete_event_marks_is_deleted():
    payload = {
        "ChangeEventHeader": {
            "changeType": "DELETE",
            "recordIds": ["5003t000XXXXXXAAA"],
        },
    }
    row = _cdc_to_case_row(payload)
    assert row is not None
    assert row["IsDeleted"] is True


def test_gap_event_is_dropped():
    payload = {
        "ChangeEventHeader": {
            "changeType": "GAP_OVERFLOW",
            "recordIds": ["5003t000XXXXXXAAA"],
        },
    }
    assert _cdc_to_case_row(payload) is None


def test_event_without_record_ids_is_dropped():
    assert (
        _cdc_to_case_row({"ChangeEventHeader": {"changeType": "CREATE", "recordIds": []}})
        is None
    )


def test_partial_update_drops_none_fields():
    """If CDC only carries the changed fields, we should not blat existing
    rows by sending None for everything else."""
    payload = {
        "ChangeEventHeader": {
            "changeType": "UPDATE",
            "recordIds": ["5003t000XXXXXXAAA"],
        },
        "Status": "Working",
    }
    row = _cdc_to_case_row(payload)
    assert row is not None
    assert "Status" in row and row["Status"] == "Working"
    assert "Subject" not in row  # the mapper filters None out
    assert "Description" not in row
