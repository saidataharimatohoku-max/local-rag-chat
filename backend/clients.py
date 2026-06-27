"""Factory helpers for chat/embedding clients (Azure OpenAI or local Ollama)."""
from __future__ import annotations

from functools import lru_cache

from .config import get_settings


@lru_cache
def get_openai_client():
    """Return a configured Azure OpenAI client, or None if not configured."""
    settings = get_settings()
    if not settings.use_azure_openai:
        return None

    from openai import AzureOpenAI

    return AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )


@lru_cache
def get_ollama_client():
    """Return an OpenAI-compatible client pointed at the local Ollama server."""
    settings = get_settings()
    from openai import OpenAI

    return OpenAI(base_url=settings.ollama_base_url, api_key="ollama")


@lru_cache
def get_search_client():
    """Return a configured Azure AI Search client, or None if not configured."""
    settings = get_settings()
    if not settings.use_search:
        return None

    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    return SearchClient(
        endpoint=settings.search_endpoint,
        index_name=settings.search_index,
        credential=AzureKeyCredential(settings.search_api_key),
    )


def get_llm():
    """Return (client, chat_model, embedding_model) for the active provider.

    Returns None if the selected provider is Azure but not configured.
    """
    settings = get_settings()
    if settings.provider == "azure":
        client = get_openai_client()
        if client is None:
            return None
        return client, settings.chat_deployment, settings.embedding_deployment

    return (
        get_ollama_client(),
        settings.ollama_chat_model,
        settings.ollama_embedding_model,
    )

