"""Model providers. The rest of the app only depends on the two small
interfaces below, so tests can swap in offline fakes."""

from typing import Iterator, Protocol

import numpy as np


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray:
        """Returns an (n, dim) float32 matrix of L2-normalised vectors."""


class ChatLLM(Protocol):
    def complete(self, messages: list[dict], model: str | None = None) -> str: ...

    def stream(self, messages: list[dict]) -> Iterator[str]: ...


def normalize(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class OpenAIEmbedder:
    BATCH = 64

    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.BATCH):
            batch = texts[start : start + self.BATCH]
            response = self.client.embeddings.create(model=self.model, input=batch)
            vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
        return normalize(np.array(vectors, dtype=np.float32))


class OpenAIChat:
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def complete(self, messages: list[dict], model: str | None = None) -> str:
        response = self.client.chat.completions.create(
            model=model or self.model, messages=messages
        )
        return (response.choices[0].message.content or "").strip()

    def stream(self, messages: list[dict]) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True
        )
        for event in stream:
            if event.choices and event.choices[0].delta.content:
                yield event.choices[0].delta.content


def build_openai_providers(settings) -> tuple[OpenAIEmbedder, OpenAIChat]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, max_retries=4, timeout=120)
    return (
        OpenAIEmbedder(client, settings.openai_embedding_model),
        OpenAIChat(client, settings.openai_chat_model),
    )
