"""Hybrid retrieval: vector similarity + BM25 keyword search, fused with
Reciprocal Rank Fusion (RRF)."""

import re
from dataclasses import dataclass, field

from .services import Services

RRF_K = 60

STOPWORDS = frozenset(
    """a an and are as at be been but by can could did do does for from had has have how i if in
    into is it its me my of on or our should so than that the their them then there these they
    this those to was we were what when where which who whom why will with would you your about
    tell give show please any all some much many""".split()
)


@dataclass
class RetrievalResult:
    chunks: list[dict] = field(default_factory=list)
    best_similarity: float = 0.0


def fts_query(question: str) -> str:
    """Turns free text into a safe FTS5 expression: quoted terms joined by OR."""
    seen: list[str] = []
    for token in re.findall(r"[A-Za-z0-9]+", question.lower()):
        if len(token) > 1 and token not in STOPWORDS and token not in seen:
            seen.append(token)
    return " OR ".join(f'"{t}"' for t in seen[:24])


def retrieve(
    services: Services, question: str, document_ids: list[str] | None = None
) -> RetrievalResult:
    settings = services.settings
    if len(services.index) == 0:
        return RetrievalResult()

    allowed = services.db.chunk_ids_for_documents(document_ids) if document_ids else None
    if allowed is not None and not allowed:
        return RetrievalResult()

    query_vector = services.embedder.embed([question])[0]
    vector_hits = services.index.search(query_vector, settings.candidate_k, allowed)
    similarity = dict(vector_hits)

    # Over-fetch keyword hits when a document filter will discard some of them.
    keyword_limit = settings.candidate_k * (5 if allowed is not None else 1)
    keyword_ids = [
        cid
        for cid in services.db.keyword_search(fts_query(question), keyword_limit)
        if allowed is None or cid in allowed
    ][: settings.candidate_k]

    fused: dict[int, float] = {}
    for ranking in ([cid for cid, _ in vector_hits], keyword_ids):
        for rank, cid in enumerate(ranking):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)

    top_ids = sorted(fused, key=fused.get, reverse=True)[: settings.top_k]
    rows = services.db.get_chunks(top_ids)
    chunks = []
    for cid in top_ids:
        row = rows.get(cid)
        if row is None:  # deleted between search and fetch
            continue
        row["score"] = round(fused[cid], 5)
        row["similarity"] = round(similarity[cid], 4) if cid in similarity else None
        chunks.append(row)

    best = max((s for _, s in vector_hits), default=0.0)
    return RetrievalResult(chunks=chunks, best_similarity=best)
