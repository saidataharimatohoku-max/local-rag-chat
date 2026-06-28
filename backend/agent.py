"""Agentic RAG: a lightweight decision layer on top of the linear pipeline.

Where ``rag.py`` always runs the same steps (retrieve then answer), this module
lets the language model *decide* what to do:

1. **Route** the question to one of three actions:
   - ``answer``  — small talk / general question that needs no documents;
   - ``search``  — look up the user's documents (with a focused query);
   - ``clarify`` — the question is too vague, so ask the user a follow-up.
2. When searching, **grade** whether the retrieved context is sufficient and,
   if not, **rephrase** the query and try again (up to ``MAX_RETRIES`` times).

It reuses ``retrieve`` and ``_build_messages`` from ``rag.py`` and the same
provider abstraction, so it still runs fully offline on Ollama.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .clients import get_llm
from .rag import Source, _build_messages, retrieve

MAX_RETRIES = 2  # extra search attempts after the first

ROUTER_PROMPT = (
    "You route messages for a document question-answering system. Decide how "
    "to handle the user's message and respond with ONLY a JSON object with "
    'keys "action" and "detail".\n'
    '- "answer": small talk or a general question needing no documents; '
    '"detail" can be empty.\n'
    '- "search": a question about the user\'s documents; set "detail" to a '
    "concise search query.\n"
    '- "clarify": too vague or ambiguous to search well; set "detail" to a '
    "short clarifying question to ask the user.\n"
    "Return only the JSON, with no extra text."
)

GRADER_PROMPT = (
    "You judge whether the provided context is sufficient to answer the "
    'question. Respond with ONLY a JSON object: {"sufficient": true} or '
    '{"sufficient": false}.'
)

REPHRASE_PROMPT = (
    "Rewrite the user's question as a different, more specific search query "
    "that may retrieve better results. Return only the query text."
)

UNCONFIGURED_MESSAGE = (
    "No language model is configured. Set Azure OpenAI credentials, or run "
    "Ollama locally (PROVIDER=local)."
)


@dataclass
class AgentResult:
    action: str  # "answer" or "clarify"
    text: str  # the answer text, or the clarifying question
    sources: list[Source] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)  # human-readable trace


def _chat(messages, temperature: float = 0.0) -> str | None:
    """Single non-streaming chat completion for the active provider."""
    llm = get_llm()
    if llm is None:
        return None
    client, chat_model, _ = llm
    completion = client.chat.completions.create(
        model=chat_model, messages=messages, temperature=temperature
    )
    return completion.choices[0].message.content


def _parse_json(text: str) -> dict:
    """Best-effort extraction of the first JSON object from a model reply."""
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return {}


def _route(question: str) -> tuple[str, str]:
    reply = _chat(
        [
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user", "content": question},
        ]
    )
    data = _parse_json(reply or "")
    action = data.get("action")
    detail = (data.get("detail") or "").strip()
    if action not in {"answer", "search", "clarify"}:
        # Safe default: ground the answer in the documents.
        return "search", question
    return action, detail


def _is_sufficient(question: str, sources: list[Source]) -> bool:
    if not sources:
        return False
    context = "\n\n".join(f"[{s.title}] {s.content}" for s in sources)
    reply = _chat(
        [
            {"role": "system", "content": GRADER_PROMPT},
            {
                "role": "user",
                "content": f"Question: {question}\n\nContext:\n{context}",
            },
        ]
    )
    return bool(_parse_json(reply or "").get("sufficient", False))


def _rephrase(question: str) -> str:
    reply = _chat(
        [
            {"role": "system", "content": REPHRASE_PROMPT},
            {"role": "user", "content": question},
        ]
    )
    return (reply or question).strip() or question


def _answer(question: str, sources: list[Source]) -> str:
    messages = _build_messages(question, sources)
    return _chat(messages, temperature=0.2) or ""


def run_agent(question: str) -> AgentResult:
    """Route the question, optionally retrieve and self-correct, then answer."""
    steps: list[str] = []

    if get_llm() is None:
        return AgentResult(action="answer", text=UNCONFIGURED_MESSAGE, steps=steps)

    action, detail = _route(question)
    steps.append(f"Router decided: {action}")

    if action == "clarify":
        return AgentResult(
            action="clarify",
            text=detail or "Could you clarify what you're asking about?",
            steps=steps,
        )

    if action == "answer":
        steps.append("Answered directly without retrieval")
        return AgentResult(action="answer", text=_answer(question, []), steps=steps)

    # action == "search"
    query = detail or question
    sources = retrieve(query)
    steps.append(f"Searched '{query}' \u2192 {len(sources)} chunk(s)")

    attempts = 0
    while attempts < MAX_RETRIES and not _is_sufficient(question, sources):
        attempts += 1
        query = _rephrase(question)
        sources = retrieve(query)
        steps.append(
            f"Context insufficient; retried with '{query}' \u2192 "
            f"{len(sources)} chunk(s)"
        )

    steps.append("Answered with retrieved context")
    return AgentResult(
        action="answer",
        text=_answer(question, sources),
        sources=sources,
        steps=steps,
    )
