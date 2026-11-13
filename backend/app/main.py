"""FastAPI application. Run from the backend folder:

    uvicorn app.main:create_app --factory --port 8010
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .config import ROOT_DIR, Settings
from .providers import ChatLLM, Embedder
from .services import Services

FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"


def create_app(
    settings: Settings | None = None,
    embedder: Embedder | None = None,
    llm: ChatLLM | None = None,
) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = FastAPI(title="Folio - Multi-Document RAG", version="1.0.0")
    app.state.services = Services(
        settings or Settings(),
        embedder=embedder,
        llm=llm,
        # Only the real app re-reads .env, so a key added later works without a restart.
        reload_settings=Settings if settings is None else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    # Serve the built web UI (frontend/dist) from the same server when it exists.
    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found.")
            candidate = (FRONTEND_DIST / path).resolve()
            if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app
