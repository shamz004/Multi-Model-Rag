"""Document ingestion: PDF -> pages -> chunks -> embeddings -> storage + index."""

import logging
from pathlib import Path

from .pdf import chunk_pages, parse_pdf
from .services import Services

log = logging.getLogger(__name__)


def embedding_input(filename: str, chunk: dict) -> str:
    """The document name and page are embedded with the text so that questions
    naming a report ("in the 2023 annual report...") match its chunks."""
    return f"Document: {filename} | Page {chunk['page']}\n{chunk['text']}"


def ingest_document(services: Services, doc_id: str, path: Path) -> None:
    """Runs as a background task; records success or failure on the document row."""
    settings = services.settings
    try:
        doc = services.db.get_document(doc_id)
        if doc is None:
            return
        pages = parse_pdf(path)
        chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ValueError(
                "No extractable text found. The PDF may be scanned images; OCR is not supported."
            )
        embeddings = services.embedder.embed(
            [embedding_input(doc["filename"], c) for c in chunks]
        )
        if services.index.dim not in (None, embeddings.shape[1]) and len(services.index):
            raise ValueError(
                "The embedding model was changed since earlier documents were indexed. "
                "Delete the data folder and re-upload the documents."
            )
        ids = services.db.add_chunks(doc_id, len(pages), chunks, embeddings)
        services.index.add(ids, embeddings)
        log.info("Ingested %s: %d pages, %d chunks", doc["filename"], len(pages), len(chunks))
    except Exception as exc:  # noqa: BLE001 - any failure must be recorded on the document
        log.exception("Ingestion failed for document %s", doc_id)
        services.db.set_document_status(doc_id, "failed", str(exc)[:500])
