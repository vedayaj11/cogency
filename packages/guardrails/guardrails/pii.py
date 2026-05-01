"""PII redaction + restoration (PRD AC7.1).

Wraps Microsoft Presidio with two cogency-specific concerns:

1. **Salesforce ID recognizers.** Stock Presidio doesn't detect SF Object Ids
   (15- or 18-char alphanumeric prefixed by 003, 005, 5003, 0033, 0013,
   etc.). We add custom recognizers for the prefixes our agents touch.

2. **Tokenize-and-restore.** Each detected entity is replaced with
   `<TYPE_idx>` (e.g. `<EMAIL_ADDRESS_0>`). The mapping is returned
   alongside so legitimate field writes (e.g. `add_case_comment` with the
   real customer email) can restore originals before hitting Salesforce.
   The redacted text is what the LLM sees — never the original PII.

The Presidio engine is heavy to construct (~5s; spaCy model load) so
`get_redactor()` caches a process-global instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider


# Salesforce object ID prefixes we care about.
# Format: 15 or 18 alphanumeric chars, first 3 = object key prefix.
# Reference: https://help.salesforce.com/s/articleView?id=000385203
_SF_OBJECT_PREFIXES = {
    "003": "SF_CONTACT_ID",
    "0033": "SF_CONTACT_ID",  # extended
    "005": "SF_USER_ID",
    "0053": "SF_USER_ID",
    "001": "SF_ACCOUNT_ID",
    "0013": "SF_ACCOUNT_ID",
    "500": "SF_CASE_ID",
    "5003": "SF_CASE_ID",
    "00G": "SF_QUEUE_ID",
    "0WO": "SF_TASK_ID",
}


def _sf_id_recognizer(prefix: str, entity: str) -> PatternRecognizer:
    """One recognizer per prefix — Presidio can't dispatch on prefix in a
    single pattern, so we register one per known prefix."""
    pattern = Pattern(
        name=f"sf_id_{prefix}",
        regex=rf"\b{prefix}[A-Za-z0-9]{{12,15}}\b",
        score=0.85,
    )
    return PatternRecognizer(
        supported_entity=entity,
        patterns=[pattern],
        name=f"SfIdRecognizer_{prefix}",
    )


def _permissive_email_recognizer() -> PatternRecognizer:
    """Catch RFC 2606 reserved TLDs (.example, .test, .invalid) that
    Presidio's stock EMAIL_ADDRESS recognizer rejects. Score 0.95 so it
    beats URL (0.5) without overshadowing the strict EMAIL_ADDRESS (1.0)."""
    pattern = Pattern(
        name="permissive_email",
        regex=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        score=0.95,
    )
    return PatternRecognizer(
        supported_entity="EMAIL_ADDRESS",
        patterns=[pattern],
        name="PermissiveEmailRecognizer",
    )


@dataclass
class RedactionResult:
    redacted_text: str
    restoration_map: dict[str, str] = field(default_factory=dict)
    found_entities: list[dict[str, Any]] = field(default_factory=list)


class Redactor:
    """Process-global redactor — instantiated once via get_redactor()."""

    def __init__(self) -> None:
        # Use the small spaCy model for speed; Presidio's default is `lg`
        # which is 380 MB. The small model is sufficient for PERSON / EMAIL
        # / PHONE detection at MVP latency targets.
        provider = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
            }
        )
        self._analyzer = AnalyzerEngine(nlp_engine=provider.create_engine())
        # Register a permissive email recognizer to catch reserved TLDs
        # (.example/.test/.invalid) that Presidio's stock recognizer skips.
        self._analyzer.registry.add_recognizer(_permissive_email_recognizer())
        # Register SF ID recognizers — one per prefix.
        for prefix, entity in _SF_OBJECT_PREFIXES.items():
            self._analyzer.registry.add_recognizer(_sf_id_recognizer(prefix, entity))

    def redact(
        self,
        text: str,
        *,
        entities: list[str] | None = None,
        score_threshold: float = 0.4,
    ) -> RedactionResult:
        """Redact PII from `text` and return a restoration map.

        Presidio frequently returns overlapping detections for the same
        span (e.g. EMAIL_ADDRESS + URL both match `foo@bar.com`). We keep
        only non-overlapping entities, preferring (a) higher confidence,
        then (b) longer span — that picks EMAIL over the partial URLs.
        """
        if not text:
            return RedactionResult(redacted_text=text)

        raw = self._analyzer.analyze(
            text=text,
            language="en",
            entities=entities,
            score_threshold=score_threshold,
        )
        # Greedy conflict resolution: sort by (-score, -length, start) and
        # accept a detection only if its span doesn't overlap an already-
        # accepted one. The highest-score detection wins each region.
        raw.sort(
            key=lambda r: (-r.score, -(r.end - r.start), r.start)
        )
        accepted: list[Any] = []
        for r in raw:
            if any(not (r.end <= a.start or r.start >= a.end) for a in accepted):
                continue
            accepted.append(r)

        # Stable per-type indexing in document order.
        accepted.sort(key=lambda r: r.start)
        type_counters: dict[str, int] = {}
        index_map: dict[tuple[int, int, str], int] = {}
        found: list[dict[str, Any]] = []
        for r in accepted:
            type_counters.setdefault(r.entity_type, -1)
            type_counters[r.entity_type] += 1
            index_map[(r.start, r.end, r.entity_type)] = type_counters[r.entity_type]
            found.append(
                {
                    "type": r.entity_type,
                    "start": r.start,
                    "end": r.end,
                    "score": r.score,
                }
            )

        # Splice in reverse so offsets stay valid.
        redacted = text
        restoration: dict[str, str] = {}
        for r in sorted(accepted, key=lambda r: r.start, reverse=True):
            idx = index_map[(r.start, r.end, r.entity_type)]
            placeholder = f"<{r.entity_type}_{idx}>"
            restoration[placeholder] = text[r.start : r.end]
            redacted = redacted[: r.start] + placeholder + redacted[r.end :]

        return RedactionResult(
            redacted_text=redacted, restoration_map=restoration, found_entities=found
        )

    def redact_dict(
        self,
        data: dict[str, Any],
        *,
        skip_keys: set[str] | None = None,
        score_threshold: float = 0.4,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Recursively redact every string value in a dict. Returns
        `(redacted_dict, merged_restoration_map)`.

        `skip_keys` lets callers opt out of redacting specific fields by
        name (e.g. case IDs we want to keep visible to the agent).
        """
        skip = skip_keys or set()
        merged: dict[str, str] = {}

        def _walk(value: Any, parent_key: str | None = None) -> Any:
            if parent_key in skip:
                return value
            if isinstance(value, str):
                result = self.redact(value, score_threshold=score_threshold)
                merged.update(result.restoration_map)
                return result.redacted_text
            if isinstance(value, dict):
                return {k: _walk(v, k) for k, v in value.items()}
            if isinstance(value, list):
                return [_walk(item, parent_key) for item in value]
            return value

        return _walk(data), merged


def restore(text: str, restoration_map: dict[str, str]) -> str:
    """Replace `<TYPE_idx>` placeholders with original values.

    Used by tools that write back to Salesforce — the LLM sees redacted
    placeholders, but the actual write needs the real value.
    """
    if not restoration_map or not text:
        return text
    out = text
    for placeholder, original in restoration_map.items():
        out = out.replace(placeholder, original)
    return out


@lru_cache(maxsize=1)
def get_redactor() -> Redactor:
    """Process-global redactor. First call constructs Presidio (~5s)."""
    return Redactor()


__all__ = ["Redactor", "RedactionResult", "get_redactor", "restore"]
