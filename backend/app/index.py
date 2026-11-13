"""In-memory vector index doing exact cosine-similarity search with NumPy.

SQLite holds the embeddings and is the source of truth; the index is rebuilt
from it on startup. Vectors are L2-normalised, so a dot product is the cosine
similarity. Exact search over a matrix is fast up to a few hundred thousand
chunks, which is well beyond what a set of uploaded reports produces.
"""

import threading

import numpy as np

DIM_ERROR = (
    "Embedding size {got} does not match the existing index ({have}). The embedding "
    "model was changed: delete the data folder and re-upload the documents."
)


class VectorIndex:
    def __init__(self):
        self._lock = threading.Lock()
        self._ids = np.empty(0, dtype=np.int64)
        self._matrix: np.ndarray | None = None

    @property
    def dim(self) -> int | None:
        return None if self._matrix is None else self._matrix.shape[1]

    def __len__(self) -> int:
        return len(self._ids)

    def add(self, ids: list[int], vectors: np.ndarray) -> None:
        if not ids:
            return
        vectors = np.asarray(vectors, dtype=np.float32)
        with self._lock:
            if self._matrix is None or len(self._ids) == 0:
                self._matrix = vectors.copy()
                self._ids = np.asarray(ids, dtype=np.int64)
                return
            if vectors.shape[1] != self.dim:
                raise ValueError(DIM_ERROR.format(got=vectors.shape[1], have=self.dim))
            self._matrix = np.vstack([self._matrix, vectors])
            self._ids = np.concatenate([self._ids, np.asarray(ids, dtype=np.int64)])

    def remove(self, ids: list[int]) -> None:
        if not ids or self._matrix is None:
            return
        with self._lock:
            keep = ~np.isin(self._ids, np.asarray(ids, dtype=np.int64))
            self._ids = self._ids[keep]
            self._matrix = self._matrix[keep]

    def search(
        self, vector: np.ndarray, k: int, allowed: set[int] | None = None
    ) -> list[tuple[int, float]]:
        """Top-k (chunk id, cosine similarity), optionally restricted to `allowed` ids."""
        with self._lock:
            if len(self._ids) == 0:
                return []
            query = np.asarray(vector, dtype=np.float32).reshape(-1)
            if query.shape[0] != self.dim:
                raise ValueError(DIM_ERROR.format(got=query.shape[0], have=self.dim))
            ids, matrix = self._ids, self._matrix
            if allowed is not None:
                mask = np.isin(ids, np.fromiter(allowed, dtype=np.int64, count=len(allowed)))
                ids, matrix = ids[mask], matrix[mask]
                if len(ids) == 0:
                    return []
            scores = matrix @ query
        k = min(k, len(ids))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(ids[i]), float(scores[i])) for i in top]
