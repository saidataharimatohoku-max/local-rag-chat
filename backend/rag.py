"""Retrieval-augmented generation pipeline (Azure OpenAI or local Ollama)."""
from __future__ import annotations

from dataclasses import dataclass

from . import store
from .clients import get_llm, get_search_client
from .config import get_settings

SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question using only the "
    "provided context. If the context does not contain the answer, say you "
    "don't know. Cite the source title in square brackets when you use it."
)

CONDENSE_PROMPT = (
    "Given the conversation history and a follow-up question, rephrase the "
    "follow-up into a standalone search query that captures the full intent. "
    "If the question is already standalone, return it as-is. Return ONLY the "
    "query text, no explanation."
)


@dataclass
class Source:
    title: str
    content: str


@dataclass
class Answer:
    text: str
    sources: list[Source]


def _embed(client, model: str, text: str) -> list[float]:
    response = client.embeddings.create(model=model, input=text)
    return response.data[0].embedding


def condense_question(question: str, history: list[tuple[str, str]]) -> str:
    """Condense a follow-up question with history into a standalone query.
    
    This enables history-aware retrieval: a question like "what about its cost?"
    becomes "what about the product's cost?" based on prior context.
    Degrades gracefully when no LLM is available (returns original question).
    """
    if not history:
        return question
    
    llm = get_llm()
    if llm is None:
        return question
    
    client, chat_model, _ = llm
    
    # Build messages with history
    messages = [{"role": "system", "content": CONDENSE_PROMPT}]
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})
    
    try:
        completion = client.chat.completions.create(
            model=chat_model,
            messages=messages,
            temperature=0.0,
        )
        condensed = completion.choices[0].message.content.strip()
        return condensed if condensed else question
    except Exception:
        # On any error, fall back to the original question
        return question


def retrieve(question: str, history: list[tuple[str, str]] | None = None) -> list[Source]:
    """Retrieve the most relevant document chunks for a question.
    
    When history is provided, condenses the question into a standalone query
    for better retrieval on follow-up questions.
    """
    history = history or []
    
    # Condense the question if we have conversation history
    search_query = condense_question(question, history)
    
    settings = get_settings()
    llm = get_llm()
    if llm is None:
        return []
    client, _, embed_model = llm
    vector = _embed(client, embed_model, search_query)

    if settings.provider == "azure":
        search = get_search_client()
        if search is None:
            return []
        from azure.search.documents.models import VectorizedQuery

        vector_query = VectorizedQuery(
            vector=vector, k_nearest_neighbors=settings.top_k, fields="embedding"
        )
        results = search.search(
            search_text=question,
            vector_queries=[vector_query],
            top=settings.top_k,
            select=["title", "content"],
        )
        return [Source(title=r["title"], content=r["content"]) for r in results]

    # Local provider: cosine search over the on-disk index.
    records = store.search(vector, settings.top_k)
    return [Source(title=r["title"], content=r["content"]) for r in records]


def answer_question(question: str, history: list[tuple[str, str]] | None = None) -> Answer:
    """Run the full RAG pipeline and return a grounded answer.
    
    Args:
        question: The user's current question
        history: Optional list of (role, content) tuples from prior turns
    """
    history = history or []
    llm = get_llm()

    if llm is None:
        return Answer(
            text=(
                "No language model is configured. Set Azure OpenAI credentials, or "
                "run Ollama locally (PROVIDER=local)."
            ),
            sources=[],
        )

    client, chat_model, _ = llm
    sources = retrieve(question, history=history)
    messages = _build_messages(question, sources, history=history)

    completion = client.chat.completions.create(
        model=chat_model,
        messages=messages,
        temperature=0.2,
    )
    return Answer(text=completion.choices[0].message.content, sources=sources)


def _build_messages(question: str, sources: list[Source], history: list[tuple[str, str]] | None = None) -> list[dict]:
    """Build the chat messages including system prompt, history, and context."""
    history = history or []
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add conversation history
    for role, content in history:
        messages.append({"role": role, "content": content})
    
    # Add current question with retrieved context
    context = "\n\n".join(f"[{s.title}]\n{s.content}" for s in sources)
    user_content = f"Context:\n{context}\n\nQuestion: {question}"
    messages.append({"role": "user", "content": user_content})
    
    return messages


def stream_answer(question: str, history: list[tuple[str, str]] | None = None):
    """Return (sources, token_iterator) for a streamed RAG answer.

    The token iterator yields successive pieces of the answer text as the
    model generates them.
    
    Args:
        question: The user's current question
        history: Optional list of (role, content) tuples from prior turns
    """
    history = history or []
    llm = get_llm()

    if llm is None:
        def _unconfigured():
            yield (
                "No language model is configured. Set Azure OpenAI credentials, "
                "or run Ollama locally (PROVIDER=local)."
            )

        return [], _unconfigured()

    client, chat_model, _ = llm
    sources = retrieve(question, history=history)
    messages = _build_messages(question, sources, history=history)

    def _tokens():
        stream = client.chat.completions.create(
            model=chat_model,
            messages=messages,
            temperature=0.2,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    return sources, _tokens()

