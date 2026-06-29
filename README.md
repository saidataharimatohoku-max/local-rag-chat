# Local RAG Chat — AI Document Q&A with Cited Sources

[![Tests](https://github.com/saidataharimatohoku-max/local-rag-chat/actions/workflows/tests.yml/badge.svg)](https://github.com/saidataharimatohoku-max/local-rag-chat/actions/workflows/tests.yml)
[![Coverage](docs/coverage.svg)](docs/coverage.svg)

> Ask questions about your own documents and get streamed, source-cited answers — running fully offline and free with Ollama, or on Azure OpenAI + AI Search.

A minimal Retrieval-Augmented Generation (RAG) application: a Python FastAPI
backend, a static web frontend, and Azure infrastructure to host it. It answers
questions grounded in your own Markdown documents using Azure OpenAI for
embeddings/chat and Azure AI Search for retrieval. It also runs **fully local
and free** with [Ollama](https://ollama.com) — no cloud account required.

## Demo

![RAG Chat answering a question grounded in a source document](docs/demo.png)

The app retrieves the most relevant chunks from your documents and answers using
only that context, citing its sources — so it doesn't make things up. Answers
**stream in token-by-token**, and each cited source expands to show the exact
retrieved text. The app supports **multi-turn conversations**: follow-up
questions like "what about its cost?" or "and why?" understand the prior
context, with history-aware retrieval ensuring relevant documents are found
even for context-dependent queries. Click **🔄 New chat** to start a fresh
conversation. You can add documents straight from the browser — click
**+ Add document** or **drag & drop** a file onto the page (Markdown, plain
text, PDF, or Word) — and the list of indexed documents updates instantly. You
can also drop files into the `data/` folder and run the ingest command.

Flip on **Agent mode** for an agentic workflow: the app routes each question
(answer directly, search the documents, or ask a clarifying question),
self-evaluates whether the retrieved context is good enough, and automatically
rephrases and retries the search when it isn't — showing its reasoning steps
alongside the answer.

## Project structure

```
backend/      FastAPI app, RAG pipeline, agent loop, ingestion, clients, config
frontend/     Static chat UI (HTML/CSS/JS)
data/         Source documents to index (.md, .txt, .pdf, .docx)
infra/        Azure Bicep templates (Search + Web App)
.github/      CI/CD workflow
```

## Prerequisites

- Python 3.11+
- **Local mode (free, no cloud):** [Ollama](https://ollama.com) installed
- **Azure mode (optional):** an Azure OpenAI resource (chat + embedding
  deployments) and an Azure AI Search service

The app auto-detects the provider: it uses Azure when Azure OpenAI is
configured, otherwise it runs fully locally with Ollama. Force it with the
`PROVIDER` environment variable (`local` or `azure`).

## Run locally with Ollama (no account needed)

1. Install Ollama from https://ollama.com, then pull the models:

   ```powershell
   ollama pull llama3.2:1b
   ollama pull nomic-embed-text
   ```

2. Create the virtual environment and install dependencies:

   ```powershell
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Build the local index from `data/` and run the app:

   ```powershell
   .venv\Scripts\python.exe -m backend.ingest
   .venv\Scripts\python.exe -m uvicorn backend.app:app --reload
   ```

   Open http://localhost:8000 to chat. Retrieval uses a local NumPy vector
   store (`data/index.json`) instead of Azure AI Search.

## Azure setup

1. Create and activate a virtual environment, then install dependencies:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env`, set `PROVIDER=azure`, and fill in your Azure
   credentials. Load it into your shell (or use a tool such as `python-dotenv`).

3. Ingest the documents from `data/` into Azure AI Search:

   ```powershell
   python -m backend.ingest
   ```

4. Run the API and frontend:

   ```powershell
   python -m uvicorn backend.app:app --reload
   ```

   Open http://localhost:8000 to chat.

## How it works

1. `ingest.py` reads every supported document in `data/` (Markdown, plain
   text, PDF, and Word `.docx`), chunks it, embeds the chunks (Azure OpenAI
   or local Ollama), and stores them in Azure AI Search or a local index.
2. On a question, `rag.py` embeds the query, retrieves the top matching chunks,
   and asks the chat model to answer using only that context.
3. For multi-turn conversations, the app condenses follow-up questions with
   prior history into standalone search queries ("what about its cost?"
   becomes "what about the product's cost?" if the prior question was about a
   product), then threads the conversation history into the final answer
   generation so the model sees the full context.
4. `app.py` serves the static frontend, a JSON `/api/chat` endpoint, and a
   streaming `/api/chat/stream` endpoint (Server-Sent Events) that the UI uses
   to render answers token-by-token.

## Tests

Unit and API tests run fully offline (the language model is mocked), so no
Ollama or Azure account is needed:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
```

They cover text chunking, the on-disk vector store, multi-format document
reading, provider selection, the RAG pipeline internals (retrieval, prompt
building, answer and streaming generation, conversation history threading,
history-aware query condensation, and the unconfigured-model paths), the
agentic pipeline (routing with history, self-evaluation, retry logic), and the
API endpoints (chat, streaming, agent, upload, validation, document list,
conversation history, and backward compatibility). **64 tests**, **83%
coverage**. The same suite runs on every push via GitHub Actions
(`.github/workflows/tests.yml`).

To measure coverage and refresh the badge:

```powershell
.venv\Scripts\python.exe -m pytest --cov=backend --cov-report=term-missing
.venv\Scripts\python.exe scripts\generate_coverage_badge.py
```

## Deploy to Azure

Provision infrastructure with the Bicep templates in `infra/`:

```powershell
az group create --name rag-rg --location eastus
az deployment group create `
  --resource-group rag-rg `
  --template-file infra/main.bicep `
  --parameters infra/main.parameters.json
```

Then set the Azure OpenAI app settings on the Web App and deploy the code
(the included GitHub Actions workflow in `.github/workflows/deploy.yml`
publishes on push to `main`).

## Configuration

All settings are read from environment variables; see `.env.example` for the
full list. If Azure OpenAI or Search is not configured, the API responds with a
helpful message instead of failing.

## Backup & versioning

The project is version-controlled with Git and published on GitHub, with
tagged releases marking stable checkpoints (see the
[Releases](https://github.com/saidataharimatohoku-max/local-rag-chat/releases)
page). To restore a release: `git clone` the repo and `git checkout v1.0.0`.

For an extra local safety net, run the backup script:

```powershell
.\backup.ps1
```

It writes two files to a sibling `microsoft-project4-backups` folder:

- a **git bundle** containing the complete commit history — clone it offline
  with `git clone <file>.bundle restored-project`, and
- a **source zip** snapshot of the tracked files (no `.venv` or secrets).
