"""Tests for the lifted chunker."""

from __future__ import annotations

from rag.chunking import TokenChunker


def test_short_text_yields_single_chunk():
    chunker = TokenChunker(chunk_size=1000, overlap_size=100)
    chunks = chunker.split("This is a short policy doc.\n\nIt fits in one chunk.")
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert "policy" in chunks[0].text


def test_metadata_propagates_to_each_chunk():
    chunker = TokenChunker(chunk_size=50, overlap_size=10)
    long = "Section A. " * 200  # forces multiple chunks
    chunks = chunker.split(long, base_metadata={"source_uri": "file://test.md", "page_num": 1})
    assert len(chunks) > 1
    for c in chunks:
        assert c.metadata["source_uri"] == "file://test.md"
        assert c.metadata["page_num"] == 1


def test_chunk_indices_are_zero_based_and_monotonic():
    chunker = TokenChunker(chunk_size=80, overlap_size=10)
    long = "\n\n".join(f"Para {i}: " + "word " * 30 for i in range(5))
    chunks = chunker.split(long)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_empty_input_yields_no_chunks():
    chunker = TokenChunker()
    assert chunker.split("") == []
    assert chunker.split("   \n\n   ") == []


def test_paragraph_overflow_falls_back_to_sentences():
    """A single paragraph larger than chunk_size should be split by sentence."""
    chunker = TokenChunker(chunk_size=20, overlap_size=5)
    one_huge_paragraph = (
        "The first sentence here has many words to fill a single chunk. "
        "The second sentence is similarly long and ought to start a new chunk. "
        "The third sentence continues the same paragraph but in another chunk. "
        "Finally the fourth sentence wraps everything up cleanly here."
    )
    chunks = chunker.split(one_huge_paragraph)
    assert len(chunks) >= 2
    # Each chunk should be roughly under chunk_size + overlap_size tokens.
    for c in chunks:
        assert chunker.count_tokens(c.text) <= 60


def test_count_tokens_returns_positive_for_non_empty():
    chunker = TokenChunker()
    assert chunker.count_tokens("hello world") > 0
    assert chunker.count_tokens("") == 0
