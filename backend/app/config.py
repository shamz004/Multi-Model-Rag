from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_rewrite_model: str = ""  # empty -> same as chat model
    openai_embedding_model: str = "text-embedding-3-small"

    data_dir: Path = ROOT_DIR / "data"

    # Chunking (characters)
    chunk_size: int = 1200
    chunk_overlap: int = 200

    # Retrieval
    top_k: int = 6
    candidate_k: int = 20
    # Best cosine similarity below this -> "not found in documents", no LLM call.
    min_similarity: float = 0.22

    # Conversation memory: how many previous messages are sent to the model
    history_messages: int = 8

    max_upload_mb: int = 50

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def rewrite_model(self) -> str:
        return self.openai_rewrite_model or self.openai_chat_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
