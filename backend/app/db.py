"""SQLite storage: documents, chunks (with embeddings + full-text index),
conversations and messages."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    pages INTEGER NOT NULL DEFAULT 0,
    chunks INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'processing',
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, tokenize='porter unicode61');
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources TEXT NOT NULL DEFAULT '[]',
    answerable INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = WAL")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    # ---- documents -------------------------------------------------------

    def create_document(self, filename: str, sha256: str, size_bytes: int) -> dict:
        doc_id = new_id()
        with self.connect() as con:
            con.execute(
                "INSERT INTO documents (id, filename, sha256, size_bytes, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (doc_id, filename, sha256, size_bytes, now()),
            )
        return self.get_document(doc_id)

    def get_document(self, doc_id: str) -> dict | None:
        with self.connect() as con:
            row = con.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def find_document_by_hash(self, sha256: str) -> dict | None:
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM documents WHERE sha256 = ? AND status != 'failed'", (sha256,)
            ).fetchone()
        return dict(row) if row else None

    def list_documents(self) -> list[dict]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def set_document_status(self, doc_id: str, status: str, error: str | None = None) -> None:
        with self.connect() as con:
            con.execute(
                "UPDATE documents SET status = ?, error = ? WHERE id = ?", (status, error, doc_id)
            )

    def delete_document(self, doc_id: str) -> list[int]:
        """Deletes a document and its chunks; returns the removed chunk ids."""
        with self.connect() as con:
            ids = [
                r["id"]
                for r in con.execute("SELECT id FROM chunks WHERE document_id = ?", (doc_id,))
            ]
            con.executemany("DELETE FROM chunks_fts WHERE rowid = ?", [(i,) for i in ids])
            con.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        return ids

    # ---- chunks ----------------------------------------------------------

    def add_chunks(
        self, doc_id: str, pages: int, chunks: list[dict], embeddings: np.ndarray
    ) -> list[int]:
        """Stores chunks + embeddings and marks the document ready, atomically."""
        ids: list[int] = []
        with self.connect() as con:
            for chunk, emb in zip(chunks, embeddings):
                cur = con.execute(
                    "INSERT INTO chunks (document_id, page, chunk_index, text, embedding)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (
                        doc_id,
                        chunk["page"],
                        chunk["chunk_index"],
                        chunk["text"],
                        np.asarray(emb, dtype=np.float32).tobytes(),
                    ),
                )
                ids.append(cur.lastrowid)
                con.execute(
                    "INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)",
                    (cur.lastrowid, chunk["text"]),
                )
            con.execute(
                "UPDATE documents SET status = 'ready', error = NULL, pages = ?, chunks = ?"
                " WHERE id = ?",
                (pages, len(chunks), doc_id),
            )
        return ids

    def all_embeddings(self) -> tuple[list[int], np.ndarray | None]:
        with self.connect() as con:
            rows = con.execute("SELECT id, embedding FROM chunks ORDER BY id").fetchall()
        if not rows:
            return [], None
        ids = [r["id"] for r in rows]
        matrix = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
        return ids, matrix

    def get_chunks(self, chunk_ids: list[int]) -> dict[int, dict]:
        if not chunk_ids:
            return {}
        marks = ",".join("?" * len(chunk_ids))
        with self.connect() as con:
            rows = con.execute(
                f"SELECT c.id, c.document_id, c.page, c.chunk_index, c.text, d.filename"
                f" FROM chunks c JOIN documents d ON d.id = c.document_id"
                f" WHERE c.id IN ({marks})",
                chunk_ids,
            ).fetchall()
        return {r["id"]: dict(r) for r in rows}

    def chunk_ids_for_documents(self, doc_ids: list[str]) -> set[int]:
        if not doc_ids:
            return set()
        marks = ",".join("?" * len(doc_ids))
        with self.connect() as con:
            rows = con.execute(
                f"SELECT id FROM chunks WHERE document_id IN ({marks})", doc_ids
            ).fetchall()
        return {r["id"] for r in rows}

    def keyword_search(self, match_query: str, limit: int) -> list[int]:
        """BM25-ranked chunk ids for an FTS5 MATCH expression."""
        if not match_query:
            return []
        with self.connect() as con:
            rows = con.execute(
                "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?"
                " ORDER BY bm25(chunks_fts) LIMIT ?",
                (match_query, limit),
            ).fetchall()
        return [r["rowid"] for r in rows]

    # ---- conversations ---------------------------------------------------

    def create_conversation(self, title: str = "New chat") -> dict:
        conv_id = new_id()
        ts = now()
        with self.connect() as con:
            con.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conv_id, title, ts, ts),
            )
        return self.get_conversation(conv_id)

    def get_conversation(self, conv_id: str) -> dict | None:
        with self.connect() as con:
            row = con.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        return dict(row) if row else None

    def list_conversations(self) -> list[dict]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM conversations ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

    def rename_conversation(self, conv_id: str, title: str) -> None:
        with self.connect() as con:
            con.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))

    def delete_conversation(self, conv_id: str) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        sources: list[dict] | None = None,
        answerable: bool | None = None,
    ) -> dict:
        ts = now()
        with self.connect() as con:
            cur = con.execute(
                "INSERT INTO messages (conversation_id, role, content, sources, answerable,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    conv_id,
                    role,
                    content,
                    json.dumps(sources or []),
                    None if answerable is None else int(answerable),
                    ts,
                ),
            )
            con.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (ts, conv_id))
            msg_id = cur.lastrowid
        return {
            "id": msg_id,
            "conversation_id": conv_id,
            "role": role,
            "content": content,
            "sources": sources or [],
            "answerable": answerable,
            "created_at": ts,
        }

    def list_messages(self, conv_id: str, limit: int | None = None) -> list[dict]:
        sql = "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id"
        params: list = [conv_id]
        if limit:
            sql = (
                "SELECT * FROM (SELECT * FROM messages WHERE conversation_id = ?"
                " ORDER BY id DESC LIMIT ?) ORDER BY id"
            )
            params.append(limit)
        with self.connect() as con:
            rows = con.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["sources"] = json.loads(d["sources"])
            d["answerable"] = None if d["answerable"] is None else bool(d["answerable"])
            out.append(d)
        return out
