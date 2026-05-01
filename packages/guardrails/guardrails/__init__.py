"""Guardrails layer.

PRD §6.7: PII redaction (Presidio), prompt-injection defense (LLM Guard),
citation enforcement, action-scope permissions, cost/token kill switch.

Layout:
- pii.py        Presidio + custom Salesforce-ID recognizers; tokenize-and-
                restore so legitimate write-back tools can recover real values.
- injection.py  Regex-based prompt-injection scanner (LLM Guard upgrade slot).
- spotlight.py  Wrap untrusted data with <<UNTRUSTED_DATA_*>> markers.
- citations.py  Citation extraction (existing, used by the executor).
"""

from guardrails.injection import (
    InjectionHit,
    ScanResult,
    scan_dict,
    scan_for_injection,
    severity_at_least,
)
from guardrails.pii import RedactionResult, Redactor, get_redactor, restore
from guardrails.spotlight import SYSTEM_PROMPT_PREFIX, wrap, wrap_field

__all__ = [
    # PII
    "Redactor",
    "RedactionResult",
    "get_redactor",
    "restore",
    # Injection
    "scan_for_injection",
    "scan_dict",
    "ScanResult",
    "InjectionHit",
    "severity_at_least",
    # Spotlight
    "wrap",
    "wrap_field",
    "SYSTEM_PROMPT_PREFIX",
]
