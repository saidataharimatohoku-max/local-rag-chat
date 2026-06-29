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
    messages = rag._build_messages("How many days?", sources, history=[])

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


def test_build_messages_with_history():
    """Test that conversation history is included in messages."""
    sources = [rag.Source(title="handbook", content="20 days")]
    history = [("user", "What is the product?"), ("assistant", "It's a widget")]
    messages = rag._build_messages("What about cost?", sources, history=history)

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "What is the product?"
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "It's a widget"
    assert messages[3]["role"] == "user"
    assert "What about cost?" in messages[3]["content"]
    assert "[handbook]" in messages[3]["content"]


def test_condense_question_without_history():
    """Test that condensation returns original question when no history."""
    result = rag.condense_question("What is the price?", history=[])
    assert result == "What is the price?"


def test_condense_question_without_llm(monkeypatch):
    """Test that condensation degrades gracefully when no LLM configured."""
    monkeypatch.setattr(rag, "get_llm", lambda: None)
    result = rag.condense_question(
        "What about its cost?",
        history=[("user", "Tell me about the product")]
    )
    assert result == "What about its cost?"


def test_condense_question_with_history(monkeypatch, local_provider):
    """Test that condensation creates a standalone query from history."""
    def _create(model, messages, temperature):
        # Verify history is included in messages
        assert len(messages) >= 3
        assert messages[1]["content"] == "Tell me about the product"
        assert messages[2]["content"] == "What about its cost?"
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content="What is the product's cost?"
            ))]
        )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )
    monkeypatch.setattr(rag, "get_llm", lambda: (fake_client, "chat", "embed"))

    result = rag.condense_question(
        "What about its cost?",
        history=[("user", "Tell me about the product")]
    )
    assert result == "What is the product's cost?"


def test_condense_question_handles_errors(monkeypatch, local_provider):
    """Test that condensation falls back to original on error."""
    def _create(model, messages, temperature):
        raise Exception("LLM error")

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )
    monkeypatch.setattr(rag, "get_llm", lambda: (fake_client, "chat", "embed"))

    result = rag.condense_question("follow-up?", history=[("user", "prior")])
    assert result == "follow-up?"


def test_retrieve_with_history_condenses_query(monkeypatch, local_provider):
    """Test that retrieve uses condensed query when history is provided."""
    condensed_queries = []

    def capture_condense(question, history):
        condensed_queries.append((question, len(history)))
        return "standalone query"

    fake_client = SimpleNamespace(embeddings=_embeddings())
    monkeypatch.setattr(rag, "get_llm", lambda: (fake_client, "chat", "embed"))
    monkeypatch.setattr(rag, "condense_question", capture_condense)
    monkeypatch.setattr(rag.store, "search", lambda vector, top_k: [])

    history = [("user", "first"), ("assistant", "response")]
    rag.retrieve("follow-up?", history=history)

    assert len(condensed_queries) == 1
    assert condensed_queries[0] == ("follow-up?", 2)


def test_answer_question_with_history(monkeypatch, local_provider):
    """Test that answer_question passes history to retrieve and build_messages."""
    retrieve_history = []
    build_messages_history = []

    def capture_retrieve(question, history):
        retrieve_history.append(history)
        return []

    def capture_build(question, sources, history):
        build_messages_history.append(history)
        return [{"role": "system", "content": "test"}]

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=_chat_completion("answer"))
    )
    monkeypatch.setattr(rag, "get_llm", lambda: (fake_client, "chat", "embed"))
    monkeypatch.setattr(rag, "retrieve", capture_retrieve)
    monkeypatch.setattr(rag, "_build_messages", capture_build)

    history = [("user", "hi")]
    rag.answer_question("follow-up", history=history)

    assert retrieve_history[0] == history
    assert build_messages_history[0] == history
