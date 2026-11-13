"""Verifies the OpenAI key and the configured models.

    python scripts/check_openai.py

Prints whether the key works, whether each configured model is available to
the account, and makes one tiny embedding call and one tiny chat call.
The key itself is never printed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import Settings  # noqa: E402


def main() -> int:
    settings = Settings()
    if not settings.openai_api_key:
        print("FAIL  OPENAI_API_KEY is empty. Add it to the .env file.")
        return 1

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, timeout=60)
    try:
        available = {m.id for m in client.models.list()}
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  Could not list models: {type(exc).__name__}: {exc}")
        return 1
    print(f"OK    Key accepted. {len(available)} models available to this account.")

    ok = True
    for label, model in [
        ("chat", settings.openai_chat_model),
        ("rewrite", settings.rewrite_model),
        ("embedding", settings.openai_embedding_model),
    ]:
        present = model in available
        ok &= present
        print(f"{'OK  ' if present else 'FAIL'}  {label} model: {model}")

    try:
        vector = client.embeddings.create(model=settings.openai_embedding_model, input=["hello"])
        print(f"OK    Embedding call works ({len(vector.data[0].embedding)} dimensions).")
        reply = client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        )
        print(f"OK    Chat call works (model replied: {reply.choices[0].message.content!r}).")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"FAIL  Test call failed: {type(exc).__name__}: {exc}")

    if not ok:
        chat_like = sorted(m for m in available if m.startswith(("gpt-", "o")) and "audio" not in m)
        print("\nChat models available to this account:\n  " + "\n  ".join(chat_like[:40]))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
