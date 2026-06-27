"""Application configuration loaded from environment variables."""
import os
from functools import lru_cache

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class Settings:
    """Runtime settings for the RAG service."""

    def __init__(self) -> None:
        # Azure OpenAI
        self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.azure_openai_api_version = os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-06-01"
        )
        self.chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
        self.embedding_deployment = os.getenv(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
        )

        # Azure AI Search
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
        self.search_api_key = os.getenv("AZURE_SEARCH_API_KEY", "")
        self.search_index = os.getenv("AZURE_SEARCH_INDEX", "knowledge-index")

        # Local provider (Ollama) — used when Azure is not configured
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.ollama_chat_model = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:1b")
        self.ollama_embedding_model = os.getenv(
            "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
        )
        self.local_index_path = os.getenv(
            "LOCAL_INDEX_PATH", os.path.join(_DATA_DIR, "index.json")
        )

        # Retrieval tuning
        self.top_k = int(os.getenv("RAG_TOP_K", "4"))

    @property
    def use_azure_openai(self) -> bool:
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key)

    @property
    def use_search(self) -> bool:
        return bool(self.search_endpoint and self.search_api_key)

    @property
    def provider(self) -> str:
        """Active provider: 'azure' or 'local'. Override with PROVIDER env var."""
        explicit = os.getenv("PROVIDER", "").lower()
        if explicit in ("azure", "local"):
            return explicit
        return "azure" if self.use_azure_openai else "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
