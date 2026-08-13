"""Nova Legal OS — Pydantic Request / Response Models."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Vault Documents ───────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: str
    filename: str
    sha256: Optional[str] = None
    file_size: int = 0
    status: str = "uploading"
    category: Optional[str] = None
    domain: Optional[str] = None
    authority_level: Optional[str] = None
    authority_weight: float = 1.0
    risk_score: int = 0
    pages: int = 0
    clauses_count: int = 0
    citations_count: int = 0
    summary: Optional[str] = None
    upload_time: str = ""
    process_time: Optional[str] = None
    error_msg: Optional[str] = None


class DocumentDetail(DocumentResponse):
    entities: list[EntityItem] = []
    clauses: list[ClauseItem] = []
    deadlines: list[DeadlineItem] = []
    links: list[GraphEdge] = []
    related: list[RelatedDocument] = []


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    message: str = "Upload received — processing started"


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
    offset: int = 0
    limit: int = 100


# ── Entities ──────────────────────────────────────────────────────

class EntityItem(BaseModel):
    entity_type: str
    entity_value: str
    context_snippet: Optional[str] = None


# ── Clauses ───────────────────────────────────────────────────────

class ClauseItem(BaseModel):
    clause_type: str
    clause_text: str
    risk_level: str = "low"
    start_page: Optional[int] = None


# ── Deadlines ─────────────────────────────────────────────────────

class DeadlineItem(BaseModel):
    id: Optional[int] = None
    doc_id: Optional[str] = None
    filename: Optional[str] = None
    deadline_type: str
    deadline_date: Optional[str] = None
    description: Optional[str] = None
    status: str = "upcoming"


# ── Knowledge Graph ───────────────────────────────────────────────

class GraphEdge(BaseModel):
    source_doc_id: str
    target_doc_id: Optional[str] = None
    target_filename: Optional[str] = None
    relationship: str
    source_ref: str = ""
    target_ref: str = ""
    confidence: float = 0.5


class RelatedDocument(BaseModel):
    id: str
    filename: str
    category: Optional[str] = None
    domain: Optional[str] = None
    relationship: str = "related"
    relevance: float = 0.0


class SectionEntry(BaseModel):
    section_ref: str
    doc_id: str
    filename: Optional[str] = None
    category: Optional[str] = None
    context_type: str = "citing"
    snippet: Optional[str] = None


class GraphNetwork(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


# ── Chat ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None
    top_k: int = Field(default=10, ge=1, le=50)
    use_reranker: bool = True


class ChatSource(BaseModel):
    doc_id: Optional[str] = None
    title: str = ""
    pages: str = ""
    section: str = ""
    relevance: float = 0.0
    category: str = ""
    snippet: str = ""


class ReasoningStep(BaseModel):
    step: str
    status: str = "pending"  # pending/active/done/error
    ms: int = 0


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource] = []
    reasoning_steps: list[ReasoningStep] = []
    follow_ups: list[str] = []
    session_id: Optional[str] = None


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ChatMessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    sources: list[dict] = []
    follow_ups: list[str] = []
    reasoning_steps: list[dict] = []
    created_at: str


# ── Search ────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    category: Optional[str] = None
    domain: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    doc_type: Optional[str] = None
    top_k: int = Field(default=20, ge=1, le=100)


class SearchResult(BaseModel):
    doc_id: Optional[str] = None
    title: str = ""
    snippet: str = ""
    relevance: float = 0.0
    category: str = ""
    domain: str = ""
    pages: str = ""
    authority_weight: float = 1.0


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query_expanded: str = ""
    facets: dict[str, dict[str, int]] = {}


# ── Dashboard ─────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_documents: int = 0
    indexed: int = 0
    processing: int = 0
    failed: int = 0
    avg_risk_score: float = 0.0
    total_pages: int = 0
    total_clauses: int = 0
    categories: dict[str, int] = {}
    domains: dict[str, int] = {}


class RiskHeatmapEntry(BaseModel):
    domain: str
    doc_count: int = 0
    avg_risk: float = 0.0
    max_risk: int = 0
    coverage: str = "none"  # none/low/medium/good


class IndexInfo(BaseModel):
    chunk_count: int = 0
    document_count: int = 0
    faiss_size_mb: float = 0.0
    sqlite_size_mb: float = 0.0
    embed_model: str = ""


class TrendPoint(BaseModel):
    date: str
    count: int
    category: str = ""


# ── Classifier ────────────────────────────────────────────────────

class CategoryInfo(BaseModel):
    name: str
    doc_count: int = 0
    domains: list[str] = []


class ClassifyResponse(BaseModel):
    doc_id: str
    category: str
    domain: str
    confidence: float
    authority_level: str
    authority_weight: float


# ── Proactive Intelligence ────────────────────────────────────────

class ComplianceGap(BaseModel):
    domain: str
    gap_description: str
    severity: str = "medium"
    detected_at: str = ""


class StalenessAlert(BaseModel):
    doc_id: str
    filename: str
    issue: str
    referenced_act: str = ""
    severity: str = "medium"


class ContradictionAlert(BaseModel):
    doc_a_id: str
    doc_a_name: str
    doc_b_id: str
    doc_b_name: str
    description: str
    clause_a: str = ""
    clause_b: str = ""
    confidence: float = 0.5


# ── Fix forward references ───────────────────────────────────────
# DocumentDetail references EntityItem, ClauseItem, etc. which are
# defined after it.  Pydantic v2 resolves these automatically, but
# we call model_rebuild() explicitly for safety.

DocumentDetail.model_rebuild()
