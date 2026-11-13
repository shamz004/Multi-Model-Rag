"""Offline test fixtures. No test here calls OpenAI: the embedder and the LLM
are replaced with deterministic fakes, so the whole pipeline (parsing, chunking,
indexing, hybrid retrieval, guards, memory, API) is exercised without a key."""

import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import pymupdf
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers import normalize  # noqa: E402
from app.retrieval import STOPWORDS  # noqa: E402


class FakeEmbedder:
    """Hashed bag-of-words: texts sharing content words get similar vectors."""

    DIM = 512

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        matrix = np.zeros((len(texts), self.DIM), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                if token in STOPWORDS or len(token) < 2:
                    continue
                token = token.rstrip("s")
                slot = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.DIM
                matrix[row, slot] += 1.0
        return normalize(matrix)


class FakeLLM:
    """Answers by quoting the first source and citing it as [1]."""

    def __init__(self):
        self.stream_calls: list[list[dict]] = []
        self.complete_calls: list[list[dict]] = []
        self.reply: str | None = None  # set to force a specific answer

    def complete(self, messages, model=None):
        self.complete_calls.append(messages)
        content = messages[-1]["content"]
        latest = content.split("Latest message:")[-1].strip()
        previous = re.findall(r"^User: (.*)$", content, flags=re.M)
        return f"{latest} {previous[-1]}" if previous else latest

    def stream(self, messages):
        self.stream_calls.append(messages)
        if self.reply is not None:
            text = self.reply
        else:
            first = re.search(r"\[1\] Document: .*?\n(.*?)(?:\n\n\[2\]|\n\nQuestion:)", messages[-1]["content"], re.S)
            text = f"{first.group(1)[:200]} [1]"
        for index in range(0, len(text), 16):
            yield text[index : index + 16]


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(60, 60, 540, 780), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


FINANCE_PDF = [
    "Aurora Dynamics annual report 2024. Total revenue for 2024 was 471.9 million dollars, "
    "an increase of 14.4 percent over the previous year.",
    "The company employed 2,480 people at year end. The chief financial officer is "
    "Daniel Okafor, who joined in February 2024.",
]
SECURITY_PDF = [
    "Information security policy. Passwords must contain at least 14 characters and "
    "multi-factor authentication is mandatory for all staff.",
    "Critical patches must be installed within 7 days. Backups run daily and are "
    "retained for 35 days.",
]

# PyMuPDF stamps each generated file with a fresh id, so build the bytes once.
FINANCE_BYTES = make_pdf(FINANCE_PDF)
SECURITY_BYTES = make_pdf(SECURITY_PDF)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        openai_api_key="",
        data_dir=tmp_path / "data",
        chunk_size=400,
        chunk_overlap=60,
        min_similarity=0.15,
    )


@pytest.fixture
def embedder():
    return FakeEmbedder()


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def client(settings, embedder, llm):
    with TestClient(create_app(settings, embedder=embedder, llm=llm)) as test_client:
        yield test_client


@pytest.fixture
def loaded(client):
    """A client with the two sample documents uploaded and processed."""
    response = client.post(
        "/api/documents",
        files=[
            ("files", ("finance.pdf", FINANCE_BYTES, "application/pdf")),
            ("files", ("security.pdf", SECURITY_BYTES, "application/pdf")),
        ],
    )
    assert response.status_code == 200, response.text
    docs = {d["filename"]: d for d in client.get("/api/documents").json()}
    assert all(d["status"] == "ready" for d in docs.values()), docs
    client.docs = docs
    return client


def ask(client, question, **extra):
    response = client.post("/api/chat", json={"question": question, "stream": False, **extra})
    assert response.status_code == 200, response.text
    return response.json()
