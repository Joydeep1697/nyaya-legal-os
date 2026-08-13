#!/usr/bin/env python3
"""Nova Legal hybrid RAG using local FAISS/SQLite and NVIDIA NIM."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
from difflib import get_close_matches
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np

LOG = logging.getLogger("nova-legal-rag")
DEFAULT_EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"
DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_MODEL = os.getenv("NVIDIA_LLM_MODEL", "")
DEFAULT_RERANK_MODEL = os.getenv(
    "NVIDIA_RERANK_MODEL", "nvidia/llama-nemotron-rerank-1b-v2"
)
DEFAULT_RERANK_URL = os.getenv(
    "NVIDIA_RERANK_URL",
    "https://ai.api.nvidia.com/v1/retrieval/"
    "nvidia/llama-nemotron-rerank-1b-v2/reranking",
)
ADMIN_TYPES = {"recruitment", "examinations", "examination", "guides", "guide"}

_RUNTIME_CACHE: dict[str, Any] = {}

PRIMARY_LAW_TYPES = {"acts", "act", "rules", "rule", "notifications", "notification", "circulars", "circular"}
CASE_LAW_TYPES = {"judgments", "judgment", "orders", "order"}


@dataclass
class Chunk:
    row_id: int
    chunk_id: str
    document_id: str
    document_type: str
    title: str
    text: str
    page_start: Optional[int]
    page_end: Optional[int]
    heading: Optional[str]
    court: Optional[str]
    case_number: Optional[str]
    decision_date: Optional[str]
    year: Optional[int]
    sha256: Optional[str]
    source_file: Optional[str]
    stored_pdf: Optional[str]
    warnings: list[str]
    quality_score: float


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_number}")
            yield item


def first(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if data.get(key) not in (None, ""):
            return data[key]
    return default


def integer(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        match = re.search(r"\d+", str(value))
        return int(match.group()) if match else None


def parse_warnings(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        return [part.strip() for part in re.split(r"[;|]", value) if part.strip()]
    return [str(value)]


def clean_document_type(value: Any) -> str:
    return str(value or "unknown").strip().lower().replace(" ", "_")


def build_manifest_map(path: Path) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    if not path.exists():
        LOG.warning("Manifest not found: %s", path)
        return mapping
    for item in read_jsonl(path):
        for key in (
            first(item, "document_id", "doc_id"),
            item.get("sha256"),
            item.get("source_file"),
            item.get("stored_pdf"),
        ):
            if key:
                mapping[str(key)] = item
    return mapping


def resolve_manifest(raw: dict[str, Any], mapping: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for key in (
        first(raw, "document_id", "doc_id"),
        first(raw, "sha256", "source_sha"),
        raw.get("source_file"),
        raw.get("stored_pdf"),
    ):
        if key and str(key) in mapping:
            return mapping[str(key)]
    return {}



def normalized_text_key(text: str) -> str:
    """Conservative normalized key for exact or almost-exact chunk deduplication."""
    value = text.lower()
    value = re.sub(r"[\W_]+", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if len(value) >= 120 else ""


def ocr_noise_score(text: str, title: str = "") -> float:
    """Return 0.0 for clean-looking text and approach 1.0 for noisy OCR."""
    sample = f"{title}\n{text[:2500]}".strip()
    if not sample:
        return 1.0
    chars = len(sample)
    letters = sum(ch.isalpha() for ch in sample)
    digits = sum(ch.isdigit() for ch in sample)
    spaces = sum(ch.isspace() for ch in sample)
    normal = letters + digits + spaces
    symbol_ratio = max(0.0, 1.0 - (normal / max(chars, 1)))
    tokens = re.findall(r"\S+", sample)
    one_char_ratio = sum(
        len(re.sub(r"\W", "", token)) == 1 for token in tokens
    ) / max(len(tokens), 1)
    score = 0.65 * min(symbol_ratio / 0.25, 1.0) + 0.35 * min(one_char_ratio / 0.35, 1.0)
    return max(0.0, min(1.0, score))



LEGAL_QUERY_EXPANSIONS: dict[str, str] = {
    "aoa": "articles of association",
    "moa": "memorandum of association",
    "nia": "national investigation agency",
    "securities premium reserve": "securities premium account section 52 companies act 2013",
    "security premium reserve": "securities premium account section 52 companies act 2013",
    "security premium account": "securities premium account section 52 companies act 2013",
    "partnership deed": "partnership deed Indian Partnership Act 1932 section 13 profit sharing",
    "profit sharing": "profit sharing partners Indian Partnership Act 1932 section 13(b)",
}

COMMON_QUERY_TYPOS: dict[str, str] = {
    "progit": "profit",
    "secuirty": "security",
    "memorundum": "memorandum",
    "assosiation": "association",
    "articals": "articles",
}


def rewrite_legal_query(question: str) -> str:
    rewritten_words: list[str] = []
    for word in question.strip().split():
        bare = re.sub(r"[^a-z]", "", word.lower())
        replacement = COMMON_QUERY_TYPOS.get(bare)
        rewritten_words.append(replacement if replacement else word)

    rewritten = " ".join(rewritten_words)
    lower = rewritten.lower()
    additions: list[str] = []

    for key, expansion in LEGAL_QUERY_EXPANSIONS.items():
        if re.search(rf"\b{re.escape(key)}\b", lower):
            additions.append(expansion)

    if "absence of partnership deed" in lower or (
        "partnership deed" in lower and ("profit" in lower or "loss" in lower)
    ):
        additions.append(
            "Indian Partnership Act 1932 section 13(b) partners share equally "
            "in profits and contribute equally to losses"
        )

    if "securities premium" in lower or "security premium" in lower:
        additions.append(
            "Companies Act 2013 section 52 application of securities premium account"
        )

    if ("aoa" in lower or "articles of association" in lower) and (
        "moa" in lower or "memorandum of association" in lower
    ):
        additions.append(
            "Companies Act 2013 memorandum of association articles of association "
            "sections 2(56) 2(5) 4 5 difference objects scope internal regulations"
        )

    if additions:
        rewritten += " | Legal retrieval expansion: " + " ; ".join(dict.fromkeys(additions))

    return rewritten


def section_reference_terms(question: str) -> list[str]:
    return list(
        dict.fromkeys(
            re.findall(
                r"\bsection\s+\d+[a-z]?(?:\([a-z0-9]+\))?",
                question.lower(),
            )
        )
    )


def query_type_preferences(question: str) -> dict[str, float]:
    """Lightweight legal query routing using multiplicative type boosts."""
    q = question.lower()
    statute_terms = (
        "section", "act", "rule", "rules", "statute", "provision", "powers",
        "power", "defined", "definition", "penalty", "offence", "offense",
        "notification", "circular", "under the law",
    )
    case_terms = (
        "court held", "held that", "judgment", "judgement", "case law",
        "precedent", "ratio", "bench", "appeal", "petitioner", "respondent",
        "what did the court", "decision",
    )
    statute_query = any(term in q for term in statute_terms)
    case_query = any(term in q for term in case_terms)
    boosts: dict[str, float] = {}
    if statute_query and not case_query:
        for dtype in PRIMARY_LAW_TYPES:
            boosts[dtype] = 1.18
        for dtype in CASE_LAW_TYPES:
            boosts[dtype] = 0.88
    elif case_query and not statute_query:
        for dtype in CASE_LAW_TYPES:
            boosts[dtype] = 1.18
        for dtype in PRIMARY_LAW_TYPES:
            boosts[dtype] = 0.94
    return boosts


def quality_score(manifest: dict[str, Any], warnings: list[str], document_type: str) -> float:
    score = 1.0
    warning_text = " ".join(warnings).lower()
    if "very little text extracted" in warning_text:
        score -= 0.75
    if "ocr used on a high proportion" in warning_text:
        score -= 0.15
    if "low confidence" in warning_text or "low-confidence" in warning_text:
        score -= 0.20
    if document_type == "unknown":
        score -= 0.50

    extracted = integer(manifest.get("extracted_characters"))
    if extracted is not None:
        if extracted < 100:
            score -= 0.70
        elif extracted < 1000:
            score -= 0.30
    if integer(manifest.get("chunk_count")) == 0:
        score = 0.0
    return max(0.0, min(1.0, score))


def normalize(raw: dict[str, Any], manifest: dict[str, Any], row_id: int) -> Chunk:
    text = str(first(raw, "text", "content", "chunk_text", default="")).strip()
    sha = first(raw, "sha256", "source_sha", default=manifest.get("sha256"))
    document_id = str(
        first(
            raw,
            "document_id",
            "doc_id",
            default=first(manifest, "document_id", "doc_id", default=""),
        )
    ).strip()
    if not document_id:
        document_id = f"legal:{str(sha)[:24]}" if sha else f"legal:row:{row_id}"

    document_type = clean_document_type(
        first(raw, "document_type", "type", default=manifest.get("document_type"))
    )
    warnings = parse_warnings(first(raw, "warnings", default=manifest.get("warnings", [])))
    page_start = integer(first(raw, "page_start", "page_number", "page"))
    page_end = integer(first(raw, "page_end", default=page_start))

    return Chunk(
        row_id=row_id,
        chunk_id=str(first(raw, "chunk_id", default=f"{document_id}:chunk:{row_id:06d}")),
        document_id=document_id,
        document_type=document_type,
        title=str(first(raw, "title", default=manifest.get("title", "Untitled document"))).strip()
        or "Untitled document",
        text=text,
        page_start=page_start,
        page_end=page_end,
        heading=first(raw, "heading"),
        court=first(raw, "court", default=manifest.get("court")),
        case_number=first(raw, "case_number", default=manifest.get("case_number")),
        decision_date=first(raw, "decision_date", default=manifest.get("decision_date")),
        year=integer(first(raw, "year", default=manifest.get("year"))),
        sha256=sha,
        source_file=first(raw, "source_file", default=manifest.get("source_file")),
        stored_pdf=first(raw, "stored_pdf", default=manifest.get("stored_pdf")),
        warnings=warnings,
        quality_score=quality_score(manifest, warnings, document_type),
    )


def corpus_files(corpus: Path) -> tuple[Path, Path]:
    return corpus / "rag" / "chunks.jsonl", corpus / "reports" / "manifest.jsonl"


def validate_corpus(corpus: Path) -> dict[str, Any]:
    chunks_path, manifest_path = corpus_files(corpus)
    if not chunks_path.exists():
        raise FileNotFoundError(f"Missing chunks file: {chunks_path}")
    chunks = list(read_jsonl(chunks_path))
    manifests = list(read_jsonl(manifest_path)) if manifest_path.exists() else []
    return {
        "corpus": str(corpus),
        "chunk_count": len(chunks),
        "manifest_count": len(manifests),
        "documents_in_chunks": len(
            {str(first(item, "document_id", "doc_id", default="unknown")) for item in chunks}
        ),
        "empty_chunks": sum(
            not str(first(item, "text", "content", "chunk_text", default="")).strip()
            for item in chunks
        ),
        "chunks_without_page": sum(
            first(item, "page_start", "page_number", "page") is None for item in chunks
        ),
    }


def write_database(path: Path, chunks: list[Chunk]) -> None:
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    try:
        db.executescript(
            """
            CREATE TABLE chunks(
                row_id INTEGER PRIMARY KEY,
                chunk_id TEXT UNIQUE NOT NULL,
                document_id TEXT NOT NULL,
                document_type TEXT NOT NULL,
                title TEXT NOT NULL,
                text TEXT NOT NULL,
                page_start INTEGER,
                page_end INTEGER,
                heading TEXT,
                court TEXT,
                case_number TEXT,
                decision_date TEXT,
                year INTEGER,
                sha256 TEXT,
                source_file TEXT,
                stored_pdf TEXT,
                warnings_json TEXT NOT NULL,
                quality_score REAL NOT NULL
            );
            CREATE INDEX idx_type ON chunks(document_type);
            CREATE INDEX idx_year ON chunks(year);
            CREATE INDEX idx_document ON chunks(document_id);
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                title, text, heading, court, case_number,
                content='chunks', content_rowid='row_id', tokenize='unicode61'
            );
            CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid,title,text,heading,court,case_number)
                VALUES(new.row_id,new.title,new.text,new.heading,new.court,new.case_number);
            END;
            """
        )
        db.executemany(
            "INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    c.row_id,
                    c.chunk_id,
                    c.document_id,
                    c.document_type,
                    c.title,
                    c.text,
                    c.page_start,
                    c.page_end,
                    c.heading,
                    c.court,
                    c.case_number,
                    c.decision_date,
                    c.year,
                    c.sha256,
                    c.source_file,
                    c.stored_pdf,
                    json.dumps(c.warnings, ensure_ascii=False),
                    c.quality_score,
                )
                for c in chunks
            ],
        )
        db.commit()
    finally:
        db.close()


def build_index(args: argparse.Namespace) -> None:
    try:
        import faiss
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Install requirements before building the index.") from exc

    corpus = Path(args.corpus).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    chunks_path, manifest_path = corpus_files(corpus)
    if not chunks_path.exists():
        raise FileNotFoundError(chunks_path)

    mapping = build_manifest_map(manifest_path)
    kept: list[Chunk] = []
    excluded: dict[str, int] = {}
    chunk_ids: set[str] = set()

    for raw in read_jsonl(chunks_path):
        chunk = normalize(raw, resolve_manifest(raw, mapping), len(kept))
        reason: Optional[str] = None
        if len(chunk.text) < args.min_chars:
            reason = "short"
        elif chunk.document_type in ADMIN_TYPES and not args.include_admin:
            reason = "administrative"
        elif chunk.document_type == "unknown" and not args.include_unknown:
            reason = "unknown"
        elif chunk.quality_score < 0.50 and not args.include_low_quality:
            reason = "low_quality"
        elif chunk.chunk_id in chunk_ids:
            reason = "duplicate_chunk_id"

        if reason:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        chunk.row_id = len(kept)
        kept.append(chunk)
        chunk_ids.add(chunk.chunk_id)

    if not kept:
        raise RuntimeError("No chunks passed the indexing filters.")

    LOG.info("Embedding %d chunks locally", len(kept))
    model = SentenceTransformer(args.embedding_model)
    vectors = model.encode(
        [chunk.text for chunk in kept],
        batch_size=args.batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype("float32")

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, str(output / "nova_legal.faiss"))
    write_database(output / "nova_legal.sqlite3", kept)

    config = {
        "embedding_model": args.embedding_model,
        "indexed_chunks": len(kept),
        "dimension": int(vectors.shape[1]),
        "excluded": excluded,
        "chunks_sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
    }
    (output / "index_config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    print(json.dumps(config, indent=2))


def load_index(index_dir: Path):
    """Load model and FAISS once per Python process; chat mode then reuses both."""
    try:
        import faiss
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Install requirements first.") from exc

    index_dir = index_dir.resolve()
    cache_key = str(index_dir).lower()
    cached = _RUNTIME_CACHE.get(cache_key)
    if cached is not None:
        return cached

    config = json.loads((index_dir / "index_config.json").read_text(encoding="utf-8"))
    LOG.info("Loading embedding model once for this process: %s", config["embedding_model"])
    model = SentenceTransformer(config["embedding_model"])
    index = faiss.read_index(str(index_dir / "nova_legal.faiss"))
    result = (model, index, index_dir / "nova_legal.sqlite3")
    _RUNTIME_CACHE[cache_key] = result
    return result


def fts_query(question: str) -> str:
    terms = [term for term in re.findall(r"[\w§]+", question) if len(term) > 1]
    return " OR ".join(f'"{term}"' for term in terms[:20])


from functools import lru_cache

@lru_cache(maxsize=512)
def _encode_query_cached(model, question_text: str):
    return model.encode([question_text], normalize_embeddings=True, convert_to_numpy=True).astype("float32")

def local_search(
    question: str,
    index_dir: Path,
    candidates: int = 40,
    document_type: Optional[str] = None,
    year: Optional[int] = None,
    court: Optional[str] = None,
) -> list[dict[str, Any]]:
    model, index, db_path = load_index(index_dir)
    retrieval_question = rewrite_legal_query(question)
    LOG.info("Retrieval query: %s", retrieval_question)
    query_vector = _encode_query_cached(model, retrieval_question)
    distances, positions = index.search(query_vector, min(candidates, index.ntotal))

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        vector_scores: dict[int, float] = {}
        for score, row_id in zip(distances[0], positions[0]):
            row_id = int(row_id)
            if row_id < 0:
                continue
            row = db.execute("SELECT * FROM chunks WHERE row_id=?", (row_id,)).fetchone()
            if not row:
                continue
            if document_type and row["document_type"] != clean_document_type(document_type):
                continue
            if year and row["year"] != year:
                continue
            if court and court.lower() not in (row["court"] or "").lower():
                continue
            vector_scores[row_id] = max(0.0, float(score))

        keyword_scores: dict[int, float] = {}
        query = fts_query(retrieval_question)
        if query:
            conditions: list[str] = []
            params: list[Any] = [query]
            if document_type:
                conditions.append("c.document_type=?")
                params.append(clean_document_type(document_type))
            if year:
                conditions.append("c.year=?")
                params.append(year)
            if court:
                conditions.append("LOWER(COALESCE(c.court,'')) LIKE ?")
                params.append(f"%{court.lower()}%")
            where = " AND " + " AND ".join(conditions) if conditions else ""
            try:
                rows = db.execute(
                    "SELECT c.row_id,bm25(chunks_fts) rank "
                    "FROM chunks_fts JOIN chunks c ON c.row_id=chunks_fts.rowid "
                    f"WHERE chunks_fts MATCH ?{where} ORDER BY rank LIMIT ?",
                    [*params, candidates],
                ).fetchall()
                keyword_scores = {
                    int(row["row_id"]): 1.0 / (1.0 + rank)
                    for rank, row in enumerate(rows)
                }
            except sqlite3.OperationalError as exc:
                LOG.warning("Keyword search failed: %s", exc)

        results: list[dict[str, Any]] = []
        for row_id in set(vector_scores) | set(keyword_scores):
            row = dict(db.execute("SELECT * FROM chunks WHERE row_id=?", (row_id,)).fetchone())
            row["warnings"] = json.loads(row.pop("warnings_json"))
            base_score = (
                0.70 * vector_scores.get(row_id, 0.0)
                + 0.30 * keyword_scores.get(row_id, 0.0)
            )
            type_boosts = query_type_preferences(retrieval_question)
            type_multiplier = type_boosts.get(row["document_type"], 1.0)
            noise = ocr_noise_score(row["text"], row["title"])
            quality_multiplier = 0.55 + 0.45 * float(row["quality_score"])
            noise_multiplier = 1.0 - 0.35 * noise
            row["ocr_noise_score"] = noise
            row["type_multiplier"] = type_multiplier

            requested_sections = section_reference_terms(retrieval_question)
            searchable_text = (
                f"{row['title']} {row['heading'] or ''} {row['text']}"
            ).lower()
            section_multiplier = 1.0
            if requested_sections and any(
                section in searchable_text for section in requested_sections
            ):
                section_multiplier = 1.35

            row["section_multiplier"] = section_multiplier
            row["local_score"] = (
                base_score
                * quality_multiplier
                * noise_multiplier
                * type_multiplier
                * section_multiplier
            )
            results.append(row)
        results.sort(key=lambda item: item["local_score"], reverse=True)
        return results[:candidates]
    finally:
        db.close()


def nvidia_headers() -> dict[str, str]:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY is not set.")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def resolve_rerank_endpoint(base_url: str) -> str:
    """Resolve hosted and self-hosted NVIDIA reranker URLs safely."""
    url = base_url.rstrip("/")

    if url.endswith("/reranking"):
        return url
    if url.endswith("/v1/ranking"):
        return url
    if url.endswith("/v1"):
        return url + "/ranking"
    return url + "/v1/ranking"


def rerank_with_nvidia(
    question: str,
    candidates: list[dict[str, Any]],
    *,
    model: str,
    base_url: str,
    top_k: int,
    timeout: int,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("Install requests to use NVIDIA reranking.") from exc

    valid_candidates = [
        item for item in candidates if str(item.get("text", "")).strip()
    ]
    if not valid_candidates:
        return candidates[:top_k]

    endpoint = resolve_rerank_endpoint(base_url)
    LOG.info("Using NVIDIA reranker endpoint: %s", endpoint)

    payload = {
        "model": model,
        "query": {"text": question},
        "passages": [{"text": item["text"]} for item in valid_candidates],
        "truncate": "END",
    }

    response = requests.post(
        endpoint,
        headers=nvidia_headers(),
        json=payload,
        timeout=timeout,
    )

    if not response.ok:
        raise RuntimeError(
            "NVIDIA reranking failed.\n"
            f"Status: {response.status_code}\n"
            f"Endpoint: {endpoint}\n"
            f"Response: {response.text[:2000]}"
        )

    data = response.json()
    rankings = data.get("rankings") or data.get("data") or data.get("results") or []

    reranked: list[dict[str, Any]] = []
    for entry in rankings:
        index = entry.get("index")
        if index is None:
            index = entry.get("passage_index")
        if index is None:
            continue

        index = int(index)
        if not 0 <= index < len(valid_candidates):
            continue

        item = dict(valid_candidates[index])
        item["rerank_score"] = float(
            entry.get("logit", entry.get("score", entry.get("relevance_score", 0.0)))
        )
        reranked.append(item)

    if not reranked:
        LOG.warning("NVIDIA reranker returned an unrecognized response; using local rank.")
        return candidates[:top_k]

    reranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return reranked[:top_k]


def diversified_top_k(
    items: list[dict[str, Any]],
    top_k: int,
    max_chunks_per_document: int = 2,
) -> list[dict[str, Any]]:
    """Limit repeated documents and remove normalized duplicate chunk text."""
    selected: list[dict[str, Any]] = []
    per_document: dict[str, int] = {}
    seen_text_keys: set[str] = set()

    for item in items:
        doc_id = item["document_id"]
        if per_document.get(doc_id, 0) >= max_chunks_per_document:
            continue
        text_key = normalized_text_key(item.get("text", ""))
        if text_key and text_key in seen_text_keys:
            continue
        selected.append(item)
        per_document[doc_id] = per_document.get(doc_id, 0) + 1
        if text_key:
            seen_text_keys.add(text_key)
        if len(selected) >= top_k:
            break
    return selected


def retrieve(args: argparse.Namespace) -> list[dict[str, Any]]:
    candidates = local_search(
        args.question,
        Path(args.index).resolve(),
        candidates=args.candidates,
        document_type=args.document_type,
        year=args.year,
        court=args.court,
    )
    if args.use_nvidia_reranker:
        candidates = rerank_with_nvidia(
            rewrite_legal_query(args.question),
            candidates,
            model=args.rerank_model,
            base_url=args.rerank_base_url,
            top_k=max(args.top_k * 2, args.top_k),
            timeout=args.timeout,
        )
    return diversified_top_k(candidates, args.top_k, args.max_chunks_per_document)


def citation(item: dict[str, Any], number: int) -> str:
    if item.get("page_start") is None:
        page = "page unavailable"
    elif item.get("page_end") not in (None, item["page_start"]):
        page = f"pp. {item['page_start']}–{item['page_end']}"
    else:
        page = f"p. {item['page_start']}"
    suffix = f" — {item['court']}" if item.get("court") else ""
    return f"[{number}] {item['title']} — {page}{suffix}"


def show_hits(hits: list[dict[str, Any]]) -> None:
    if not hits:
        print("No matching sources found.")
        return
    for number, item in enumerate(hits, 1):
        score = item.get("rerank_score", item.get("local_score", 0.0))
        print(f"\n{citation(item, number)}")
        print(f"Type: {item['document_type']} | Score: {score:.4f} | OCR noise: {item.get('ocr_noise_score', 0.0):.2f}")
        print(item["text"][:1000].strip() + ("…" if len(item["text"]) > 1000 else ""))


def answer_with_nvidia(args: argparse.Namespace, hits: list[dict[str, Any]]) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the openai package first.") from exc

    if not args.nvidia_model:
        raise RuntimeError(
            "No NVIDIA model selected. Set NVIDIA_LLM_MODEL or pass --nvidia-model."
        )

    blocks = []
    used_chars = 0
    for number, item in enumerate(hits, 1):
        block = (
            f"{citation(item, number)}\n"
            f"Document ID: {item['document_id']}\n"
            f"Document type: {item['document_type']}\n"
            f"Case number: {item.get('case_number') or 'Not recorded'}\n"
            f"Source PDF: {item.get('stored_pdf') or item.get('source_file') or 'Not recorded'}\n"
            f"EXCERPT:\n{item['text']}"
        )
        if used_chars + len(block) > args.max_context_chars:
            break
        blocks.append(block)
        used_chars += len(block)

    system = (
        "You are Nova Legal, a legal research assistant. Use only the supplied "
        "source excerpts. Cite every legal or factual claim with the matching "
        "source number such as [1]. Never invent an authority, section, date, "
        "case number, quotation, holding, or procedural fact. Distinguish direct "
        "quotes from summaries. If the supplied sources are insufficient, say so "
        "clearly. Do not present the answer as legal advice. End with exactly: "
        "Research note: Verify the cited original documents before relying on "
        "this answer. This is not legal advice."
    )
    user = (
        "SOURCE EXCERPTS\n================\n"
        + "\n\n".join(blocks)
        + f"\n\nQUESTION\n========\n{args.question}\n\n"
        "Give a direct answer, supporting legal basis, citations, and any limitation."
    )

    client = OpenAI(
        api_key=os.environ["NVIDIA_API_KEY"],
        base_url=args.nvidia_base_url,
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    response = client.chat.completions.create(
        model=args.nvidia_model,
        messages=messages,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    choice = response.choices[0]
    content = choice.message.content or ""
    finish_reason = getattr(choice, "finish_reason", None)

    if finish_reason == "length" and args.auto_continue:
        LOG.warning(
            "Answer reached max_tokens=%s; requesting one continuation.",
            args.max_tokens,
        )
        continuation = client.chat.completions.create(
            model=args.nvidia_model,
            messages=[
                *messages,
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": (
                        "Continue exactly where you stopped. Do not repeat earlier "
                        "content. Complete unfinished sentences, tables, citations, "
                        "limitations, and the required research note."
                    ),
                },
            ],
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        content += "\n" + (continuation.choices[0].message.content or "")

    if not content.strip():
        raise RuntimeError("NVIDIA returned an empty answer.")
    return content


def add_retrieval_arguments(parser: argparse.ArgumentParser, question_required: bool = True) -> None:
    parser.add_argument("--index", required=True)
    parser.add_argument("--question", required=question_required)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidates", type=int, default=60)
    parser.add_argument("--max-chunks-per-document", type=int, default=2)
    parser.add_argument("--document-type")
    parser.add_argument("--year", type=int)
    parser.add_argument("--court")
    parser.add_argument("--use-nvidia-reranker", action="store_true")
    parser.add_argument("--rerank-model", default=DEFAULT_RERANK_MODEL)
    parser.add_argument("--rerank-base-url", default=DEFAULT_RERANK_URL)
    parser.add_argument("--timeout", type=int, default=120)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nova Legal NVIDIA hybrid RAG")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--corpus", required=True)
    validate.add_argument("--save")

    build = sub.add_parser("build")
    build.add_argument("--corpus", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--embedding-model", default=DEFAULT_EMBED_MODEL)
    build.add_argument("--batch-size", type=int, default=16)
    build.add_argument("--min-chars", type=int, default=80)
    build.add_argument("--include-admin", action="store_true")
    build.add_argument("--include-unknown", action="store_true")
    build.add_argument("--include-low-quality", action="store_true")

    search_parser = sub.add_parser("search")
    add_retrieval_arguments(search_parser)

    ask = sub.add_parser("ask")
    add_retrieval_arguments(ask)
    ask.add_argument("--nvidia-model", default=DEFAULT_NVIDIA_MODEL)
    ask.add_argument("--nvidia-base-url", default=DEFAULT_NVIDIA_BASE_URL)
    ask.add_argument("--temperature", type=float, default=0.1)
    ask.add_argument("--max-tokens", type=int, default=3000)
    ask.add_argument("--auto-continue", action=argparse.BooleanOptionalAction, default=True)
    ask.add_argument("--max-context-chars", type=int, default=30000)
    ask.add_argument("--no-llm", action="store_true")

    chat = sub.add_parser("chat")
    add_retrieval_arguments(chat, question_required=False)
    chat.add_argument("--nvidia-model", default=DEFAULT_NVIDIA_MODEL)
    chat.add_argument("--nvidia-base-url", default=DEFAULT_NVIDIA_BASE_URL)
    chat.add_argument("--temperature", type=float, default=0.1)
    chat.add_argument("--max-tokens", type=int, default=3000)
    chat.add_argument("--auto-continue", action=argparse.BooleanOptionalAction, default=True)
    chat.add_argument("--max-context-chars", type=int, default=30000)
    chat.add_argument("--no-llm", action="store_true")

    return parser


def run_question(args: argparse.Namespace) -> None:
    hits = retrieve(args)
    if args.no_llm:
        show_hits(hits)
        return
    if not hits:
        print("No matching sources found.")
        return
    print(answer_with_nvidia(args, hits))
    print("\nRetrieved sources:")
    for number, item in enumerate(hits, 1):
        print(citation(item, number))
        source = item.get("stored_pdf") or item.get("source_file")
        if source:
            print(f"    {source}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    try:
        if args.command == "validate":
            result = validate_corpus(Path(args.corpus).resolve())
            print(json.dumps(result, indent=2))
            if args.save:
                output = Path(args.save).resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        elif args.command == "build":
            build_index(args)
        elif args.command == "search":
            show_hits(retrieve(args))
        elif args.command == "ask":
            run_question(args)
        elif args.command == "chat":
            print("Nova Legal NVIDIA chat. Type exit to stop.")
            while True:
                try:
                    question = input("\nYou: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if question.lower() in {"exit", "quit", "q"}:
                    break
                if not question:
                    continue
                args.question = question
                run_question(args)
        return 0
    except Exception as exc:
        LOG.error("%s", exc)
        if args.verbose:
            LOG.exception("Detailed error")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
