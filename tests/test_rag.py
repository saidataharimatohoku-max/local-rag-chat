"""Tests for the RAG pipeline internals (LLM and retrieval are mocked)."""
from types import SimpleNamespace

import pytest

from backend import rag
from backend.config import get_settings


@pytest.fixture
def local_provider(monkeypatch):
    """Force the local provider and reset the cached settings."""
    monkeypatch.setenv("PROVIDER", "local")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _embeddings():
    return SimpleNamespace(
        create=lambda model, input: SimpleNamespace(
            data=[SimpleNamespace(embedding=[1.0, 0.0])]
        )
    )


def _chat_completion(content):
    return SimpleNamespace(
        create=lambda model, messages, temperature: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
    )


def _stream_chunk(text):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
    )


def test_build_messages_includes_context_and_question():
    sources = [rag.Source(title="handbook", content="20 days of vacation")]
    messages = rag._build_messages("How many days?", sources)

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "[handbook]" in messages[1]["content"]
    assert "20 days of vacation" in messages[1]["content"]
    assert "How many days?" in messages[1]["content"]


def test_retrieve_local_uses_vector_store(monkeypatch, local_provider):
    fake_client = SimpleNamespace(embeddings=_embeddings())
    monkeypatch.setattr(rag, "get_llm", lambda: (fake_client, "chat", "embed"))
    monkeypatch.setattr(
        rag.store,
        "search",
        lambda vector, top_k: [{"title": "handbook", "content": "20 days"}],
    )

    sources = rag.retrieve("vacation?")
    assert len(sources) == 1
    assert sources[0].title == "handbook"
    assert sources[0].content == "20 days"


def test_retrieve_without_llm_returns_empty(monkeypatch):
    monkeypatch.setattr(rag, "get_llm", lambda: None)
    assert rag.retrieve("anything") == []


def test_answer_question_grounds_in_sources(monkeypatch, local_provider):
    fake_client = SimpleNamespace(
        embeddings=_embeddings(),
        chat=SimpleNamespace(
            completions=_chat_completion("Full-time staff get 20 days [handbook].")
        ),
    )
    monkeypatch.setattr(rag, "get_llm", lambda: (fake_client, "chat", "embed"))
    monkeypatch.setattr(
        rag.store,
        "search",
        lambda vector, top_k: [{"title": "handbook", "content": "20 days"}],
    )

    answer = rag.answer_question("How many vacation days?")
    assert "20 days" in answer.text
    assert answer.sources[0].title == "handbook"


def test_answer_question_without_llm_returns_message(monkeypatch):
    monkeypatch.setattr(rag, "get_llm", lambda: None)
    answer = rag.answer_question("anything")
    assert "No language model is configured" in answer.text
    assert answer.sources == []


def test_stream_answer_yields_tokens(monkeypatch, local_provider):
    def _create(model, messages, temperature, stream):
        assert stream is True
        return iter([_stream_chunk("Full-time "), _stream_chunk("staff.")])

    fake_client = SimpleNamespace(
        embeddings=_embeddings(),
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create)),
    )
    monkeypatch.setattr(rag, "get_llm", lambda: (fake_client, "chat", "embed"))
    monkeypatch.setattr(
        rag.store,
        "search",
        lambda vector, top_k: [{"title": "handbook", "content": "20 days"}],
    )

    sources, tokens = rag.stream_answer("vacation?")
    assert sources[0].title == "handbook"
    assert "".join(tokens) == "Full-time staff."


def test_stream_answer_skips_empty_choices(monkeypatch, local_provider):
    def _create(model, messages, temperature, stream):
        return iter(
            [
                SimpleNamespace(choices=[]),  # keep-alive chunk with no choices
                _stream_chunk(None),  # delta with no content
                _stream_chunk("Hello"),
            ]
        )

    fake_client = SimpleNamespace(
        embeddings=_embeddings(),
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create)),
    )
    monkeypatch.setattr(rag, "get_llm", lambda: (fake_client, "chat", "embed"))
    monkeypatch.setattr(rag.store, "search", lambda vector, top_k: [])

    _sources, tokens = rag.stream_answer("hi")
    assert "".join(tokens) == "Hello"


def test_stream_answer_without_llm_returns_message(monkeypatch):
    monkeypatch.setattr(rag, "get_llm", lambda: None)
    sources, tokens = rag.stream_answer("anything")
    assert sources == []
    assert "No language model is configured" in "".join(tokens)
