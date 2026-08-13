"""Nova Legal OS — FastAPI Application Entry Point.

Creates the FastAPI app, mounts routers, serves the static frontend,
and pre-loads the FAISS index + SentenceTransformer model on startup.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import torch
torch.set_num_threads(1)

from app import config
from app.database import get_db

logger = logging.getLogger("nova-legal-app")

# ── Lifespan — runs once on startup / shutdown ────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: preload models, init DB.  Shutdown: cleanup."""
    import asyncio
    logger.info("Nova Legal OS starting up ...")

    # 1. Initialize the application database (creates tables if needed)
    db = get_db()
    logger.info("Application database ready at %s", config.APP_DB_PATH)

    # 2. Preload FAISS index in background thread (don't block startup)
    def _preload_index():
        index_dir = config.INDEX_DIR
        if (index_dir / "nova_legal.faiss").exists():
            try:
                from nova_legal_rag_nvidia import load_index  # type: ignore[import-untyped]
                _model, _index, _db_path = load_index(index_dir)
                logger.info(
                    "FAISS index loaded: %s vectors, embedding model in memory",
                    _index.ntotal,
                )
            except Exception as exc:
                logger.warning("Could not preload FAISS index: %s", exc)
        else:
            logger.warning("No FAISS index found at %s — search will be unavailable until index is built", index_dir)

    # Launch index loading in background — server starts immediately
    asyncio.get_event_loop().run_in_executor(None, _preload_index)

    # 3. Check LLM availability (non-blocking)
    def _check_llm():
        if config.LLM_PROVIDER == "ollama":
            import requests as _requests
            try:
                resp = _requests.get(config.get_llm_client_kwargs()["base_url"].replace("/v1", "") + "/api/tags", timeout=3)
                models = [m["name"] for m in resp.json().get("models", [])]
                if config.LLM_MODEL in models or any(config.LLM_MODEL in m for m in models):
                    logger.info("Ollama model '%s' available", config.LLM_MODEL)
                else:
                    logger.warning(
                        "Ollama model '%s' not found. Available: %s. AI features will use fallback.",
                        config.LLM_MODEL, models,
                    )
            except Exception:
                logger.warning("Ollama not reachable — AI chat/summary features will be unavailable")
        else:
            if not config.get_llm_client_kwargs().get("api_key"):
                logger.warning("NVIDIA_API_KEY not set — AI features will be unavailable")
            else:
                logger.info("NVIDIA NIM configured with model '%s'", config.LLM_MODEL)

    asyncio.get_event_loop().run_in_executor(None, _check_llm)

    logger.info("OCR available: %s", config.OCR_ENABLED)
    logger.info("Nova Legal OS ready — serving on http://%s:%s", config.HOST, config.PORT)

    yield  # ── app runs here ──

    logger.info("Nova Legal OS shutting down ...")


# ── Create FastAPI app ────────────────────────────────────────────

app = FastAPI(
    title="Nyaya Darshan",
    description="AI-powered Indian Legal Intelligence Operating System — powered by NoveLaw, a fine-tuned Indian Legal LLM",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS (allow all for dev) ──────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount API Routers ─────────────────────────────────────────────

from app.routers import vault, chat, classifier, dashboard, knowledge_graph, proactive  # noqa: E402

app.include_router(vault.router, prefix="/api/vault", tags=["Knowledge Vault"])
app.include_router(chat.router, prefix="/api/chat", tags=["AI Chat"])
app.include_router(classifier.router, prefix="/api/classifier", tags=["Classifier"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(knowledge_graph.router, prefix="/api/graph", tags=["Knowledge Graph"])
app.include_router(proactive.router, prefix="/api/proactive", tags=["Proactive Intelligence"])

# ── Serve Static Frontend ────────────────────────────────────────

STATIC_DIR = config.STATIC_DIR
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the Nyaya Legal OS frontend without browser caching."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(
            str(index),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return {"message": "Nyaya Legal OS API is running. Frontend not found at app/static/index.html"}


@app.get("/health")
async def health_check():
    """Quick health check endpoint."""
    db = get_db()
    return {
        "status": "healthy",
        "llm_provider": config.LLM_PROVIDER,
        "llm_model": config.LLM_MODEL,
        "index_available": (config.INDEX_DIR / "nova_legal.faiss").exists(),
        "ocr_available": config.OCR_ENABLED,
        "documents": db.count_documents(),
    }
