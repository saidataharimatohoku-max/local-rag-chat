"""FastAPI application exposing the RAG chat endpoint and static frontend."""
from __future__ import annotations

import json
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .ingest import DATA_DIR, SUPPORTED_EXTENSIONS, ingest, list_documents
from .rag import answer_question, stream_answer
from .agent import run_agent

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

app = FastAPI(title="RAG Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


class SourceModel(BaseModel):
    title: str
    content: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceModel]


class UploadResponse(BaseModel):
    filename: str
    chunks: int
    message: str


class AgentResponse(BaseModel):
    action: str
    text: str
    sources: list[SourceModel]
    steps: list[str]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/documents")
def documents() -> dict[str, list[str]]:
    """List the indexed source documents in data/."""
    return {"documents": list_documents()}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    result = answer_question(request.question)
    return ChatResponse(
        answer=result.text,
        sources=[SourceModel(title=s.title, content=s.content) for s in result.sources],
    )


@app.post("/api/agent", response_model=AgentResponse)
def agent(request: ChatRequest) -> AgentResponse:
    """Run the agentic RAG pipeline (routing, self-evaluation, clarification)."""
    result = run_agent(request.question)
    return AgentResponse(
        action=result.action,
        text=result.text,
        sources=[SourceModel(title=s.title, content=s.content) for s in result.sources],
        steps=result.steps,
    )


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Stream the answer token-by-token as Server-Sent Events."""
    sources, tokens = stream_answer(request.question)

    def event_stream():
        yield _sse(
            "sources",
            [{"title": s.title, "content": s.content} for s in sources],
        )
        for token in tokens:
            yield _sse("token", token)
        yield _sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    """Save an uploaded document to data/ and rebuild the index."""
    filename = os.path.basename(file.filename or "")
    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    extension = os.path.splitext(filename)[1].lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension}'. "
            f"Allowed: {', '.join(SUPPORTED_EXTENSIONS)}.",
        )

    os.makedirs(DATA_DIR, exist_ok=True)
    destination = os.path.join(DATA_DIR, filename)
    contents = await file.read()
    with open(destination, "wb") as handle:
        handle.write(contents)

    chunks = ingest()
    return UploadResponse(
        filename=filename,
        chunks=chunks,
        message=f"Indexed '{filename}'. Knowledge base now has {chunks} chunks.",
    )


if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
