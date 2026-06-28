"""Tests for the word-based text chunking helper."""
from backend.ingest import CHUNK_OVERLAP, CHUNK_SIZE, chunk_text


def test_short_text_is_a_single_chunk():
    chunks = list(chunk_text("hello world"))
    assert chunks == ["hello world"]


def test_empty_text_yields_no_chunks():
    assert list(chunk_text("")) == []
    assert list(chunk_text("   ")) == []


def test_long_text_is_split_into_multiple_chunks():
    words = " ".join(f"w{i}" for i in range(CHUNK_SIZE * 2))
    chunks = list(chunk_text(words))
    assert len(chunks) >= 2
    # Every chunk has at most CHUNK_SIZE words.
    assert all(len(c.split()) <= CHUNK_SIZE for c in chunks)


def test_chunks_overlap():
    words = " ".join(f"w{i}" for i in range(CHUNK_SIZE + 50))
    chunks = list(chunk_text(words))
    assert len(chunks) == 2
    first_tail = chunks[0].split()[-CHUNK_OVERLAP:]
    second_head = chunks[1].split()[:CHUNK_OVERLAP]
    assert first_tail == second_head
