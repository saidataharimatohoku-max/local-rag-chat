"""Ingest documents from the data/ folder into the vector index.

Supports Markdown (.md), plain text (.txt), PDF (.pdf), and Word (.docx)
files. Uses Azure AI Search when Azure is configured, otherwise builds a
local on-disk index for Ollama-based retrieval.

Usage:
    python -m backend.ingest
"""
from __future__ import annotations

import glob
import os
import uuid

from . import store
from .clients import get_llm, get_search_client
from .config import get_settings

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SUPPORTED_EXTENSIONS = (".md", ".txt", ".pdf", ".docx")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Split text into overlapping word-based chunks."""
    words = text.split()
    step = max(size - overlap, 1)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + size])
        if chunk:
            yield chunk


def ensure_index() -> None:
    """Create the search index if it does not already exist."""
    settings = get_settings()
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )

    index_client = SearchIndexClient(
        endpoint=settings.search_endpoint,
        credential=AzureKeyCredential(settings.search_api_key),
    )

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="default-profile",
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
        profiles=[
            VectorSearchProfile(
                name="default-profile", algorithm_configuration_name="default-hnsw"
            )
        ],
    )

    from azure.search.documents.indexes.models import SearchIndex

    index = SearchIndex(
        name=settings.search_index, fields=fields, vector_search=vector_search
    )
    index_client.create_or_update_index(index)
    print(f"Index '{settings.search_index}' is ready.")


def embed(text: str) -> list[float]:
    client, _, embed_model = get_llm()
    response = client.embeddings.create(model=embed_model, input=text)
    return response.data[0].embedding


def _read_text_file(path: str) -> str:
    """Read a Markdown or plain-text file."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _read_pdf(path: str) -> str:
    """Extract text from a PDF file."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _read_docx(path: str) -> str:
    """Extract text from a Word .docx file."""
    from docx import Document

    document = Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def read_document(path: str) -> str:
    """Read a document's text based on its file extension."""
    extension = os.path.splitext(path)[1].lower()
    if extension in (".md", ".txt"):
        return _read_text_file(path)
    if extension == ".pdf":
        return _read_pdf(path)
    if extension == ".docx":
        return _read_docx(path)
    raise ValueError(f"Unsupported file type: {extension}")


def _read_chunks():
    """Yield (title, chunk) tuples for every supported file in data/."""
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*"))):
        extension = os.path.splitext(path)[1].lower()
        if extension not in SUPPORTED_EXTENSIONS:
            continue
        title = os.path.splitext(os.path.basename(path))[0]
        text = read_document(path)
        for chunk in chunk_text(text):
            yield title, chunk


def ingest() -> int:
    settings = get_settings()
    documents = [
        {
            "id": str(uuid.uuid4()),
            "title": title,
            "content": chunk,
            "embedding": embed(chunk),
        }
        for title, chunk in _read_chunks()
    ]

    if not documents:
        print("No documents found in data/.")
        return 0

    if settings.provider == "azure":
        ensure_index()
        get_search_client().upload_documents(documents)
        print(f"Ingested {len(documents)} chunks into Azure AI Search.")
    else:
        store.save_index(documents)
        print(
            f"Ingested {len(documents)} chunks into local index "
            f"({settings.local_index_path})."
        )

    return len(documents)


if __name__ == "__main__":
    ingest()
