"""Tests for the agentic RAG layer (LLM and retrieval are mocked)."""
import pytest

from backend import agent
from backend.rag import Source


# --- helper unit tests -----------------------------------------------------


def test_parse_json_extracts_object():
    assert agent._parse_json('noise {"action": "search"} trailing') == {
        "action": "search"
    }


def test_parse_json_invalid_returns_empty():
    assert agent._parse_json("no json here") == {}


def test_route_parses_action(monkeypatch):
    monkeypatch.setattr(
        agent,
        "_chat",
        lambda messages, temperature=0.0: '{"action": "search", "detail": "vacation"}',
    )
    action, detail = agent._route("How many vacation days?")
    assert action == "search"
    assert detail == "vacation"


def test_route_defaults_to_search_on_garbage(monkeypatch):
    monkeypatch.setattr(agent, "_chat", lambda messages, temperature=0.0: "not json")
    action, detail = agent._route("something")
    assert action == "search"
    assert detail == "something"


def test_is_sufficient_true(monkeypatch):
    monkeypatch.setattr(
        agent, "_chat", lambda messages, temperature=0.0: '{"sufficient": true}'
    )
    assert agent._is_sufficient("q", [Source("t", "c")]) is True


def test_is_sufficient_empty_sources_short_circuits(monkeypatch):
    monkeypatch.setattr(
        agent, "_chat", lambda *a, **k: pytest.fail("should not call the model")
    )
    assert agent._is_sufficient("q", []) is False


# --- orchestration tests ---------------------------------------------------


def test_agent_without_llm_returns_message(monkeypatch):
    monkeypatch.setattr(agent, "get_llm", lambda: None)
    result = agent.run_agent("anything")
    assert result.action == "answer"
    assert "No language model is configured" in result.text


def test_agent_clarify_path(monkeypatch):
    monkeypatch.setattr(agent, "get_llm", lambda: ("c", "m", "e"))
    monkeypatch.setattr(agent, "_route", lambda q: ("clarify", "Which leave type?"))

    result = agent.run_agent("leave?")
    assert result.action == "clarify"
    assert "Which leave type?" in result.text
    assert result.sources == []


def test_agent_answers_directly(monkeypatch):
    monkeypatch.setattr(agent, "get_llm", lambda: ("c", "m", "e"))
    monkeypatch.setattr(agent, "_route", lambda q: ("answer", ""))
    monkeypatch.setattr(agent, "_answer", lambda q, s: "Hello!")

    result = agent.run_agent("hi")
    assert result.action == "answer"
    assert result.text == "Hello!"
    assert result.sources == []


def test_agent_search_sufficient_no_retry(monkeypatch):
    monkeypatch.setattr(agent, "get_llm", lambda: ("c", "m", "e"))
    monkeypatch.setattr(agent, "_route", lambda q: ("search", "vacation policy"))
    monkeypatch.setattr(agent, "retrieve", lambda q: [Source("handbook", "20 days")])
    monkeypatch.setattr(agent, "_is_sufficient", lambda q, s: True)
    monkeypatch.setattr(agent, "_answer", lambda q, s: "20 days [handbook].")

    result = agent.run_agent("vacation?")
    assert result.action == "answer"
    assert result.sources[0].title == "handbook"
    assert not any("retried" in step for step in result.steps)


def test_agent_search_retries_when_insufficient(monkeypatch):
    monkeypatch.setattr(agent, "get_llm", lambda: ("c", "m", "e"))
    monkeypatch.setattr(agent, "_route", lambda q: ("search", "leave"))

    calls = {"n": 0}

    def fake_retrieve(query):
        calls["n"] += 1
        return [Source("h", f"chunk {calls['n']}")]

    monkeypatch.setattr(agent, "retrieve", fake_retrieve)
    grades = iter([False, True])  # weak first, good after rephrase
    monkeypatch.setattr(agent, "_is_sufficient", lambda q, s: next(grades))
    monkeypatch.setattr(agent, "_rephrase", lambda q: "sick leave policy")
    monkeypatch.setattr(agent, "_answer", lambda q, s: "answer")

    result = agent.run_agent("leave?")
    assert result.action == "answer"
    assert calls["n"] == 2  # retried exactly once
    assert any("retried" in step for step in result.steps)


def test_agent_search_stops_at_max_retries(monkeypatch):
    monkeypatch.setattr(agent, "get_llm", lambda: ("c", "m", "e"))
    monkeypatch.setattr(agent, "_route", lambda q: ("search", "leave"))

    calls = {"n": 0}

    def fake_retrieve(query):
        calls["n"] += 1
        return [Source("h", "weak")]

    monkeypatch.setattr(agent, "retrieve", fake_retrieve)
    monkeypatch.setattr(agent, "_is_sufficient", lambda q, s: False)  # never enough
    monkeypatch.setattr(agent, "_rephrase", lambda q: "rephrased")
    monkeypatch.setattr(agent, "_answer", lambda q, s: "best effort")

    result = agent.run_agent("leave?")
    assert result.action == "answer"
    # initial search + MAX_RETRIES additional attempts
    assert calls["n"] == agent.MAX_RETRIES + 1
