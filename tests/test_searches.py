"""Tests for searches.py — no browser required."""

import pytest
from searches import get_random_query, get_random_queries, ALL_QUERIES, QUERIES


def test_all_queries_non_empty():
    assert len(ALL_QUERIES) > 0


def test_all_queries_are_strings():
    for q in ALL_QUERIES:
        assert isinstance(q, str) and q.strip(), f"Empty or non-string query: {q!r}"


def test_categories_present():
    expected = {"noticias", "deportes", "tecnología", "cultura"}
    assert expected.issubset(set(QUERIES.keys()))


def test_get_random_query_returns_known_query():
    result = get_random_query()
    assert result in ALL_QUERIES


def test_get_random_queries_count():
    for n in (1, 10, 30, 40):
        queries = get_random_queries(n)
        assert len(queries) == n, f"Expected {n} queries, got {len(queries)}"


def test_get_random_queries_are_strings():
    for q in get_random_queries(15):
        assert isinstance(q, str) and q.strip()


def test_get_random_queries_varied_topics():
    """With 40 queries we should see terms from at least 3 different categories."""
    queries = set(get_random_queries(40))
    categories_seen = 0
    for category_queries in QUERIES.values():
        if queries.intersection(category_queries):
            categories_seen += 1
    assert categories_seen >= 3, (
        f"Expected queries from ≥3 categories, got {categories_seen}"
    )
