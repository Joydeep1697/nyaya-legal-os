"""Nova Legal OS — Application Database.

Manages the web-application SQLite database (``nova_app.sqlite3``).
This is separate from the existing classifier/RAG databases and tracks:
  - Vault document state & metadata
  - Chat sessions & messages
  - Knowledge graph edges
  - Extracted entities, clauses, deadlines
  - Compliance gaps & activity log
  - Search analytics
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

from app.config import APP_DB_PATH

# ── Schema ────────────────────────────────────────────────────────

_SCHEMA = """
-- Vault documents (tracks every uploaded PDF through the processing pipeline)
CREATE TABLE IF NOT EXISTS vault_documents (
    id              TEXT PRIMARY KEY,
    filename        TEXT NOT NULL,
    sha256          TEXT,
    file_size       INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'uploading',   -- uploading/extracting/parsing/classifying/entities/clauses/linking/indexing/indexed/failed
    category        TEXT,
    domain          TEXT,
    authority_level TEXT,
    authority_weight REAL DEFAULT 1.0,
    risk_score      INTEGER DEFAULT 0,          -- 0-100
    pages           INTEGER DEFAULT 0,
    clauses_count   INTEGER DEFAULT 0,
    citations_count INTEGER DEFAULT 0,
    summary         TEXT,                       -- AI-generated summary (cached)
    raw_path        TEXT,                       -- path in raw/
    category_path   TEXT,                       -- path in Category/<cat>/
    error_msg       TEXT,
    upload_time     TEXT NOT NULL,
    process_time    TEXT
);

-- Extracted entities (courts, judges, parties, sections, etc.)
CREATE TABLE IF NOT EXISTS document_entities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id          TEXT NOT NULL REFERENCES vault_documents(id) ON DELETE CASCADE,
    entity_type     TEXT NOT NULL,              -- court/judge/party_petitioner/party_respondent/section/rule/article/citation/notification/act_name/year/decision_date/case_number
    entity_value    TEXT NOT NULL,
    context_snippet TEXT
);
CREATE INDEX IF NOT EXISTS idx_entities_doc ON document_entities(doc_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON document_entities(entity_type);

-- Detected legal clauses
CREATE TABLE IF NOT EXISTS document_clauses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id          TEXT NOT NULL REFERENCES vault_documents(id) ON DELETE CASCADE,
    clause_type     TEXT NOT NULL,              -- indemnity/limitation_of_liability/force_majeure/termination/confidentiality/governing_law/arbitration/ip_assignment/non_compete/data_protection
    clause_text     TEXT NOT NULL,
    risk_level      TEXT DEFAULT 'low',         -- low/medium/high
    start_page      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_clauses_doc ON document_clauses(doc_id);

-- Deadlines extracted from documents
CREATE TABLE IF NOT EXISTS document_deadlines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id          TEXT NOT NULL REFERENCES vault_documents(id) ON DELETE CASCADE,
    deadline_type   TEXT NOT NULL,              -- filing/renewal/expiry/limitation/compliance
    deadline_date   TEXT,                       -- ISO date
    description     TEXT,
    status          TEXT DEFAULT 'upcoming'     -- upcoming/overdue/cleared
);
CREATE INDEX IF NOT EXISTS idx_deadlines_doc ON document_deadlines(doc_id);
CREATE INDEX IF NOT EXISTS idx_deadlines_date ON document_deadlines(deadline_date);

-- Knowledge graph edges (citation links between documents)
CREATE TABLE IF NOT EXISTS knowledge_graph (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_doc_id   TEXT NOT NULL REFERENCES vault_documents(id) ON DELETE CASCADE,
    target_doc_id   TEXT REFERENCES vault_documents(id) ON DELETE SET NULL,
    relationship    TEXT NOT NULL,              -- cites/amends/repeals/supersedes/interprets/conflicts_with/applies
    source_ref      TEXT,                       -- e.g. "Section 12 of RTI Act"
    target_ref      TEXT,                       -- matched reference in target doc
    confidence      REAL DEFAULT 0.5
);
CREATE INDEX IF NOT EXISTS idx_kg_source ON knowledge_graph(source_doc_id);
CREATE INDEX IF NOT EXISTS idx_kg_target ON knowledge_graph(target_doc_id);

-- Global section index (all section/rule/article refs across corpus)
CREATE TABLE IF NOT EXISTS section_index (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    section_ref     TEXT NOT NULL,              -- e.g. "Section 302 IPC"
    doc_id          TEXT NOT NULL REFERENCES vault_documents(id) ON DELETE CASCADE,
    context_type    TEXT DEFAULT 'citing',      -- defining/citing/amending/interpreting
    snippet         TEXT
);
CREATE INDEX IF NOT EXISTS idx_sections_ref ON section_index(section_ref);
CREATE INDEX IF NOT EXISTS idx_sections_doc ON section_index(doc_id);

-- Chat sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id              TEXT PRIMARY KEY,
    title           TEXT DEFAULT 'New Conversation',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Chat messages
CREATE TABLE IF NOT EXISTS chat_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,              -- user/assistant/system
    content         TEXT NOT NULL,
    sources_json    TEXT,                       -- JSON array of source objects
    follow_ups_json TEXT,                       -- JSON array of follow-up questions
    reasoning_json  TEXT,                       -- JSON array of reasoning steps
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);

-- Activity log
CREATE TABLE IF NOT EXISTS activity_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action          TEXT NOT NULL,              -- upload/classify/search/chat/scan/error
    detail          TEXT,
    doc_id          TEXT,
    timestamp       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_log(timestamp);

-- Compliance gaps
CREATE TABLE IF NOT EXISTS compliance_gaps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    domain          TEXT NOT NULL,
    gap_description TEXT NOT NULL,
    severity        TEXT DEFAULT 'medium',      -- low/medium/high/critical
    detected_at     TEXT NOT NULL
);

-- Search analytics
CREATE TABLE IF NOT EXISTS search_analytics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    query           TEXT NOT NULL,
    result_count    INTEGER DEFAULT 0,
    timestamp       TEXT NOT NULL
);
"""


# ── Database Manager ──────────────────────────────────────────────

class Database:
    """Thread-safe SQLite database manager for the Nova Legal web app."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or APP_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Vault Documents ───────────────────────────────────────────

    def create_document(self, filename: str, file_size: int, raw_path: str) -> str:
        doc_id = self.new_id()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO vault_documents
                   (id, filename, file_size, status, raw_path, upload_time)
                   VALUES (?, ?, ?, 'uploading', ?, ?)""",
                (doc_id, filename, file_size, raw_path, self.now()),
            )
        self.log_activity("upload", f"Uploaded {filename}", doc_id)
        return doc_id

    def update_document(self, doc_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        cols = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [doc_id]
        with self.connect() as conn:
            conn.execute(f"UPDATE vault_documents SET {cols} WHERE id = ?", vals)

    def get_document(self, doc_id: str) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM vault_documents WHERE id = ?", (doc_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_documents(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        query = "SELECT * FROM vault_documents WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if category:
            query += " AND category = ?"
            params.append(category)
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        query += " ORDER BY upload_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def count_documents(self, status: Optional[str] = None) -> int:
        query = "SELECT COUNT(*) FROM vault_documents"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        with self.connect() as conn:
            return conn.execute(query, params).fetchone()[0]

    def delete_document(self, doc_id: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM vault_documents WHERE id = ?", (doc_id,))
            if cur.rowcount > 0:
                self.log_activity("delete", f"Deleted document {doc_id}", doc_id)
                return True
            return False

    def get_document_stats(self) -> dict:
        with self.connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM vault_documents").fetchone()[0]
            indexed = conn.execute(
                "SELECT COUNT(*) FROM vault_documents WHERE status = 'indexed'"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM vault_documents WHERE status = 'failed'"
            ).fetchone()[0]
            processing = total - indexed - failed
            cats = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM vault_documents WHERE category IS NOT NULL GROUP BY category ORDER BY cnt DESC"
            ).fetchall()
            domains = conn.execute(
                "SELECT domain, COUNT(*) as cnt FROM vault_documents WHERE domain IS NOT NULL GROUP BY domain ORDER BY cnt DESC"
            ).fetchall()
            avg_risk = conn.execute(
                "SELECT AVG(risk_score) FROM vault_documents WHERE risk_score > 0"
            ).fetchone()[0] or 0
            total_pages = conn.execute(
                "SELECT SUM(pages) FROM vault_documents"
            ).fetchone()[0] or 0
            total_clauses = conn.execute(
                "SELECT SUM(clauses_count) FROM vault_documents"
            ).fetchone()[0] or 0
            return {
                "total_documents": total,
                "indexed": indexed,
                "processing": processing,
                "failed": failed,
                "avg_risk_score": round(avg_risk, 1),
                "total_pages": total_pages,
                "total_clauses": total_clauses,
                "categories": {r["category"]: r["cnt"] for r in cats},
                "domains": {r["domain"]: r["cnt"] for r in domains},
            }

    # ── Entities ──────────────────────────────────────────────────

    def add_entities(self, doc_id: str, entities: list[dict]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """INSERT INTO document_entities (doc_id, entity_type, entity_value, context_snippet)
                   VALUES (?, ?, ?, ?)""",
                [(doc_id, e["type"], e["value"], e.get("snippet")) for e in entities],
            )

    def get_entities(self, doc_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM document_entities WHERE doc_id = ?", (doc_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Clauses ───────────────────────────────────────────────────

    def add_clauses(self, doc_id: str, clauses: list[dict]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """INSERT INTO document_clauses (doc_id, clause_type, clause_text, risk_level, start_page)
                   VALUES (?, ?, ?, ?, ?)""",
                [(doc_id, c["type"], c["text"], c.get("risk", "low"), c.get("page")) for c in clauses],
            )

    def get_clauses(self, doc_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM document_clauses WHERE doc_id = ?", (doc_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Deadlines ─────────────────────────────────────────────────

    def add_deadlines(self, doc_id: str, deadlines: list[dict]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """INSERT INTO document_deadlines (doc_id, deadline_type, deadline_date, description, status)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (doc_id, d["type"], d.get("date"), d.get("description"), d.get("status", "upcoming"))
                    for d in deadlines
                ],
            )

    def get_deadlines(self, status: Optional[str] = None, doc_id: Optional[str] = None) -> list[dict]:
        query = "SELECT d.*, v.filename FROM document_deadlines d JOIN vault_documents v ON d.doc_id = v.id WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND d.status = ?"
            params.append(status)
        if doc_id:
            query += " AND d.doc_id = ?"
            params.append(doc_id)
        query += " ORDER BY d.deadline_date ASC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ── Knowledge Graph ───────────────────────────────────────────

    def add_graph_edge(self, source_id: str, target_id: Optional[str], relationship: str,
                       source_ref: str = "", target_ref: str = "", confidence: float = 0.5) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO knowledge_graph (source_doc_id, target_doc_id, relationship, source_ref, target_ref, confidence)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (source_id, target_id, relationship, source_ref, target_ref, confidence),
            )

    def get_document_links(self, doc_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT kg.*, v.filename as target_filename
                   FROM knowledge_graph kg
                   LEFT JOIN vault_documents v ON kg.target_doc_id = v.id
                   WHERE kg.source_doc_id = ? OR kg.target_doc_id = ?""",
                (doc_id, doc_id),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_full_graph(self) -> dict:
        with self.connect() as conn:
            nodes = conn.execute(
                "SELECT id, filename, category, domain, risk_score FROM vault_documents WHERE status = 'indexed'"
            ).fetchall()
            edges = conn.execute(
                "SELECT source_doc_id, target_doc_id, relationship, confidence FROM knowledge_graph"
            ).fetchall()
            return {
                "nodes": [dict(n) for n in nodes],
                "edges": [dict(e) for e in edges],
            }

    # ── Section Index ─────────────────────────────────────────────

    def add_section_entries(self, doc_id: str, entries: list[dict]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """INSERT INTO section_index (section_ref, doc_id, context_type, snippet)
                   VALUES (?, ?, ?, ?)""",
                [(e["ref"], doc_id, e.get("context_type", "citing"), e.get("snippet")) for e in entries],
            )

    def search_section(self, ref: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT si.*, v.filename, v.category
                   FROM section_index si
                   JOIN vault_documents v ON si.doc_id = v.id
                   WHERE si.section_ref LIKE ?
                   ORDER BY si.context_type""",
                (f"%{ref}%",),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Chat Sessions ─────────────────────────────────────────────

    def create_chat_session(self, title: str = "New Conversation") -> str:
        session_id = self.new_id()
        now = self.now()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO chat_sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now),
            )
        return session_id

    def list_chat_sessions(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_sessions ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_chat_messages(self, session_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["sources"] = json.loads(d["sources_json"]) if d["sources_json"] else []
                d["follow_ups"] = json.loads(d["follow_ups_json"]) if d["follow_ups_json"] else []
                d["reasoning_steps"] = json.loads(d["reasoning_json"]) if d["reasoning_json"] else []
                result.append(d)
            return result

    def add_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[list] = None,
        follow_ups: Optional[list] = None,
        reasoning_steps: Optional[list] = None,
    ) -> int:
        now = self.now()
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO chat_messages
                   (session_id, role, content, sources_json, follow_ups_json, reasoning_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id, role, content,
                    json.dumps(sources) if sources else None,
                    json.dumps(follow_ups) if follow_ups else None,
                    json.dumps(reasoning_steps) if reasoning_steps else None,
                    now,
                ),
            )
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ?, title = CASE WHEN title = 'New Conversation' THEN ? ELSE title END WHERE id = ?",
                (now, content[:60] + "..." if len(content) > 60 else content, session_id),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def delete_chat_session(self, session_id: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
            return cur.rowcount > 0

    # ── Activity Log ──────────────────────────────────────────────

    def log_activity(self, action: str, detail: str = "", doc_id: Optional[str] = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO activity_log (action, detail, doc_id, timestamp) VALUES (?, ?, ?, ?)",
                (action, detail, doc_id, self.now()),
            )

    def get_recent_activity(self, limit: int = 20) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Compliance Gaps ───────────────────────────────────────────

    def add_compliance_gap(self, domain: str, description: str, severity: str = "medium") -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO compliance_gaps (domain, gap_description, severity, detected_at) VALUES (?, ?, ?, ?)",
                (domain, description, severity, self.now()),
            )

    def get_compliance_gaps(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM compliance_gaps ORDER BY detected_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Search Analytics ──────────────────────────────────────────

    def log_search(self, query: str, result_count: int) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO search_analytics (query, result_count, timestamp) VALUES (?, ?, ?)",
                (query, result_count, self.now()),
            )


# ── Singleton ─────────────────────────────────────────────────────

_db: Optional[Database] = None


def get_db() -> Database:
    """Get or create the singleton Database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db
