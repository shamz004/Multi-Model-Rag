"""HTTP API."""

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from .chat import answer_events
from .ingest import ingest_document
from .services import ProviderNotConfigured, Services

router = APIRouter(prefix="/api")


def get_services(request: Request) -> Services:
    return request.app.state.services


def require_providers(services: Services) -> None:
    try:
        services.embedder  # noqa: B018 - property access triggers configuration check
    except ProviderNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ---- health --------------------------------------------------------------


@router.get("/health")
def health(request: Request) -> dict:
    services = get_services(request)
    configured = services.configured
    settings = services.settings
    return {
        "status": "ok",
        "openai_configured": configured,
        "chat_model": settings.openai_chat_model,
        "embedding_model": settings.openai_embedding_model,
        "indexed_chunks": len(services.index),
    }


# ---- documents -----------------------------------------------------------


@router.get("/documents")
def list_documents(request: Request) -> list[dict]:
    return get_services(request).db.list_documents()


@router.post("/documents")
async def upload_documents(
    request: Request, background: BackgroundTasks, files: list[UploadFile] = File(...)
) -> list[dict]:
    services = get_services(request)
    require_providers(services)
    max_bytes = services.settings.max_upload_mb * 1024 * 1024

    results: list[dict] = []
    for upload in files:
        name = Path(upload.filename or "document.pdf").name
        data = await upload.read()
        if not data.startswith(b"%PDF"):
            results.append({"filename": name, "status": "rejected", "error": "Not a PDF file."})
            continue
        if len(data) > max_bytes:
            results.append(
                {
                    "filename": name,
                    "status": "rejected",
                    "error": f"File is larger than {services.settings.max_upload_mb} MB.",
                }
            )
            continue

        digest = hashlib.sha256(data).hexdigest()
        existing = services.db.find_document_by_hash(digest)
        if existing:
            results.append({**existing, "duplicate": True})
            continue

        doc = services.db.create_document(name, digest, len(data))
        path = services.settings.upload_dir / f"{doc['id']}.pdf"
        path.write_bytes(data)
        background.add_task(ingest_document, services, doc["id"], path)
        results.append(doc)
    return results


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, request: Request) -> dict:
    services = get_services(request)
    if services.db.get_document(doc_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    removed = services.db.delete_document(doc_id)
    services.index.remove(removed)
    (services.settings.upload_dir / f"{doc_id}.pdf").unlink(missing_ok=True)
    return {"deleted": doc_id}


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: str, request: Request) -> FileResponse:
    services = get_services(request)
    doc = services.db.get_document(doc_id)
    path = services.settings.upload_dir / f"{doc_id}.pdf"
    if doc is None or not path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{doc["filename"]}"'},
    )


# ---- conversations -------------------------------------------------------


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)


@router.get("/conversations")
def list_conversations(request: Request) -> list[dict]:
    return get_services(request).db.list_conversations()


@router.post("/conversations")
def create_conversation(request: Request) -> dict:
    return get_services(request).db.create_conversation()


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: str, request: Request) -> dict:
    db = get_services(request).db
    conversation = db.get_conversation(conv_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {**conversation, "messages": db.list_messages(conv_id)}


@router.patch("/conversations/{conv_id}")
def rename_conversation(conv_id: str, body: ConversationUpdate, request: Request) -> dict:
    db = get_services(request).db
    if db.get_conversation(conv_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.rename_conversation(conv_id, body.title.strip())
    return db.get_conversation(conv_id)


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str, request: Request) -> dict:
    db = get_services(request).db
    if db.get_conversation(conv_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.delete_conversation(conv_id)
    return {"deleted": conv_id}


# ---- chat ----------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    document_ids: list[str] | None = None
    stream: bool = True


@router.post("/chat")
def chat(body: ChatRequest, request: Request):
    services = get_services(request)
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="Question is empty.")
    require_providers(services)
    events = answer_events(services, body.question, body.conversation_id, body.document_ids)

    if body.stream:

        def sse():
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            sse(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result: dict = {"rewritten_question": None}
    for event in events:
        if event["type"] == "conversation":
            result["conversation"] = event["conversation"]
        elif event["type"] == "rewrite":
            result["rewritten_question"] = event["question"]
        elif event["type"] == "done":
            result["message"] = event["message"]
        elif event["type"] == "error":
            raise HTTPException(status_code=502, detail=event["message"])
    return result
