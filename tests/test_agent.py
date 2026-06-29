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
    action, detail = agent._route("How many vacation days?", history=[])
    assert action == "search"
    assert detail == "vacation"


def test_route_defaults_to_search_on_garbage(monkeypatch):
    monkeypatch.setattr(agent, "_chat", lambda messages, temperature=0.0: "not json")
    action, detail = agent._route("something", history=[])
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
    monkeypatch.setattr(agent, "_route", lambda q, h: ("clarify", "Which leave type?"))

    result = agent.run_agent("leave?")
    assert result.action == "clarify"
    assert "Which leave type?" in result.text
    assert result.sources == []


def test_agent_answers_directly(monkeypatch):
    monkeypatch.setattr(agent, "get_llm", lambda: ("c", "m", "e"))
    monkeypatch.setattr(agent, "_route", lambda q, h: ("answer", ""))
    monkeypatch.setattr(agent, "_answer", lambda q, s, h: "Hello!")

    result = agent.run_agent("hi")
    assert result.action == "answer"
    assert result.text == "Hello!"
    assert result.sources == []


def test_agent_search_sufficient_no_retry(monkeypatch):
    monkeypatch.setattr(agent, "get_llm", lambda: ("c", "m", "e"))
    monkeypatch.setattr(agent, "_route", lambda q, h: ("search", "vacation policy"))
    monkeypatch.setattr(agent, "condense_question", lambda q, h: q)
    monkeypatch.setattr(agent, "retrieve", lambda q, history: [Source("handbook", "20 days")])
    monkeypatch.setattr(agent, "_is_sufficient", lambda q, s: True)
    monkeypatch.setattr(agent, "_answer", lambda q, s, h: "20 days [handbook].")

    result = agent.run_agent("vacation?")
    assert result.action == "answer"
    assert result.sources[0].title == "handbook"
    assert not any("retried" in step for step in result.steps)


def test_agent_search_retries_when_insufficient(monkeypatch):
    monkeypatch.setattr(agent, "get_llm", lambda: ("c", "m", "e"))
    monkeypatch.setattr(agent, "_route", lambda q, h: ("search", "leave"))

    calls = {"n": 0}

    def fake_retrieve(query, history):
        calls["n"] += 1
        return [Source("h", f"chunk {calls['n']}")]

    monkeypatch.setattr(agent, "condense_question", lambda q, h: q)
    monkeypatch.setattr(agent, "retrieve", fake_retrieve)
    grades = iter([False, True])  # weak first, good after rephrase
    monkeypatch.setattr(agent, "_is_sufficient", lambda q, s: next(grades))
    monkeypatch.setattr(agent, "_rephrase", lambda q: "sick leave policy")
    monkeypatch.setattr(agent, "_answer", lambda q, s, h: "answer")

    result = agent.run_agent("leave?")
    assert result.action == "answer"
    assert calls["n"] == 2  # retried exactly once
    assert any("retried" in step for step in result.steps)


def test_agent_search_stops_at_max_retries(monkeypatch):
    monkeypatch.setattr(agent, "get_llm", lambda: ("c", "m", "e"))
    monkeypatch.setattr(agent, "_route", lambda q, h: ("search", "leave"))

    calls = {"n": 0}

    def fake_retrieve(query, history):
        calls["n"] += 1
        return [Source("h", "weak")]

    monkeypatch.setattr(agent, "retrieve", fake_retrieve)
    monkeypatch.setattr(agent, "_is_sufficient", lambda q, s: False)  # never enough
    monkeypatch.setattr(agent, "_rephrase", lambda q: "rephrased")
    monkeypatch.setattr(agent, "_answer", lambda q, s, h: "best effort")

    result = agent.run_agent("leave?")
    assert result.action == "answer"
    # initial search + MAX_RETRIES additional attempts
    assert calls["n"] == agent.MAX_RETRIES + 1


def test_route_with_history(monkeypatch):
    """Test that _route includes conversation history in routing decision."""
    received_messages = []

    def capture_chat(messages, temperature=0.0):
        received_messages.extend(messages)
        return '{"action": "search", "detail": "query"}'

    monkeypatch.setattr(agent, "_chat", capture_chat)

    history = [("user", "first question"), ("assistant", "first answer")]
    agent._route("follow-up?", history)

    # Should have system + history + current question
    assert len(received_messages) >= 4
    assert received_messages[1]["content"] == "first question"
    assert received_messages[2]["content"] == "first answer"
    assert received_messages[3]["content"] == "follow-up?"


def test_answer_with_history(monkeypatch):
    """Test that _answer passes history to _build_messages."""
    build_messages_calls = []

    def capture_build(question, sources, history):
        build_messages_calls.append((question, len(sources), len(history)))
        return [{"role": "system", "content": "test"}]

    def fake_chat(messages, temperature):
        return "answer"

    monkeypatch.setattr(agent, "_build_messages", capture_build)
    monkeypatch.setattr(agent, "_chat", fake_chat)

    history = [("user", "hi")]
    sources = [Source("doc", "content")]
    result = agent._answer("follow-up", sources, history)

    assert result == "answer"
    assert build_messages_calls[0] == ("follow-up", 1, 1)


def test_agent_search_with_history_condenses_query(monkeypatch):
    """Test that agent search path uses condensed query with history."""
    condense_calls = []

    def capture_condense(question, history):
        condense_calls.append((question, len(history)))
        return "condensed query"

    monkeypatch.setattr(agent, "get_llm", lambda: ("c", "m", "e"))
    monkeypatch.setattr(agent, "_route", lambda q, h: ("search", "raw query"))
    monkeypatch.setattr(agent, "condense_question", capture_condense)
    monkeypatch.setattr(agent, "retrieve", lambda q, history: [])
    monkeypatch.setattr(agent, "_is_sufficient", lambda q, s: True)
    monkeypatch.setattr(agent, "_answer", lambda q, s, h: "answer")

    history = [("user", "first")]
    agent.run_agent("follow-up?", history=history)

    # Should have condensed the detail from route
    assert len(condense_calls) == 1
    assert condense_calls[0] == ("raw query", 1)


def test_agent_passes_history_to_retrieve_and_answer(monkeypatch):
    """Test that run_agent threads history through retrieve and answer."""
    retrieve_calls = []
    answer_calls = []

    def capture_retrieve(query, history):
        retrieve_calls.append(len(history))
        return [Source("doc", "content")]

    def capture_answer(question, sources, history):
        answer_calls.append(len(history))
        return "answer"

    monkeypatch.setattr(agent, "get_llm", lambda: ("c", "m", "e"))
    monkeypatch.setattr(agent, "_route", lambda q, h: ("search", "query"))
    monkeypatch.setattr(agent, "condense_question", lambda q, h: q)
    monkeypatch.setattr(agent, "retrieve", capture_retrieve)
    monkeypatch.setattr(agent, "_is_sufficient", lambda q, s: True)
    monkeypatch.setattr(agent, "_answer", capture_answer)

    history = [("user", "first"), ("assistant", "response")]
    agent.run_agent("follow-up?", history=history)

    assert retrieve_calls[0] == 2
    assert answer_calls[0] == 2
