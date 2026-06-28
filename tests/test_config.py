"""Tests for provider-selection logic in Settings."""
import pytest

from backend.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults_to_local_without_azure(monkeypatch):
    monkeypatch.delenv("PROVIDER", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    assert Settings().provider == "local"


def test_uses_azure_when_configured(monkeypatch):
    monkeypatch.delenv("PROVIDER", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "secret")
    settings = Settings()
    assert settings.use_azure_openai is True
    assert settings.provider == "azure"


def test_explicit_provider_override_wins(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "secret")
    monkeypatch.setenv("PROVIDER", "local")
    assert Settings().provider == "local"


def test_top_k_reads_from_env(monkeypatch):
    monkeypatch.setenv("RAG_TOP_K", "7")
    assert Settings().top_k == 7
