"""Wires storage, the vector index and the model providers together."""

from typing import Callable

from .config import Settings
from .db import Database
from .index import VectorIndex
from .providers import ChatLLM, Embedder, build_openai_providers


class ProviderNotConfigured(Exception):
    pass


class Services:
    def __init__(
        self,
        settings: Settings,
        embedder: Embedder | None = None,
        llm: ChatLLM | None = None,
        reload_settings: Callable[[], Settings] | None = None,
    ):
        self.settings = settings
        self._reload_settings = reload_settings
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(settings.db_path)

        # Anything still "processing" at startup was interrupted by a shutdown.
        for doc in self.db.list_documents():
            if doc["status"] == "processing":
                self.db.set_document_status(
                    doc["id"], "failed", "Processing was interrupted. Delete and upload again."
                )

        self.index = VectorIndex()
        ids, matrix = self.db.all_embeddings()
        if ids:
            self.index.add(ids, matrix)

        self._embedder = embedder
        self._llm = llm

    def _ensure_providers(self) -> None:
        if self._embedder is not None and self._llm is not None:
            return
        if not self.settings.openai_api_key and self._reload_settings:
            # Pick up a key added to .env after the server started.
            self.settings = self._reload_settings()
        if not self.settings.openai_api_key:
            raise ProviderNotConfigured(
                "OpenAI API key is not configured. Add OPENAI_API_KEY to the .env file."
            )
        embedder, llm = build_openai_providers(self.settings)
        self._embedder = self._embedder or embedder
        self._llm = self._llm or llm

    @property
    def configured(self) -> bool:
        try:
            self._ensure_providers()
            return True
        except ProviderNotConfigured:
            return False

    @property
    def embedder(self) -> Embedder:
        self._ensure_providers()
        return self._embedder

    @property
    def llm(self) -> ChatLLM:
        self._ensure_providers()
        return self._llm
