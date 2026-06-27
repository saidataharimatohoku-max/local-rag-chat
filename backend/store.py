"""Simple on-disk vector store for local (Ollama) retrieval.

Stores document chunks and their embeddings as JSON and performs cosine
similarity search with NumPy. Used when running without Azure AI Search.
"""
from __future__ import annotations

import json
import os

import numpy as np

from .config import get_settings


def _index_path() -> str:
    return get_settings().local_index_path


def save_index(records: list[dict]) -> None:
    """Persist records (id, title, content, embedding) to disk."""
    path = _index_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(records, handle)


def load_index() -> list[dict]:
    path = _index_path()
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def search(query_embedding: list[float], top_k: int) -> list[dict]:
    """Return the top_k records most similar to the query embedding."""
    records = load_index()
    if not records:
        return []

    matrix = np.asarray([r["embedding"] for r in records], dtype=float)
    query = np.asarray(query_embedding, dtype=float)

    denom = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
    denom[denom == 0] = 1e-9
    similarities = matrix @ query / denom

    order = np.argsort(similarities)[::-1][:top_k]
    return [records[i] for i in order]
