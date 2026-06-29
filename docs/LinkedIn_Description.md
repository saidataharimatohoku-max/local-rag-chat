# LinkedIn — Project Description

Ready-to-paste content for the LinkedIn **Projects** section (and Featured/posts).

---

## Project name

```
Local RAG Chat — AI Document Q&A with Cited Sources
```

## Project URL

```
https://github.com/saidataharimatohoku-max/local-rag-chat
```

---

## Description — full version

```
Local RAG Chat is a full-stack Retrieval-Augmented Generation (RAG) application that answers questions grounded in your own documents and cites its sources, so it doesn't hallucinate.

A Python/FastAPI backend ingests multi-format documents (Markdown, PDF, Word, and text), splits and embeds them into a vector index, and streams grounded answers token-by-token to a clean web UI with drag-and-drop upload and expandable source snippets. It supports multi-turn conversations: follow-up questions like "what about its cost?" understand prior context through history-aware retrieval that condenses context-dependent queries into standalone searches.

It also ships an optional agentic mode: an agent loop routes each question (answer, search, or ask a clarifying question), self-evaluates whether the retrieved context is sufficient, and automatically rephrases and retries the search before answering — exposing its reasoning steps in the UI.

It runs fully offline and free with Ollama, or scales to Azure OpenAI + Azure AI Search by changing configuration only — no code changes. Engineered with a 64-test pytest suite (83% coverage), GitHub Actions CI, and Azure Bicep infrastructure-as-code.

Tech: Python · FastAPI · RAG · AI Agents · LLMs · Ollama · Azure OpenAI · Azure AI Search · Vector Search · REST APIs · pytest · CI/CD · Bicep · JavaScript
```

## Description — short version (2–3 sentences)

```
Built a full-stack Retrieval-Augmented Generation (RAG) app that answers questions from your own documents and cites its sources — streaming answers token-by-token with expandable source snippets. Supports multi-turn conversations with history-aware retrieval, plus an agentic mode that routes questions, self-evaluates retrieval, and rephrases-and-retries before answering. Runs fully offline and free with Ollama, or on Azure OpenAI + Azure AI Search by changing configuration only; shipped with 64 automated tests (83% coverage), CI, and Bicep infrastructure-as-code.
```

---

## Skills to tag

`Python` · `FastAPI` · `Retrieval-Augmented Generation (RAG)` · `AI Agents` · `Large Language Models (LLM)` ·
`Azure OpenAI` · `Azure AI Search` · `Vector Databases` · `REST APIs` ·
`Test-Driven Development` · `CI/CD` · `Infrastructure as Code (Bicep)` · `JavaScript`

---

## Featured post (optional announcement)

```
🚀 Just shipped a project I'm proud of: Local RAG Chat — a Retrieval-Augmented Generation app that answers questions from your own documents and cites its sources, so it doesn't hallucinate.

What it does:
📄 Ingests Markdown, PDF, Word & text — upload right in the browser (drag & drop)
💬 Streams answers token-by-token, with expandable source snippets
🔄 Multi-turn conversations — follow-ups like "what about cost?" understand prior context
🤖 Optional agentic mode — routes questions, self-checks retrieval, and rephrases-and-retries before answering
🔌 Runs 100% free & offline with Ollama, or scales to Azure OpenAI + AI Search via config only
✅ 64 automated tests (83% coverage) + CI + Bicep infrastructure-as-code

Built with Python, FastAPI, and a focus on clean engineering. Code + docs here 👇
https://github.com/saidataharimatohoku-max/local-rag-chat

#Python #RAG #LLM #AIAgents #Azure #SoftwareEngineering #AI
```

---

## Posting tips

- LinkedIn shows only the first ~2 lines before a "see more" — the opening sentence is written to hook a recruiter there.
- Add the tagged skills so you surface in recruiter searches.
- Pin the repo on your GitHub profile so it's the first thing visitors see.
- Share the **GitHub** link (public, opens for everyone). Do NOT share `http://127.0.0.1:8000` — that only works on your own computer.
