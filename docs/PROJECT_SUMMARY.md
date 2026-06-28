# Project Summary — Local RAG Chat

**Repository:** https://github.com/saidataharimatohoku-max/local-rag-chat

## Overview

Local RAG Chat is a Retrieval-Augmented Generation (RAG) application that
answers questions grounded in your own documents and cites its sources, so it
does not invent answers. It runs **fully local and free** with
[Ollama](https://ollama.com) — no cloud account required — and can optionally
run on **Azure OpenAI + Azure AI Search** by changing configuration only (no
code changes).

## What it does

1. You add documents (Markdown, plain text, PDF, or Word) — from the browser or
   the `data/` folder.
2. The app splits each document into overlapping chunks, turns them into vector
   embeddings, and stores them in a searchable index.
3. When you ask a question, it embeds the question, finds the most relevant
   chunks, and asks a language model to answer using **only** that context.
4. The answer streams back token-by-token, with each cited source expandable to
   reveal the exact text it was based on.

## Key features

- **Grounded answers with citations** — responses are based on retrieved
  document chunks, each shown as an expandable source snippet.
- **Streaming responses** — answers render token-by-token via Server-Sent
  Events for a responsive, ChatGPT-like feel.
- **Multi-format ingestion** — Markdown (`.md`), text (`.txt`), PDF (`.pdf`),
  and Word (`.docx`).
- **In-browser upload** — add a document with the **+ Add document** button or
  by **dragging and dropping** it onto the page; it is indexed immediately and
  the list of indexed documents refreshes.
- **Agentic mode** — an optional agent loop that **routes** each question
  (answer directly, search, or ask for clarification), **self-evaluates** the
  retrieved context with the model, and **rephrases and retries** the search
  when the context is insufficient (up to a retry limit); the reasoning steps
  are returned and shown in the UI.
- **Local-first and free** — uses Ollama with `llama3.2:1b` (chat) and
  `nomic-embed-text` (embeddings); a NumPy cosine-similarity store replaces a
  cloud vector database.
- **Cloud-ready** — the same code targets Azure OpenAI and Azure AI Search by
  setting environment variables; Bicep templates are included.
- **Tested + CI** — a pytest suite runs offline (the model is mocked) and on
  every push via GitHub Actions.

## Architecture

```
Browser (HTML/CSS/JS)
        |  POST /api/chat/stream (SSE)   POST /api/agent   POST /api/upload
        v
FastAPI app  (backend/app.py)
        |
        +--> Agent loop (backend/agent.py): route -> retrieve -> self-check
        |                                    -> rephrase + retry -> answer
        v
RAG pipeline (backend/rag.py)
   embed question  ->  retrieve top-k chunks  ->  chat model answers
        |                    |
        |                    +-- local: NumPy cosine search (backend/store.py)
        |                    +-- azure: Azure AI Search
        v
Ingestion (backend/ingest.py): read -> chunk -> embed -> index
```

The active provider (local vs. Azure) is selected automatically in
`backend/config.py`: it uses Azure when Azure OpenAI credentials are present,
otherwise it runs locally with Ollama. The `PROVIDER` environment variable can
force either mode.

## Tech stack

| Layer        | Technology                                              |
| ------------ | ------------------------------------------------------- |
| Backend      | Python, FastAPI, Uvicorn, Pydantic                      |
| LLM (local)  | Ollama — `llama3.2:1b`, `nomic-embed-text`              |
| LLM (cloud)  | Azure OpenAI (chat + embeddings)                        |
| Retrieval    | Local NumPy vector store, or Azure AI Search            |
| Documents    | pypdf, python-docx                                      |
| Frontend     | Vanilla HTML, CSS, JavaScript (Server-Sent Events)      |
| Infra        | Azure Bicep (AI Search + Linux Python Web App)          |
| Testing / CI | pytest, pytest-cov, FastAPI TestClient, GitHub Actions   |

## Project structure

```
backend/      FastAPI app, RAG pipeline, agent loop, ingestion, store, config
frontend/     Static chat UI (HTML/CSS/JS)
data/         Source documents to index (.md, .txt, .pdf, .docx)
infra/        Azure Bicep templates (Search + Web App)
tests/        Pytest suite (chunking, store, documents, config, API)
docs/         Demo screenshot and this summary
scripts/      Word-doc generators and helpers
backup.ps1    Local backup script (git bundle + source zip)
.github/      CI (tests) and deploy workflows
```

## How to run locally (free)

```powershell
# 1. Install models
ollama pull llama3.2:1b
ollama pull nomic-embed-text

# 2. Set up Python
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Build the index and run
.venv\Scripts\python.exe -m backend.ingest
.venv\Scripts\python.exe -m uvicorn backend.app:app --reload
# open http://localhost:8000
```

## Testing

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
```

The suite (48 tests) covers text chunking, the on-disk vector store, multi-format
document reading, provider selection, the RAG pipeline internals (retrieval,
prompt building, answer and streaming generation, and the unconfigured-model
paths), the agent loop (routing, retrieval self-evaluation, rephrase-and-retry,
and clarification paths), and the API endpoints (chat, streaming, agent, upload,
validation, document list, and a path-traversal security check). It runs fully
offline because the language model is mocked, and reports ~81% line coverage of
the backend.

## Security notes

- Secrets (`.env`) and the generated index (`data/index.json`) are git-ignored.
- The upload endpoint validates file extensions against an allow-list and
  sanitizes filenames to prevent path-traversal writes outside `data/`.

## Backup & versioning

- Version-controlled with Git and published on GitHub, with tagged releases
  (e.g. `v1.0.0`) marking stable, restorable checkpoints.
- `backup.ps1` creates two local backups in a sibling folder: a **git bundle**
  with the complete commit history (clone it offline with
  `git clone <file>.bundle`) and a **source zip** snapshot of tracked files.

## Possible future enhancements

- Conversation memory for multi-turn agent follow-ups.
- Heading- or paragraph-aware chunking for more precise retrieval.
- Dockerfile + docker-compose (app + Ollama) for one-command setup.
- Authentication and per-user document collections.
