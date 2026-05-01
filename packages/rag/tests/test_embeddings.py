"""Tests for cosine similarity helper."""

from __future__ import annotations

import math

from rag.embeddings import cosine_similarity


def test_identical_vectors_score_one():
    a = [0.1, 0.2, 0.3, 0.4]
    assert math.isclose(cosine_similarity(a, a), 1.0, rel_tol=1e-9)


def test_orthogonal_vectors_score_zero():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert cosine_similarity(a, b) == 0.0


def test_opposite_vectors_score_negative_one():
    a = [1.0, 2.0, 3.0]
    b = [-1.0, -2.0, -3.0]
    assert math.isclose(cosine_similarity(a, b), -1.0, rel_tol=1e-9)


def test_empty_or_mismatched_returns_zero():
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], []) == 0.0
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0


def test_zero_vector_returns_zero():
    assert cosine_similarity([0.0, 0.0, 0.0], [1.0, 1.0, 1.0]) == 0.0
