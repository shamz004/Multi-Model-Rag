import json

from fastapi.testclient import TestClient

from app.chat import NO_DOCUMENTS_TEXT, NOT_FOUND_TEXT
from app.main import create_app

from .conftest import FINANCE_BYTES, ask, make_pdf


# ---- health and configuration -------------------------------------------


def test_health_reports_configuration(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["openai_configured"] is True
    assert body["indexed_chunks"] == 0


def test_missing_api_key_gives_clear_503(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json()["openai_configured"] is False
        upload = client.post(
            "/api/documents", files=[("files", ("a.pdf", make_pdf(["x"]), "application/pdf"))]
        )
        chat = client.post("/api/chat", json={"question": "hello"})
    assert upload.status_code == 503
    assert chat.status_code == 503
    assert "OPENAI_API_KEY" in chat.json()["detail"]


# ---- documents -----------------------------------------------------------


def test_upload_multiple_pdfs_processes_them(loaded):
    finance, security = loaded.docs["finance.pdf"], loaded.docs["security.pdf"]
    assert finance["pages"] == 2 and finance["chunks"] >= 2
    assert security["pages"] == 2 and security["chunks"] >= 2
    health = loaded.get("/api/health").json()
    assert health["indexed_chunks"] == finance["chunks"] + security["chunks"]


def test_upload_rejects_non_pdf_and_accepts_the_rest(client):
    response = client.post(
        "/api/documents",
        files=[
            ("files", ("notes.txt", b"just text", "text/plain")),
            ("files", ("real.pdf", make_pdf(["Real content here."]), "application/pdf")),
        ],
    )
    results = {r["filename"]: r for r in response.json()}
    assert results["notes.txt"]["status"] == "rejected"
    assert [d["filename"] for d in client.get("/api/documents").json()] == ["real.pdf"]


def test_upload_same_file_twice_is_deduplicated(loaded):
    response = loaded.post(
        "/api/documents",
        files=[("files", ("copy.pdf", FINANCE_BYTES, "application/pdf"))],
    )
    assert response.json()[0]["duplicate"] is True
    assert len(loaded.get("/api/documents").json()) == 2


def test_pdf_without_text_is_marked_failed(client):
    client.post(
        "/api/documents", files=[("files", ("scan.pdf", make_pdf(["", ""]), "application/pdf"))]
    )
    doc = client.get("/api/documents").json()[0]
    assert doc["status"] == "failed"
    assert "No extractable text" in doc["error"]


def test_document_file_can_be_downloaded(loaded):
    response = loaded.get(f"/api/documents/{loaded.docs['finance.pdf']['id']}/file")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert loaded.get("/api/documents/unknown/file").status_code == 404


def test_delete_document_removes_it_from_search(loaded, llm):
    doc_id = loaded.docs["security.pdf"]["id"]
    assert loaded.delete(f"/api/documents/{doc_id}").status_code == 200
    assert loaded.delete(f"/api/documents/{doc_id}").status_code == 404
    result = ask(loaded, "How many characters must passwords contain?")
    assert result["message"]["answerable"] is False
    assert all(s["filename"] != "security.pdf" for s in result["message"]["sources"])


# ---- grounded answers, citations, unavailable information ----------------


def test_answer_cites_the_right_document_and_page(loaded):
    result = ask(loaded, "How many characters must passwords contain?")
    message = result["message"]
    assert message["answerable"] is True
    assert "14 characters" in message["content"]
    cited = [s for s in message["sources"] if s["cited"]]
    assert len(cited) == 1
    assert (cited[0]["filename"], cited[0]["page"], cited[0]["n"]) == ("security.pdf", 1, 1)


def test_questions_are_routed_to_the_correct_document(loaded):
    result = ask(loaded, "What was the total revenue of Aurora Dynamics for 2024?")
    top = result["message"]["sources"][0]
    assert (top["filename"], top["page"]) == ("finance.pdf", 1)
    result = ask(loaded, "Within how many days must critical patches be installed?")
    top = result["message"]["sources"][0]
    assert (top["filename"], top["page"]) == ("security.pdf", 2)


def test_unrelated_question_is_refused_without_calling_the_llm(loaded, llm):
    result = ask(loaded, "Which football club won the league?")
    assert result["message"]["content"] == NOT_FOUND_TEXT
    assert result["message"]["answerable"] is False
    assert result["message"]["sources"] == []
    assert llm.stream_calls == []


def test_model_reported_not_found_hides_sources(loaded, llm):
    llm.reply = NOT_FOUND_TEXT
    result = ask(loaded, "What was the revenue of Aurora Dynamics in 1999?")
    assert len(llm.stream_calls) == 1
    assert result["message"]["answerable"] is False
    assert result["message"]["sources"] == []


def test_chat_with_no_documents(client, llm):
    result = ask(client, "What is the revenue?")
    assert result["message"]["content"] == NO_DOCUMENTS_TEXT
    assert llm.stream_calls == []


def test_document_filter_restricts_retrieval(loaded):
    finance_id = loaded.docs["finance.pdf"]["id"]
    result = ask(
        loaded, "How many characters must passwords contain?", document_ids=[finance_id]
    )
    assert all(s["filename"] == "finance.pdf" for s in result["message"]["sources"])
    assert result["message"]["answerable"] is False


def test_prompt_contains_only_retrieved_sources_and_grounding_rules(loaded, llm):
    ask(loaded, "How many people did the company employ?")
    messages = llm.stream_calls[0]
    assert "ONLY the numbered source excerpts" in messages[0]["content"]
    assert "[1] Document: finance.pdf | Page 2" in messages[-1]["content"]


# ---- conversation memory -------------------------------------------------


def test_follow_up_question_uses_conversation_memory(loaded, llm):
    first = ask(loaded, "Who is the chief financial officer of Aurora Dynamics?")
    conv_id = first["conversation"]["id"]
    assert first["rewritten_question"] is None  # no history yet -> no rewrite call
    assert llm.complete_calls == []

    second = ask(loaded, "When did he join?", conversation_id=conv_id)
    # The rewrite step saw the earlier turn and produced a standalone question.
    assert len(llm.complete_calls) == 1
    assert "chief financial officer" in second["rewritten_question"]
    assert second["conversation"]["id"] == conv_id
    top = second["message"]["sources"][0]
    assert (top["filename"], top["page"]) == ("finance.pdf", 2)

    # The answer prompt included the earlier turns.
    roles = [m["role"] for m in llm.stream_calls[1]]
    assert roles == ["system", "user", "assistant", "user"]

    stored = loaded.get(f"/api/conversations/{conv_id}").json()
    assert [m["role"] for m in stored["messages"]] == ["user", "assistant", "user", "assistant"]
    assert stored["title"] == "Who is the chief financial officer of Aurora Dynamics?"


def test_conversations_are_isolated_from_each_other(loaded, llm):
    ask(loaded, "Who is the chief financial officer of Aurora Dynamics?")
    ask(loaded, "How many days are backups retained?")  # new conversation
    assert llm.complete_calls == []
    assert [m["role"] for m in llm.stream_calls[1]] == ["system", "user"]
    assert len(loaded.get("/api/conversations").json()) == 2


def test_conversation_crud(client):
    conv = client.post("/api/conversations").json()
    assert conv["title"] == "New chat"
    renamed = client.patch(f"/api/conversations/{conv['id']}", json={"title": "Budget review"})
    assert renamed.json()["title"] == "Budget review"
    assert client.patch(f"/api/conversations/{conv['id']}", json={"title": ""}).status_code == 422
    assert client.delete(f"/api/conversations/{conv['id']}").status_code == 200
    assert client.get(f"/api/conversations/{conv['id']}").status_code == 404
    assert client.get("/api/conversations").json() == []


# ---- streaming and persistence ------------------------------------------


def test_streaming_emits_sources_tokens_and_done(loaded):
    with loaded.stream(
        "POST", "/api/chat", json={"question": "How many days are backups retained?"}
    ) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [
            json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")
        ]
    types = [e["type"] for e in events]
    assert types[0] == "conversation" and types[1] == "sources" and types[-1] == "done"
    assert types.count("token") > 1
    streamed = "".join(e["text"] for e in events if e["type"] == "token")
    assert streamed.strip() == events[-1]["message"]["content"]
    assert "35 days" in streamed


def test_index_is_rebuilt_from_storage_after_restart(loaded, settings, embedder, llm):
    chunks = loaded.get("/api/health").json()["indexed_chunks"]
    with TestClient(create_app(settings, embedder=embedder, llm=llm)) as restarted:
        assert restarted.get("/api/health").json()["indexed_chunks"] == chunks
        result = ask(restarted, "How many days are backups retained?")
        assert "35 days" in result["message"]["content"]


def test_empty_question_is_rejected(client):
    assert client.post("/api/chat", json={"question": "   "}).status_code == 422
    assert client.post("/api/chat", json={"question": ""}).status_code == 422
