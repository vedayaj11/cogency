"""Bulk 2.0 result CSV parsing helpers.

The actual job lifecycle (submit, poll, fetch, delete) lives on
SalesforceClient. This module decodes the streaming CSV chunks into typed
dicts that downstream repositories can apply to the local mirror.
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator, Iterator
from typing import Any


def parse_csv_chunk(chunk: bytes, *, header_only_first: bool = True) -> Iterator[dict[str, Any]]:
    """Parse one CSV chunk from Bulk 2.0 results.

    Bulk 2.0 emits the header row in every chunk; the caller decides whether
    to keep it (first chunk) or skip (subsequent chunks).
    """
    text = chunk.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        yield {k: (v if v != "" else None) for k, v in row.items()}


async def parse_csv_stream(
    chunks: AsyncIterator[bytes],
) -> AsyncIterator[dict[str, Any]]:
    """Flatten a chunked CSV stream into a stream of row dicts."""
    first = True
    async for chunk in chunks:
        # Each chunk is itself a complete CSV with header; DictReader handles dedup.
        for row in parse_csv_chunk(chunk):
            yield row
        first = False  # noqa: F841 — kept for clarity if we switch to header-stripping later
