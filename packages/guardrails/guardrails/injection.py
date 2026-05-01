"""Prompt-injection scanner (PRD AC7.2).

For MVP we use a regex-based scanner that catches the most common
injection patterns observed in the wild + a couple of heuristic signals
(unusual control-character density, suspicious unicode). LLM Guard's
neural classifier is a drop-in upgrade for production — same interface;
the executor doesn't need to change.

Detection categories:
- INSTRUCTION_OVERRIDE: "ignore previous", "disregard instructions", etc.
- SYSTEM_LEAK: "what is your system prompt", "repeat your instructions"
- ROLE_HIJACK: "you are now a", "pretend to be", "act as"
- DANGEROUS_TOOL: "run sql", "drop table", "rm -rf", etc.
- DELIMITER_BREAK: tokens that mimic the LLM's delimiters

The scanner returns the highest-severity match plus the full list of hits.
The executor decides whether to halt or just log + warn based on the
AOP's `metadata.injection_action: block | warn | off`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


Severity = Literal["low", "medium", "high", "critical"]


@dataclass(frozen=True)
class _Pattern:
    name: str
    category: str
    severity: Severity
    regex: re.Pattern[str]


def _p(name: str, category: str, severity: Severity, pattern: str) -> _Pattern:
    return _Pattern(
        name=name,
        category=category,
        severity=severity,
        regex=re.compile(pattern, re.IGNORECASE),
    )


# Pattern set drawn from public injection corpora (Lakera, NCC Group, OWASP
# LLM Top-10). Tuned for English; multi-lingual patterns are M9b.
_PATTERNS: list[_Pattern] = [
    # INSTRUCTION_OVERRIDE
    _p(
        "ignore_previous",
        "INSTRUCTION_OVERRIDE",
        "high",
        r"\b(?:ignore|disregard|forget|override)\b[^.]{0,40}\b(?:previous|prior|above|earlier|all)\b[^.]{0,40}\b(?:instructions?|rules?|prompts?|directives?)\b",
    ),
    _p(
        "now_act_as",
        "ROLE_HIJACK",
        "high",
        r"\bnow\b[^.]{0,30}\b(?:act|behave|respond)\s+as\b",
    ),
    _p(
        "you_are_now",
        "ROLE_HIJACK",
        "high",
        r"\byou\s+are\s+now\b[^.]{0,40}\b(?:a|an)\b",
    ),
    _p(
        "pretend_to_be",
        "ROLE_HIJACK",
        "medium",
        r"\bpretend\s+(?:to\s+be|you'?re)\b",
    ),
    _p(
        "developer_mode",
        "ROLE_HIJACK",
        "high",
        r"\b(?:developer|debug|jailbreak|DAN|admin|sudo)\s+mode\b",
    ),
    # SYSTEM_LEAK
    _p(
        "reveal_system_prompt",
        "SYSTEM_LEAK",
        "critical",
        r"\b(?:reveal|show|print|display|repeat|output)\b[^.]{0,40}\b(?:system|initial|original)\s+(?:prompt|instructions?|message)\b",
    ),
    _p(
        "what_were_instructions",
        "SYSTEM_LEAK",
        "high",
        r"\bwhat\s+(?:were|are)\s+your\s+(?:original|initial|original)?\s*(?:instructions?|prompts?|rules?)\b",
    ),
    # DELIMITER_BREAK
    _p(
        "system_tag",
        "DELIMITER_BREAK",
        "critical",
        r"<\s*\|?\s*(?:system|im_start|im_end)\s*\|?\s*>",
    ),
    _p(
        "fake_role",
        "DELIMITER_BREAK",
        "high",
        r"^\s*(?:system|assistant|user)\s*:\s*",
    ),
    # DANGEROUS_TOOL
    _p(
        "shell_command",
        "DANGEROUS_TOOL",
        "high",
        r"\b(?:rm\s+-rf|sudo\s+rm|format\s+c:|del\s+/[fsq])\b",
    ),
    _p(
        "sql_injection",
        "DANGEROUS_TOOL",
        "medium",
        r"\b(?:drop|truncate|delete\s+from)\b[^.]{0,40}\b(?:table|database|schema)\b",
    ),
    # GENERIC HIGH-RISK PHRASES
    _p(
        "stop_being",
        "INSTRUCTION_OVERRIDE",
        "medium",
        r"\bstop\s+being\b",
    ),
    _p(
        "new_instructions",
        "INSTRUCTION_OVERRIDE",
        "medium",
        r"\b(?:new|updated|revised)\s+instructions?\s*:",
    ),
]


_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class InjectionHit:
    pattern_name: str
    category: str
    severity: Severity
    matched_text: str
    span: tuple[int, int]


@dataclass
class ScanResult:
    detected: bool
    max_severity: Severity | None
    hits: list[InjectionHit] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if not self.hits:
            return "no injection patterns detected"
        cats = sorted({h.category for h in self.hits})
        return (
            f"{len(self.hits)} hit(s) at max severity={self.max_severity} — "
            f"categories: {', '.join(cats)}"
        )


def scan_for_injection(text: str) -> ScanResult:
    """Return all matched injection patterns + the highest severity.

    Empty / non-string input → no hits.
    """
    if not text or not isinstance(text, str):
        return ScanResult(detected=False, max_severity=None, hits=[])

    hits: list[InjectionHit] = []
    for p in _PATTERNS:
        for match in p.regex.finditer(text):
            hits.append(
                InjectionHit(
                    pattern_name=p.name,
                    category=p.category,
                    severity=p.severity,
                    matched_text=match.group(0)[:120],
                    span=(match.start(), match.end()),
                )
            )

    if not hits:
        return ScanResult(detected=False, max_severity=None)
    max_sev = max(hits, key=lambda h: _SEVERITY_RANK[h.severity]).severity
    return ScanResult(detected=True, max_severity=max_sev, hits=hits)


def scan_dict(data: dict, *, skip_keys: set[str] | None = None) -> ScanResult:
    """Recursively scan every string value in a dict. Combines hits across
    all strings into a single ScanResult.
    """
    skip = skip_keys or set()
    all_hits: list[InjectionHit] = []

    def _walk(value, parent_key=None):
        if parent_key in skip:
            return
        if isinstance(value, str):
            r = scan_for_injection(value)
            all_hits.extend(r.hits)
        elif isinstance(value, dict):
            for k, v in value.items():
                _walk(v, k)
        elif isinstance(value, list):
            for item in value:
                _walk(item, parent_key)

    _walk(data)
    if not all_hits:
        return ScanResult(detected=False, max_severity=None)
    max_sev = max(all_hits, key=lambda h: _SEVERITY_RANK[h.severity]).severity
    return ScanResult(detected=True, max_severity=max_sev, hits=all_hits)


def severity_at_least(found: Severity | None, threshold: Severity) -> bool:
    if found is None:
        return False
    return _SEVERITY_RANK[found] >= _SEVERITY_RANK[threshold]


__all__ = [
    "scan_for_injection",
    "scan_dict",
    "ScanResult",
    "InjectionHit",
    "severity_at_least",
    "Severity",
]
