"""Tests for the on-disk vector store (save/load and cosine search)."""
import json

import pytest

from backend import store
from backend.config import get_settings


@pytest.fixture
def temp_index(tmp_path, monkeypatch):
    """Point the store at a temporary index file."""
    index_path = tmp_path / "index.json"
    monkeypatch.setenv("LOCAL_INDEX_PATH", str(index_path))
    get_settings.cache_clear()
    yield index_path
    get_settings.cache_clear()


def _record(rec_id, title, embedding):
    return {"id": rec_id, "title": title, "content": f"content {rec_id}", "embedding": embedding}


def test_save_and_load_roundtrip(temp_index):
    records = [_record("1", "a", [1.0, 0.0]), _record("2", "b", [0.0, 1.0])]
    store.save_index(records)
    assert temp_index.exists()
    loaded = store.load_index()
    assert loaded == records


def test_load_missing_index_returns_empty(temp_index):
    assert store.load_index() == []


def test_search_returns_most_similar_first(temp_index):
    records = [
        _record("x", "x-axis", [1.0, 0.0]),
        _record("y", "y-axis", [0.0, 1.0]),
        _record("diag", "diagonal", [0.7, 0.7]),
    ]
    store.save_index(records)
    results = store.search([1.0, 0.0], top_k=2)
    assert results[0]["id"] == "x"
    assert len(results) == 2


def test_search_empty_index_returns_empty(temp_index):
    assert store.search([1.0, 0.0], top_k=3) == []


def test_search_handles_zero_vectors(temp_index):
    store.save_index([_record("z", "zero", [0.0, 0.0])])
    # Should not raise a divide-by-zero error.
    results = store.search([0.0, 0.0], top_k=1)
    assert len(results) == 1
