"""Nova Legal OS — Configuration Management.

Reads environment variables (with .env fallback) and provides
centralized path and LLM configuration for the entire application.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env file if present ─────────────────────────────────────
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)

# Prevent Hugging Face from making slow online network checks
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# ── Base directories ──────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent  # d:\Nova Legal
INDIAN_LEGAL_DIR = Path(
    os.getenv("INDIAN_LEGAL_DIR", str(ROOT_DIR / "Indian Legal"))
)

# Ensure the Indian Legal backend modules are importable
if str(INDIAN_LEGAL_DIR) not in sys.path:
    sys.path.insert(0, str(INDIAN_LEGAL_DIR))

RAW_DIR = Path(os.getenv("RAW_DIR", str(INDIAN_LEGAL_DIR / "raw")))
CORPUS_DIR = Path(os.getenv("CORPUS_DIR", str(INDIAN_LEGAL_DIR / "processed_corpus")))
INDEX_DIR = Path(os.getenv("INDEX_DIR", str(INDIAN_LEGAL_DIR / "nova_rag_index")))
CATEGORY_DIR = Path(os.getenv("CATEGORY_DIR", str(INDIAN_LEGAL_DIR / "Category")))
CLASSIFICATION_REPORTS_DIR = INDIAN_LEGAL_DIR / "classification_reports"
CATEGORY_REGISTRY_DB = INDIAN_LEGAL_DIR / "category_registry.sqlite3"

# ── App database ──────────────────────────────────────────────────

APP_DB_PATH = ROOT_DIR / "app" / "nova_app.sqlite3"

# ── LLM Provider ─────────────────────────────────────────────────

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()  # "ollama" or "nvidia"


def get_llm_client_kwargs() -> dict:
    """Return kwargs for ``openai.OpenAI(...)`` matching the active provider."""
    if LLM_PROVIDER == "nvidia":
        api_key = os.getenv("NVIDIA_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "NVIDIA_API_KEY environment variable is required when LLM_PROVIDER=nvidia"
            )
        return {
            "base_url": os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            "api_key": api_key,
        }
    # Default: Ollama (local)
    return {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "api_key": "ollama",  # Ollama doesn't require a real key
    }


LLM_MODEL = os.getenv("OLLAMA_MODEL", "novelaw") if LLM_PROVIDER == "ollama" else os.getenv("NVIDIA_LLM_MODEL", "")
RERANK_MODEL = os.getenv("NVIDIA_RERANK_MODEL", "nvidia/llama-nemotron-rerank-1b-v2")
RERANK_BASE_URL = os.getenv(
    "NVIDIA_RERANK_URL",
    "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-1b-v2/reranking",
)

# ── OCR ───────────────────────────────────────────────────────────

TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "eng")
OCR_ENABLED = Path(TESSERACT_CMD).exists()

# ── Server ────────────────────────────────────────────────────────

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# ── Embedding model (local, no API needed) ────────────────────────

EMBED_MODEL_NAME = os.getenv(
    "EMBED_MODEL", "sentence-transformers/all-mpnet-base-v2"
)

# ── Static files ──────────────────────────────────────────────────

STATIC_DIR = Path(__file__).resolve().parent / "static"
