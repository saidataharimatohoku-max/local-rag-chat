"""Tests for the FastAPI endpoints (LLM and ingestion are mocked)."""
import io

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.rag import Answer, Source

client = TestClient(app_module.app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_returns_answer_and_sources(monkeypatch):
    fake = Answer(
        text="Full-time employees get 20 vacation days [handbook].",
        sources=[Source(title="handbook", content="20 days of vacation")],
    )
    monkeypatch.setattr(app_module, "answer_question", lambda q, history: fake)

    response = client.post("/api/chat", json={"question": "How many vacation days?"})
    assert response.status_code == 200
    body = response.json()
    assert "20 vacation days" in body["answer"]
    assert body["sources"][0]["title"] == "handbook"


def test_chat_requires_question():
    response = client.post("/api/chat", json={})
    assert response.status_code == 422


def test_documents_lists_indexed_files(monkeypatch):
    monkeypatch.setattr(
        app_module, "list_documents", lambda: ["handbook.md", "policy.pdf"]
    )

    response = client.get("/api/documents")
    assert response.status_code == 200
    assert response.json() == {"documents": ["handbook.md", "policy.pdf"]}


def test_agent_endpoint_returns_action_and_steps(monkeypatch):
    from backend.agent import AgentResult

    result = AgentResult(
        action="answer",
        text="Full-time staff get 20 days [handbook].",
        sources=[Source(title="handbook", content="20 days of vacation")],
        steps=["Router decided: search", "Answered with retrieved context"],
    )
    monkeypatch.setattr(app_module, "run_agent", lambda q, history: result)

    response = client.post("/api/agent", json={"question": "vacation?"})
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "answer"
    assert "20 days" in body["text"]
    assert body["sources"][0]["title"] == "handbook"
    assert len(body["steps"]) == 2


def test_chat_stream_emits_sources_and_tokens(monkeypatch):
    sources = [Source(title="handbook", content="20 days of vacation")]
    monkeypatch.setattr(
        app_module,
        "stream_answer",
        lambda q, history: (sources, iter(["Full-time ", "employees ", "get 20 days."])),
    )

    response = client.post("/api/chat/stream", json={"question": "vacation?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    body = response.text
    assert "event: sources" in body
    assert "handbook" in body
    assert "event: token" in body
    assert "Full-time " in body
    assert "event: done" in body



def test_upload_indexes_supported_file(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(app_module, "ingest", lambda: 3)

    files = {"file": ("note.txt", io.BytesIO(b"hello world"), "text/plain")}
    response = client.post("/api/upload", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "note.txt"
    assert body["chunks"] == 3
    assert (tmp_path / "note.txt").exists()


def test_chat_accepts_conversation_history(monkeypatch):
    """Test that /api/chat accepts and passes conversation history."""
    received_history = []

    def capture_history(q, history):
        received_history.extend(history)
        return Answer(text="Follow-up answer", sources=[])

    monkeypatch.setattr(app_module, "answer_question", capture_history)

    response = client.post(
        "/api/chat",
        json={
            "question": "What about cost?",
            "history": [
                {"role": "user", "content": "Tell me about the product"},
                {"role": "assistant", "content": "It's a great product"}
            ]
        }
    )
    assert response.status_code == 200
    assert len(received_history) == 2
    assert received_history[0] == ("user", "Tell me about the product")
    assert received_history[1] == ("assistant", "It's a great product")


def test_chat_backward_compatible_without_history(monkeypatch):
    """Test that requests without history still work (backward compatibility)."""
    fake = Answer(text="Answer without history", sources=[])
    monkeypatch.setattr(app_module, "answer_question", lambda q, history: fake)

    response = client.post("/api/chat", json={"question": "Simple question?"})
    assert response.status_code == 200
    assert response.json()["answer"] == "Answer without history"


def test_chat_rejects_excessive_history():
    """Test that history is limited to 20 messages."""
    history = [{"role": "user", "content": f"turn {i}"} for i in range(21)]
    response = client.post(
        "/api/chat",
        json={"question": "test", "history": history}
    )
    assert response.status_code == 422
    assert "history" in response.text.lower()


def test_agent_accepts_conversation_history(monkeypatch):
    """Test that /api/agent accepts and passes conversation history."""
    from backend.agent import AgentResult

    received_history = []

    def capture_history(q, history):
        received_history.extend(history)
        return AgentResult(action="answer", text="Agent answer", sources=[], steps=[])

    monkeypatch.setattr(app_module, "run_agent", capture_history)

    response = client.post(
        "/api/agent",
        json={
            "question": "follow-up?",
            "history": [{"role": "user", "content": "first question"}]
        }
    )
    assert response.status_code == 200
    assert len(received_history) == 1
    assert received_history[0] == ("user", "first question")


def test_stream_accepts_conversation_history(monkeypatch):
    """Test that /api/chat/stream accepts and passes conversation history."""
    received_history = []

    def capture_stream(q, history):
        received_history.extend(history)
        return [], iter(["token"])

    monkeypatch.setattr(app_module, "stream_answer", capture_stream)

    response = client.post(
        "/api/chat/stream",
        json={
            "question": "follow-up?",
            "history": [{"role": "user", "content": "prior question"}]
        }
    )
    assert response.status_code == 200
    assert len(received_history) == 1
    assert received_history[0] == ("user", "prior question")


def test_upload_rejects_unsupported_type(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path))
    # ingest should never be reached for an invalid type.
    monkeypatch.setattr(
        app_module, "ingest", lambda: pytest.fail("ingest should not run")
    )

    files = {"file": ("data.csv", io.BytesIO(b"a,b,c"), "text/csv")}
    response = client.post("/api/upload", files=files)

    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_upload_sanitizes_path_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(app_module, "ingest", lambda: 1)

    files = {"file": ("../evil.txt", io.BytesIO(b"x"), "text/plain")}
    response = client.post("/api/upload", files=files)

    assert response.status_code == 200
    # The file is written inside DATA_DIR, not the parent directory.
    assert (tmp_path / "evil.txt").exists()
    assert not (tmp_path.parent / "evil.txt").exists()
