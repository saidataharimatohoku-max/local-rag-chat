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


def retrieve(question: str) -> list[Source]:
    """Retrieve the most relevant document chunks for a question."""
    settings = get_settings()
    llm = get_llm()
    if llm is None:
        return []
    client, _, embed_model = llm
    vector = _embed(client, embed_model, question)

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


def answer_question(question: str) -> Answer:
    """Run the full RAG pipeline and return a grounded answer."""
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
    sources = retrieve(question)
    context = "\n\n".join(f"[{s.title}]\n{s.content}" for s in sources)
    user_content = f"Context:\n{context}\n\nQuestion: {question}"

    completion = client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
    )
    return Answer(text=completion.choices[0].message.content, sources=sources)
