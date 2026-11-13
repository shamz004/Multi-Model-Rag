import numpy as np
import pytest

from app.chat import build_messages, strip_citations
from app.index import VectorIndex
from app.pdf import chunk_pages, chunk_text, clean_text, parse_pdf
from app.retrieval import fts_query

from .conftest import make_pdf


# ---- PDF parsing and chunking -------------------------------------------


def test_clean_text_joins_wrapped_lines_and_hyphenation():
    raw = "Total reve-\nnue grew\nstrongly.\n\nSecond   paragraph."
    assert clean_text(raw) == "Total revenue grew strongly.\n\nSecond paragraph."


def test_parse_pdf_returns_one_entry_per_page_with_page_numbers(tmp_path):
    path = tmp_path / "doc.pdf"
    path.write_bytes(make_pdf(["First page text.", "", "Third page text."]))
    pages = parse_pdf(path)
    assert [p["page"] for p in pages] == [1, 2, 3]
    assert "First page" in pages[0]["text"]
    assert pages[1]["text"] == ""
    assert "Third page" in pages[2]["text"]


def test_chunk_text_respects_size_and_overlaps():
    sentences = [f"Sentence number {i} talks about topic {i}." for i in range(40)]
    chunks = chunk_text(" ".join(sentences), size=200, overlap=60)
    assert len(chunks) > 3
    assert all(len(c) <= 200 for c in chunks)
    # Consecutive chunks share at least one sentence.
    for first, second in zip(chunks, chunks[1:]):
        assert first.split(". ")[-1].rstrip(".") in second
    # Nothing is lost.
    for sentence in sentences:
        assert any(sentence in c for c in chunks)


def test_chunk_text_splits_a_single_oversized_sentence():
    chunks = chunk_text("word " * 500, size=120, overlap=20)
    assert all(len(c) <= 120 for c in chunks)
    assert sum(c.count("word") for c in chunks) == 500


def test_chunk_pages_keeps_page_numbers_and_skips_empty_pages():
    pages = [{"page": 1, "text": "Alpha."}, {"page": 2, "text": ""}, {"page": 3, "text": "Gamma."}]
    chunks = chunk_pages(pages, size=100, overlap=10)
    assert [(c["page"], c["chunk_index"], c["text"]) for c in chunks] == [
        (1, 0, "Alpha."),
        (3, 1, "Gamma."),
    ]


# ---- vector index --------------------------------------------------------


def unit(*values):
    v = np.array(values, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_index_search_ranks_by_cosine_similarity():
    index = VectorIndex()
    index.add([10, 20, 30], np.vstack([unit(1, 0, 0), unit(0, 1, 0), unit(1, 1, 0)]))
    hits = index.search(unit(1, 0.1, 0), k=2)
    assert [cid for cid, _ in hits] == [10, 30]
    assert hits[0][1] > hits[1][1] > 0


def test_index_remove_and_allowed_filter():
    index = VectorIndex()
    index.add([1, 2, 3], np.vstack([unit(1, 0), unit(0.9, 0.1), unit(0, 1)]))
    assert [cid for cid, _ in index.search(unit(1, 0), k=3, allowed={2, 3})] == [2, 3]
    assert index.search(unit(1, 0), k=3, allowed={99}) == []
    index.remove([1])
    assert len(index) == 2
    assert [cid for cid, _ in index.search(unit(1, 0), k=5)] == [2, 3]


def test_index_empty_and_dimension_mismatch():
    index = VectorIndex()
    assert index.search(unit(1, 0), k=3) == []
    index.add([1], unit(1, 0).reshape(1, -1))
    with pytest.raises(ValueError, match="embedding model was changed"):
        index.add([2], unit(1, 0, 0).reshape(1, -1))
    with pytest.raises(ValueError, match="embedding model was changed"):
        index.search(unit(1, 0, 0), k=1)


# ---- query and prompt helpers -------------------------------------------


def test_fts_query_is_safe_and_drops_stopwords():
    assert fts_query("What was the revenue in 2024?") == '"revenue" OR "2024"'
    # FTS5 operators and quotes in user input must not reach the MATCH expression.
    assert fts_query('revenue" OR * NEAR( AND -- ;') == '"revenue" OR "near"'
    assert fts_query("?? !!") == ""


def test_strip_citations():
    assert strip_citations("Revenue was $5M [1][2]. Costs fell [3].") == "Revenue was $5M. Costs fell."


def test_build_messages_numbers_sources_and_includes_history():
    chunks = [
        {"filename": "a.pdf", "page": 3, "text": "Alpha fact."},
        {"filename": "b.pdf", "page": 7, "text": "Beta fact."},
    ]
    history = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer [1]"},
    ]
    messages = build_messages(history, "Second question", chunks)
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[2]["content"] == "First answer"
    final = messages[-1]["content"]
    assert "[1] Document: a.pdf | Page 3\nAlpha fact." in final
    assert "[2] Document: b.pdf | Page 7\nBeta fact." in final
    assert final.endswith("Question: Second question")


def test_clean_text_expands_pdf_ligatures():
    assert clean_text("The ﬁnancial proﬁt") == "The financial profit"


def test_renumber_citations_orders_by_first_appearance():
    from app.chat import renumber_citations

    sources = [{"n": n, "chunk_id": 100 + n, "cited": False} for n in (1, 2, 3, 4)]
    text, result = renumber_citations("Guidance was set [3]. It was met [1][3]. Bogus [9].", sources)
    assert text == "Guidance was set [1]. It was met [2][1]. Bogus."
    # Cited sources come first, numbered in reading order; the rest follow.
    assert [(s["chunk_id"], s["n"], s["cited"]) for s in result] == [
        (103, 1, True),
        (101, 2, True),
        (102, 3, False),
        (104, 4, False),
    ]


def test_chunk_text_keeps_paragraph_breaks_as_newlines():
    text = "Revenue by segment\n\nAutomation $276.0 million\n\nLogistics $149.2 million. It grew fast."
    assert chunk_text(text, size=500, overlap=50) == [
        "Revenue by segment\nAutomation $276.0 million\nLogistics $149.2 million. It grew fast."
    ]
