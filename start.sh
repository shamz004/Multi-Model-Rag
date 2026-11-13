#!/usr/bin/env bash
# Folio - one-step local start (macOS / Linux).
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8010}"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env - paste your OpenAI key after OPENAI_API_KEY= and run ./start.sh again."
  exit 1
fi
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm install && npm run build)
fi
echo "Folio is starting on http://localhost:$PORT  (press Ctrl+C to stop)"
exec .venv/bin/python -m uvicorn app.main:create_app --factory --app-dir backend --port "$PORT"
