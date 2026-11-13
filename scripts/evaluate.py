"""End-to-end evaluation against the real OpenAI models.

    python scripts/evaluate.py

Uploads the PDFs in sample_docs/ into a temporary, isolated copy of the system
and asks a fixed set of questions that cover every requirement:

  * direct fact lookup            * cross-document comparison
  * source references             * follow-up questions (conversation memory)
  * information that is NOT in the documents (must be refused)

Each case checks the answer text, whether the right document was cited, and
whether "not found" was reported when it should be. Requires OPENAI_API_KEY.
"""

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

A23 = "Aurora_Dynamics_Annual_Report_2023.pdf"
A24 = "Aurora_Dynamics_Annual_Report_2024.pdf"
SUS = "Aurora_Dynamics_Sustainability_Report_2024.pdf"
SEC = "Aurora_Dynamics_Information_Security_Policy.pdf"

# Each conversation is a list of turns. A turn is:
#   (question, text fragments the answer must contain, documents that must be cited)
# An empty "must contain" list together with answerable=False means it must be refused.
CONVERSATIONS: list[dict] = [
    {
        "name": "Direct fact lookup",
        "independent": True,  # every question starts a new conversation
        "turns": [
            ("What was Aurora Dynamics' total revenue in 2024?", ["471.9"], [A24], True),
            ("What is the minimum password length?", ["14"], [SEC], True),
            ("By what percentage did Scope 1 and 2 emissions fall in 2024?", ["12%"], [SUS], True),
            ("Who is the Chief Information Security Officer?", ["Rahul Menon"], [SEC], True),
        ],
    },
    {
        "name": "Cross-document comparison",
        "turns": [
            (
                "Compare research and development spending in 2023 and 2024.",
                ["46.1", "55.3"],
                [A24],
                True,
            ),
            (
                "The 2023 report gave revenue guidance for 2024. What was it, and was it met?",
                ["450", "465", "471.9"],
                [A23, A24],
                True,
            ),
        ],
    },
    {
        "name": "Conversation memory (follow-up questions)",
        "turns": [
            ("Which company did Aurora Dynamics acquire in 2024?", ["Helix Vision Systems"], [A24], True),
            ("How much did they pay for it?", ["62"], [A24], True),
            ("And where is it based?", ["Tampere"], [A24], True),
        ],
    },
    {
        "name": "Conversation memory (topic carried across turns)",
        "turns": [
            ("How many employees did the company have at the end of 2023?", ["2,140"], [A23], True),
            ("What about 2024?", ["2,480"], [A24], True),
        ],
    },
    {
        "name": "Information not in the documents",
        "turns": [
            ("What is Aurora Dynamics' share price?", [], [], False),
            ("Who won the 2022 football World Cup?", [], [], False),
            ("What is the company's policy on parental leave?", [], [], False),
        ],
    },
]


def main() -> int:
    settings = Settings()
    if not settings.openai_api_key:
        print("OPENAI_API_KEY is empty. Add it to the .env file first.")
        return 1
    pdfs = sorted((ROOT / "sample_docs").glob("*.pdf"))
    if not pdfs:
        print("No PDFs in sample_docs/. Run: python scripts/make_sample_reports.py")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        settings = settings.model_copy(update={"data_dir": Path(tmp)})
        with TestClient(create_app(settings)) as client:
            started = time.time()
            response = client.post(
                "/api/documents",
                files=[("files", (p.name, p.read_bytes(), "application/pdf")) for p in pdfs],
            )
            response.raise_for_status()
            docs = client.get("/api/documents").json()
            failed = [d for d in docs if d["status"] != "ready"]
            if failed:
                print("Ingestion failed:", failed)
                return 1
            print(
                f"Ingested {len(docs)} documents, {sum(d['chunks'] for d in docs)} passages "
                f"in {time.time() - started:.1f}s  "
                f"(chat: {settings.openai_chat_model}, embeddings: {settings.openai_embedding_model})\n"
            )

            passed = total = 0
            for conversation in CONVERSATIONS:
                print(f"== {conversation['name']}")
                conversation_id = None
                for question, must_contain, must_cite, answerable in conversation["turns"]:
                    started = time.time()
                    result = client.post(
                        "/api/chat",
                        json={"question": question, "conversation_id": conversation_id, "stream": False},
                    )
                    result.raise_for_status()
                    body = result.json()
                    conversation_id = (
                        None if conversation.get("independent") else body["conversation"]["id"]
                    )
                    message = body["message"]
                    cited = {s["filename"] for s in message["sources"] if s["cited"]}

                    problems = []
                    if message["answerable"] != answerable:
                        problems.append(f"answerable={message['answerable']}, expected {answerable}")
                    for fragment in must_contain:
                        if fragment.lower() not in message["content"].lower():
                            problems.append(f"answer is missing '{fragment}'")
                    for filename in must_cite:
                        if filename not in cited:
                            problems.append(f"did not cite {filename}")
                    if answerable and not cited:
                        problems.append("answer has no citations")

                    total += 1
                    passed += not problems
                    print(f"  [{'PASS' if not problems else 'FAIL'}] {question}  ({time.time() - started:.1f}s)")
                    if body.get("rewritten_question"):
                        print(f"         understood as: {body['rewritten_question']}")
                    print(f"         answer: {message['content'][:220].replace(chr(10), ' ')}")
                    if cited:
                        pages = sorted(
                            {(s["filename"], s["page"]) for s in message["sources"] if s["cited"]}
                        )
                        print("         cited: " + "; ".join(f"{f} p.{p}" for f, p in pages))
                    for problem in problems:
                        print(f"         !! {problem}")
                print()

    print(f"RESULT: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
