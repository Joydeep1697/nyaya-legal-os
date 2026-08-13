#!/usr/bin/env python3
"""
Nova Legal Classifier
========================

A safe, incremental legal-document organizer and metadata generator.

Main features
-------------
- Scans raw/ recursively for PDFs.
- Copies originals into Category/<category>/ without deleting raw files.
- Detects exact duplicates using SHA-256.
- Extracts PDF text with PyMuPDF.
- Uses Tesseract OCR only for low-text pages.
- Performs transparent rule-based legal classification first.
- Optionally asks an NVIDIA NIM LLM only when classification is uncertain.
- Creates one metadata JSON sidecar beside every categorized PDF.
- Extracts title, year, court, case number, parties, judges, legal domain,
  authority level, section references, citation hints and document language.
- Learns from manual corrections:
    move a PDF from one Category folder to another, then run
    --learn-corrections; the registry and token-feedback database are updated.
- Creates audit reports.
- Performs one run and exits; use Windows Task Scheduler every two hours.

The script never deletes PDFs from raw/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import fitz

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

ROOT = Path(r"D:\Nova Legal\Indian Legal")
DEFAULT_RAW = ROOT / "raw"
DEFAULT_CATEGORY = ROOT / "Category"
DEFAULT_DB = ROOT / "category_registry.sqlite3"
DEFAULT_REPORTS = ROOT / "classification_reports"
DEFAULT_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_MODEL = os.getenv("NVIDIA_CLASSIFIER_MODEL", "")

OCR_MIN_NATIVE_CHARS = 80
MAX_CLASSIFICATION_PAGES = 15
MAX_OCR_PAGES = 10
MAX_TEXT_CHARS = 100_000
DEFAULT_THRESHOLD = 0.62

LOG = logging.getLogger("nova-legal-classifier")


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

CATEGORIES = [
    "constitution_and_constitutional_documents",
    "central_acts",
    "state_acts",
    "amendment_acts",
    "repealing_and_amending_acts",
    "ordinances",
    "bills",
    "rules",
    "regulations",
    "schemes",
    "notifications",
    "circulars",
    "government_orders",
    "office_memoranda",
    "government_guidelines",
    "gazette_publications",
    "supreme_court_judgments",
    "supreme_court_orders",
    "high_court_judgments",
    "high_court_orders",
    "district_court_judgments",
    "district_court_orders",
    "tribunal_decisions",
    "commission_decisions",
    "arbitral_awards",
    "legal_notices",
    "contracts_and_agreements",
    "petitions_and_pleadings",
    "affidavits",
    "legal_opinions",
    "forms_and_schedules",
    "legal_study_material",
    "law_reports_and_journals",
    "recruitment_and_examinations",
    "administrative_documents",
    "unclassified",
]

LEGAL_DOMAINS = [
    "constitutional_law",
    "criminal_law",
    "civil_procedure",
    "company_law",
    "partnership_law",
    "consumer_law",
    "contract_law",
    "property_law",
    "tax_law",
    "labour_and_employment_law",
    "family_law",
    "environmental_law",
    "banking_and_finance_law",
    "securities_law",
    "competition_law",
    "insolvency_and_bankruptcy",
    "intellectual_property_law",
    "information_technology_law",
    "telecommunications_law",
    "electricity_and_energy_law",
    "administrative_law",
    "service_law",
    "education_law",
    "health_law",
    "transport_law",
    "municipal_law",
    "election_law",
    "human_rights",
    "international_law",
    "arbitration_and_mediation",
    "evidence_law",
    "procedural_law",
    "general_or_mixed",
]

AUTHORITY_WEIGHTS = {
    "constitution": 1.35,
    "central_act": 1.25,
    "state_act": 1.20,
    "supreme_court": 1.18,
    "high_court": 1.12,
    "rules": 1.08,
    "regulations": 1.06,
    "tribunal": 1.04,
    "notification": 1.00,
    "circular": 0.95,
    "government_guideline": 0.90,
    "study_material": 0.70,
    "administrative": 0.65,
    "unknown": 0.50,
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class ExtractedDocument:
    text: str
    page_count: int
    native_pages: int
    ocr_pages: int
    warnings: list[str]


@dataclass
class LegalMetadata:
    title: str
    document_category: str
    classification_confidence: float
    classification_method: str
    legal_domain: str
    authority_level: str
    authority_weight: float
    jurisdiction: Optional[str]
    court: Optional[str]
    bench: list[str]
    judges: list[str]
    parties: dict[str, Optional[str]]
    case_number: Optional[str]
    neutral_citation: Optional[str]
    reported_citations: list[str]
    act_name: Optional[str]
    year: Optional[int]
    decision_date: Optional[str]
    notification_number: Optional[str]
    sections: list[str]
    rules: list[str]
    articles: list[str]
    keywords: list[str]
    language: str
    source_filename: str
    sha256: str
    file_size: int
    page_count: int
    native_text_pages: int
    ocr_pages: int
    extraction_warnings: list[str]
    classification_reasons: list[str]
    category_scores: dict[str, float]
    generated_at: str


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def sanitize_filename(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:180] or "document.pdf"


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def stable_file(path: Path, delay: float = 2.0) -> bool:
    try:
        first = (path.stat().st_size, path.stat().st_mtime_ns)
        time.sleep(delay)
        second = (path.stat().st_size, path.stat().st_mtime_ns)
        return first == second and second[0] > 0
    except OSError:
        return False


def iter_pdfs(folder: Path) -> Iterable[Path]:
    if not folder.exists():
        return
    for path in folder.rglob("*.pdf"):
        if path.is_file() and not path.name.startswith("~$"):
            yield path


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False) + "\n")


def append_csv(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def tokenize_feedback_text(text: str) -> list[str]:
    stop = {
        "the", "and", "for", "with", "from", "this", "that", "shall", "into",
        "under", "page", "section", "india", "government", "document", "file",
    }
    tokens = re.findall(r"[a-z][a-z0-9]{2,}", text.lower())
    return [token for token in tokens if token not in stop][:800]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

class Registry:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents(
                sha256 TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                destination_path TEXT,
                category TEXT,
                confidence REAL,
                classification_method TEXT,
                metadata_path TEXT,
                source_filename TEXT,
                title TEXT,
                legal_domain TEXT,
                authority_level TEXT,
                processed_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_files(
                source_path TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS category_feedback(
                token TEXT NOT NULL,
                category TEXT NOT NULL,
                positive_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(token, category)
            );

            CREATE TABLE IF NOT EXISTS corrections(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sha256 TEXT NOT NULL,
                old_category TEXT,
                new_category TEXT NOT NULL,
                corrected_path TEXT NOT NULL,
                corrected_at TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def document(self, digest: str) -> Optional[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM documents WHERE sha256=?", (digest,)
        ).fetchone()

    def save_document(
        self,
        digest: str,
        source: Path,
        destination: Path,
        metadata: LegalMetadata,
    ) -> None:
        now = utc_now()
        metadata_path = destination.with_suffix(destination.suffix + ".metadata.json")
        self.db.execute(
            """
            INSERT OR REPLACE INTO documents(
                sha256,source_path,destination_path,category,confidence,
                classification_method,metadata_path,source_filename,title,
                legal_domain,authority_level,processed_at,last_seen_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                digest,
                str(source),
                str(destination),
                metadata.document_category,
                metadata.classification_confidence,
                metadata.classification_method,
                str(metadata_path),
                source.name,
                metadata.title,
                metadata.legal_domain,
                metadata.authority_level,
                now,
                now,
            ),
        )
        self.db.execute(
            "INSERT OR REPLACE INTO source_files VALUES(?,?,?)",
            (str(source), digest, now),
        )
        self.db.commit()

    def touch(self, source: Path, digest: str) -> None:
        now = utc_now()
        self.db.execute(
            "INSERT OR REPLACE INTO source_files VALUES(?,?,?)",
            (str(source), digest, now),
        )
        self.db.execute(
            "UPDATE documents SET last_seen_at=? WHERE sha256=?",
            (now, digest),
        )
        self.db.commit()

    def feedback_boosts(self, text: str) -> dict[str, float]:
        boosts: dict[str, float] = defaultdict(float)
        tokens = set(tokenize_feedback_text(text))
        if not tokens:
            return boosts
        placeholders = ",".join("?" for _ in tokens)
        rows = self.db.execute(
            f"""
            SELECT token, category, positive_count
            FROM category_feedback
            WHERE token IN ({placeholders})
            """,
            list(tokens),
        ).fetchall()
        for row in rows:
            boosts[row["category"]] += min(4.0, row["positive_count"] * 0.18)
        return dict(boosts)

    def record_correction(
        self,
        digest: str,
        old_category: Optional[str],
        new_category: str,
        path: Path,
        feedback_text: str,
    ) -> None:
        now = utc_now()
        self.db.execute(
            """
            INSERT INTO corrections(
                sha256,old_category,new_category,corrected_path,corrected_at
            ) VALUES(?,?,?,?,?)
            """,
            (digest, old_category, new_category, str(path), now),
        )
        self.db.execute(
            """
            UPDATE documents
            SET category=?, destination_path=?, metadata_path=?, last_seen_at=?
            WHERE sha256=?
            """,
            (
                new_category,
                str(path),
                str(path.with_suffix(path.suffix + ".metadata.json")),
                now,
                digest,
            ),
        )
        for token in set(tokenize_feedback_text(feedback_text)):
            self.db.execute(
                """
                INSERT INTO category_feedback(token,category,positive_count)
                VALUES(?,?,1)
                ON CONFLICT(token,category)
                DO UPDATE SET positive_count=positive_count+1
                """,
                (token, new_category),
            )
        self.db.commit()

    def close(self) -> None:
        self.db.close()


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def configure_ocr(path: Optional[Path]) -> bool:
    if not pytesseract or not Image:
        return False
    if path and path.exists():
        pytesseract.pytesseract.tesseract_cmd = str(path)
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def render_page(page: fitz.Page, dpi: int = 250) -> Any:
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def extract_pdf(
    path: Path,
    ocr_enabled: bool,
    ocr_language: str,
) -> ExtractedDocument:
    warnings: list[str] = []
    parts: list[str] = []
    native_pages = 0
    ocr_pages = 0

    doc = fitz.open(path)
    try:
        page_limit = min(doc.page_count, MAX_CLASSIFICATION_PAGES)
        for index in range(page_limit):
            page = doc[index]
            native = page.get_text("text").strip()
            if len(native) >= OCR_MIN_NATIVE_CHARS:
                native_pages += 1
                parts.append(f"\n--- PAGE {index + 1} ---\n{native}")
                continue

            if ocr_enabled and index < MAX_OCR_PAGES:
                try:
                    image = render_page(page)
                    result = pytesseract.image_to_string(
                        image, lang=ocr_language
                    ).strip()
                    if result:
                        ocr_pages += 1
                        parts.append(f"\n--- PAGE {index + 1} OCR ---\n{result}")
                        continue
                except Exception as exc:
                    warnings.append(f"OCR page {index + 1}: {exc}")

            if native:
                native_pages += 1
                parts.append(f"\n--- PAGE {index + 1} LOW TEXT ---\n{native}")

        if doc.page_count > page_limit:
            warnings.append(
                f"Classification used first {page_limit}/{doc.page_count} pages."
            )
        text = "\n".join(parts)[:MAX_TEXT_CHARS]
        if not text.strip():
            warnings.append("No useful text extracted.")
        return ExtractedDocument(
            text=text,
            page_count=doc.page_count,
            native_pages=native_pages,
            ocr_pages=ocr_pages,
            warnings=warnings,
        )
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

def title_from_text(text: str, filename: str) -> str:
    bad = {"contents", "index", "table of contents", "preface"}
    lines = [
        normalize_space(line)
        for line in text.splitlines()
        if line.strip() and not line.startswith("--- PAGE")
    ]
    candidates = [
        line for line in lines[:60]
        if line.lower() not in bad and 8 <= len(line) <= 220
    ]
    return candidates[0] if candidates else Path(filename).stem


def extract_year(text: str, filename: str) -> Optional[int]:
    values = re.findall(
        r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b",
        f"{filename}\n{text[:20_000]}",
    )
    if not values:
        return None
    return Counter(map(int, values)).most_common(1)[0][0]


def extract_case_number(text: str) -> Optional[str]:
    patterns = [
        r"\b(?:W\.?P\.?|C\.?R\.?L\.?|CRL\.?A\.?|CIVIL APPEAL|SLP|SPECIAL LEAVE PETITION|FAO|RFA|LPA|OA|MA|TA|CP|CA)\s*(?:\([A-Z]+\))?\s*(?:NO\.?)?\s*[\w./()\-]+\s*(?:OF|/)\s*\d{4}\b",
        r"\bCASE\s+NO\.?\s*[:\-]?\s*[\w./()\-]+\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return normalize_space(match.group())
    return None


def extract_court(text: str) -> Optional[str]:
    upper = text[:30_000].upper()
    patterns = [
        ("Supreme Court of India", r"IN THE SUPREME COURT|SUPREME COURT OF INDIA"),
        ("High Court", r"IN THE HIGH COURT OF|HIGH COURT OF [A-Z ]+"),
        ("District Court", r"DISTRICT COURT|COURT OF THE DISTRICT JUDGE|SESSIONS COURT"),
        ("NCLT", r"NATIONAL COMPANY LAW TRIBUNAL|\bNCLT\b"),
        ("NCLAT", r"NATIONAL COMPANY LAW APPELLATE TRIBUNAL|\bNCLAT\b"),
        ("Tribunal", r"\bAPPELLATE TRIBUNAL\b|\bTRIBUNAL\b"),
        ("Commission", r"\bCOMMISSION\b"),
    ]
    for name, pattern in patterns:
        if re.search(pattern, upper):
            return name
    return None


def extract_sections(text: str) -> list[str]:
    values = re.findall(
        r"\bsections?\s+(\d+[A-Z]?(?:\([a-z0-9]+\))?)",
        text,
        re.I,
    )
    return list(dict.fromkeys(value.upper() for value in values))[:100]


def extract_rules(text: str) -> list[str]:
    values = re.findall(r"\brules?\s+(\d+[A-Z]?(?:\([a-z0-9]+\))?)", text, re.I)
    return list(dict.fromkeys(value.upper() for value in values))[:100]


def extract_articles(text: str) -> list[str]:
    values = re.findall(r"\barticles?\s+(\d+[A-Z]?(?:\([a-z0-9]+\))?)", text, re.I)
    return list(dict.fromkeys(value.upper() for value in values))[:100]


def extract_dates(text: str) -> Optional[str]:
    patterns = [
        r"\b(?:DECIDED|PRONOUNCED|DATED|DATE OF DECISION)\s*(?:ON|:|-)?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        r"\b(\d{1,2}\s+(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+\d{4})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text[:40_000], re.I)
        if match:
            return normalize_space(match.group(1))
    return None


def extract_judges(text: str) -> list[str]:
    results: list[str] = []
    for pattern in [
        r"\bHON['’]?BLE\s+(?:MR\.?|MS\.?|MRS\.?)?\s*JUSTICE\s+([A-Z][A-Z .'-]{3,80})",
        r"\bCORAM\s*:\s*([A-Z][A-Z .,'&\n-]{3,250})",
    ]:
        for match in re.findall(pattern, text[:30_000], re.I):
            value = normalize_space(match)
            if value and value not in results:
                results.append(value)
    return results[:10]


def extract_parties(text: str) -> dict[str, Optional[str]]:
    first = text[:20_000]
    petitioner = None
    respondent = None
    match = re.search(
        r"([A-Z][A-Z .,&'()-]{2,120})\s+\.{2,}\s*(?:PETITIONER|APPELLANT)",
        first,
        re.I,
    )
    if match:
        petitioner = normalize_space(match.group(1))
    match = re.search(
        r"([A-Z][A-Z .,&'()-]{2,120})\s+\.{2,}\s*RESPONDENT",
        first,
        re.I,
    )
    if match:
        respondent = normalize_space(match.group(1))
    return {"petitioner_or_appellant": petitioner, "respondent": respondent}


def extract_citations(text: str) -> tuple[Optional[str], list[str]]:
    neutral = None
    neutral_match = re.search(
        r"\b(?:20\d{2})\s+(?:INSC|SCC OnLine [A-Za-z]+|DHC|BHC|KHC|MHC)\s+\d+\b",
        text,
        re.I,
    )
    if neutral_match:
        neutral = normalize_space(neutral_match.group())
    reported = re.findall(
        r"\b(?:\(\d{4}\)|\d{4})\s+\d+\s+(?:SCC|AIR|SCR|All LJ|DLT)\s+\d+\b",
        text,
        re.I,
    )
    return neutral, list(dict.fromkeys(normalize_space(x) for x in reported))[:20]


def extract_notification_number(text: str) -> Optional[str]:
    match = re.search(
        r"\b(?:S\.O\.|G\.S\.R\.|F\.?\s*NO\.?|NOTIFICATION\s+NO\.?)\s*[:.-]?\s*[A-Z0-9/().-]+",
        text[:30_000],
        re.I,
    )
    return normalize_space(match.group()) if match else None


def language_guess(text: str) -> str:
    devanagari = len(re.findall(r"[\u0900-\u097F]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if devanagari > 100 and latin > 100:
        return "English and Hindi"
    if devanagari > latin:
        return "Hindi"
    return "English"


def keyword_extract(text: str, title: str) -> list[str]:
    tokens = tokenize_feedback_text(f"{title} {text[:25_000]}")
    counts = Counter(tokens)
    return [word for word, _ in counts.most_common(35)]


# ---------------------------------------------------------------------------
# Domain and authority
# ---------------------------------------------------------------------------

DOMAIN_PATTERNS: dict[str, list[str]] = {
    "consumer_law": ["consumer protection", "consumer commission", "unfair trade practice", "product liability"],
    "company_law": ["companies act", "company law", "memorandum of association", "articles of association", "share capital"],
    "partnership_law": ["partnership act", "partnership deed", "partner", "firm"],
    "criminal_law": ["penal code", "bharatiya nyaya", "criminal procedure", "scheduled offence", "accused"],
    "constitutional_law": ["constitution of india", "fundamental rights", "article 14", "article 19", "article 21"],
    "tax_law": ["income tax", "goods and services tax", "gst", "customs act", "taxation"],
    "labour_and_employment_law": ["industrial disputes", "labour", "wages", "employment", "workmen"],
    "family_law": ["marriage act", "divorce", "maintenance", "guardian", "succession"],
    "property_law": ["transfer of property", "registration act", "land acquisition", "tenancy"],
    "contract_law": ["contract act", "sale of goods", "breach of contract", "specific relief"],
    "banking_and_finance_law": ["banking regulation", "reserve bank", "negotiable instruments", "financial institution"],
    "securities_law": ["securities and exchange board", "sebi", "securities contract", "listing obligations"],
    "insolvency_and_bankruptcy": ["insolvency and bankruptcy", "corporate insolvency", "resolution professional"],
    "competition_law": ["competition act", "competition commission", "anti-competitive"],
    "intellectual_property_law": ["copyright", "patent", "trademark", "trade marks"],
    "information_technology_law": ["information technology act", "cyber", "electronic record", "data protection"],
    "environmental_law": ["environment protection", "pollution control", "forest act", "wildlife"],
    "electricity_and_energy_law": ["electricity act", "electricity supply", "energy regulatory"],
    "municipal_law": ["municipal corporation", "municipal council", "municipality"],
    "service_law": ["service rules", "government servant", "promotion", "disciplinary proceedings"],
    "arbitration_and_mediation": ["arbitration and conciliation", "arbitral", "mediation"],
    "evidence_law": ["evidence act", "bharatiya sakshya", "admissibility", "burden of proof"],
}


def detect_domain(text: str, title: str) -> str:
    haystack = f"{title} {text[:50_000]}".lower()
    scores = {
        domain: sum(haystack.count(term) for term in terms)
        for domain, terms in DOMAIN_PATTERNS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general_or_mixed"


def authority_for(category: str) -> tuple[str, float]:
    if category == "constitution_and_constitutional_documents":
        level = "constitution"
    elif category in {"central_acts", "amendment_acts", "repealing_and_amending_acts", "ordinances"}:
        level = "central_act"
    elif category == "state_acts":
        level = "state_act"
    elif category.startswith("supreme_court"):
        level = "supreme_court"
    elif category.startswith("high_court"):
        level = "high_court"
    elif category == "rules":
        level = "rules"
    elif category == "regulations":
        level = "regulations"
    elif category == "tribunal_decisions":
        level = "tribunal"
    elif category == "notifications":
        level = "notification"
    elif category == "circulars":
        level = "circular"
    elif category in {"government_guidelines", "schemes"}:
        level = "government_guideline"
    elif category == "legal_study_material":
        level = "study_material"
    elif category in {"administrative_documents", "recruitment_and_examinations"}:
        level = "administrative"
    else:
        level = "unknown"
    return level, AUTHORITY_WEIGHTS[level]


# ---------------------------------------------------------------------------
# Rule classification
# ---------------------------------------------------------------------------

def add(scores: dict[str, float], reasons: list[str], category: str, amount: float, reason: str) -> None:
    scores[category] += amount
    reasons.append(f"{category}: +{amount:.2f} ({reason})")


def classify_rules(
    filename: str,
    text: str,
    feedback: dict[str, float],
    threshold: float,
) -> tuple[str, float, dict[str, float], list[str]]:
    scores = {category: 0.0 for category in CATEGORIES if category != "unclassified"}
    reasons: list[str] = []
    lower = text.lower()
    upper = text.upper()
    name = filename.lower()

    # Constitution
    if "constitution of india" in lower or "we, the people of india" in lower:
        add(scores, reasons, "constitution_and_constitutional_documents", 10, "constitutional wording")

    # Courts
    if re.search(r"IN THE SUPREME COURT|SUPREME COURT OF INDIA", upper):
        target = "supreme_court_judgments" if "judgment" in lower else "supreme_court_orders"
        add(scores, reasons, target, 10, "Supreme Court heading")
    if re.search(r"IN THE HIGH COURT OF|HIGH COURT OF [A-Z ]+", upper):
        target = "high_court_judgments" if "judgment" in lower or "judgement" in lower else "high_court_orders"
        add(scores, reasons, target, 9, "High Court heading")
    if re.search(r"DISTRICT COURT|COURT OF THE DISTRICT JUDGE|SESSIONS COURT", upper):
        target = "district_court_judgments" if "judgment" in lower else "district_court_orders"
        add(scores, reasons, target, 8, "District/Sessions Court heading")
    if re.search(r"NCLT|NCLAT|APPELLATE TRIBUNAL|CENTRAL ADMINISTRATIVE TRIBUNAL", upper):
        add(scores, reasons, "tribunal_decisions", 9, "Tribunal heading")
    if "consumer commission" in lower or "consumer disputes redressal commission" in lower:
        add(scores, reasons, "commission_decisions", 8, "Commission heading")

    judicial_hits = sum(
        term in lower for term in [
            "petitioner", "respondent", "appellant", "coram", "pronounced on",
            "reserved on", "learned counsel", "judgment", "ordered accordingly",
        ]
    )
    if judicial_hits >= 3 and max(
        scores["supreme_court_judgments"],
        scores["supreme_court_orders"],
        scores["high_court_judgments"],
        scores["high_court_orders"],
        scores["district_court_judgments"],
        scores["district_court_orders"],
        scores["tribunal_decisions"],
    ) == 0:
        add(scores, reasons, "high_court_orders", judicial_hits * 0.8, "general judicial language")

    # Legislation
    act_hits = sum(
        bool(re.search(pattern, upper))
        for pattern in [
            r"\bAN ACT\b", r"\bACT NO\.?\s*\d+", r"\bBE IT ENACTED\b",
            r"\bARRANGEMENT OF SECTIONS\b", r"\bSHORT TITLE.*COMMENCEMENT\b",
        ]
    )
    if act_hits:
        add(scores, reasons, "central_acts", 3 + 1.5 * act_hits, f"{act_hits} Act signals")
    if re.search(r"\bAMENDMENT ACT\b|\bAMENDMENT\) ACT\b", upper):
        add(scores, reasons, "amendment_acts", 10, "Amendment Act title")
    if "repealing and amending act" in lower:
        add(scores, reasons, "repealing_and_amending_acts", 10, "Repealing and Amending Act")
    if re.search(r"\bSTATE LEGISLATURE\b|\bSTATE ACT\b", upper):
        add(scores, reasons, "state_acts", 7, "state legislation signal")
    if re.search(r"\bORDINANCE\b", upper):
        add(scores, reasons, "ordinances", 9, "Ordinance wording")
    if re.search(r"\bA BILL\b|\bBILL NO\.?\b", upper):
        add(scores, reasons, "bills", 9, "Bill wording")
    if re.search(r"\bTHE .{0,120} RULES,?\s*(18|19|20)\d{2}\b", upper):
        add(scores, reasons, "rules", 10, "formal Rules title")
    if re.search(r"\bTHE .{0,120} REGULATIONS,?\s*(18|19|20)\d{2}\b", upper):
        add(scores, reasons, "regulations", 10, "formal Regulations title")
    if re.search(r"\bSCHEME,?\s*(18|19|20)\d{2}\b", upper):
        add(scores, reasons, "schemes", 8, "formal Scheme title")

    # Executive documents
    if re.search(r"\bNOTIFICATION\b", upper):
        add(scores, reasons, "notifications", 7, "Notification heading")
    if re.search(r"\bS\.O\.\s*\d+|\bG\.S\.R\.\s*\d+", upper):
        add(scores, reasons, "notifications", 4, "notification number")
    if "circular" in lower or "circular" in name:
        add(scores, reasons, "circulars", 8, "Circular wording")
    if re.search(r"\bGOVERNMENT ORDER\b|\bOFFICE ORDER\b", upper):
        add(scores, reasons, "government_orders", 8, "government/office order")
    if re.search(r"\bOFFICE MEMORANDUM\b|\bO\.M\.\s*NO", upper):
        add(scores, reasons, "office_memoranda", 9, "Office Memorandum")
    if re.search(r"\bGUIDELINES?\b|\bSTANDARD OPERATING PROCEDURE\b", upper):
        add(scores, reasons, "government_guidelines", 8, "guideline/SOP")
    gazette_hits = sum(
        token in lower for token in ["gazette of india", "extraordinary", "registered no.", "regd. no."]
    )
    if gazette_hits >= 2:
        add(scores, reasons, "gazette_publications", 3 + gazette_hits, "Gazette signals")

    # Other documents
    if re.search(r"\bARBITRAL AWARD\b|\bSOLE ARBITRATOR\b", upper):
        add(scores, reasons, "arbitral_awards", 9, "arbitral wording")
    if re.search(r"\bLEGAL NOTICE\b", upper):
        add(scores, reasons, "legal_notices", 9, "legal notice")
    if re.search(r"\bAGREEMENT\b|\bMEMORANDUM OF UNDERSTANDING\b", upper):
        add(scores, reasons, "contracts_and_agreements", 6, "agreement/MOU")
    if re.search(r"\bWRIT PETITION\b|\bPETITION UNDER\b|\bPLAINT\b", upper):
        add(scores, reasons, "petitions_and_pleadings", 7, "petition/pleading")
    if re.search(r"\bAFFIDAVIT\b|\bDEPONENT\b", upper):
        add(scores, reasons, "affidavits", 7, "affidavit wording")
    if re.search(r"\bLEGAL OPINION\b|\bOPINION SOUGHT\b", upper):
        add(scores, reasons, "legal_opinions", 8, "legal opinion")
    if re.search(r"\bFORM\s+[A-Z0-9-]+\b|\bSCHEDULE\b", upper):
        add(scores, reasons, "forms_and_schedules", 3, "form/schedule")
    study_hits = sum(
        token in lower
        for token in ["study material", "learning objectives", "multiple choice questions", "practice questions", "lesson"]
    )
    if study_hits >= 2:
        add(scores, reasons, "legal_study_material", 3 + study_hits, "study material signals")
    if re.search(r"\bLAW REPORT\b|\bJOURNAL\b|\bCASE NOTE\b", upper):
        add(scores, reasons, "law_reports_and_journals", 6, "law report/journal")
    recruitment_hits = sum(
        token in lower
        for token in ["recruitment", "vacancy", "admit card", "answer key", "examination", "apply online"]
    )
    if recruitment_hits:
        add(scores, reasons, "recruitment_and_examinations", 3 + 1.8 * recruitment_hits, "recruitment/exam signals")

    # Filename evidence
    filename_map = {
        "act": "central_acts",
        "rules": "rules",
        "regulation": "regulations",
        "notification": "notifications",
        "circular": "circulars",
        "judgment": "high_court_judgments",
        "judgement": "high_court_judgments",
        "ordinance": "ordinances",
        "bill": "bills",
        "affidavit": "affidavits",
        "agreement": "contracts_and_agreements",
    }
    for token, category in filename_map.items():
        if token in name:
            add(scores, reasons, category, 2.5, f"filename contains {token}")

    # Learned manual-feedback boosts
    for category, boost in feedback.items():
        if category in scores and boost > 0:
            add(scores, reasons, category, boost, "learned from prior manual corrections")

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_category, best_score = ranked[0]
    second_score = ranked[1][1]
    if best_score <= 0:
        confidence = 0.0
    else:
        strength = min(1.0, best_score / 10.0)
        separation = max(0.0, min(1.0, (best_score - second_score) / best_score))
        confidence = 0.68 * strength + 0.32 * separation

    final = best_category if confidence >= threshold else "unclassified"
    if final == "unclassified":
        reasons.append(
            f"Confidence {confidence:.3f} below threshold {threshold:.3f}"
        )
    return (
        final,
        round(confidence, 4),
        {key: round(value, 3) for key, value in ranked},
        reasons,
    )


# ---------------------------------------------------------------------------
# NVIDIA fallback
# ---------------------------------------------------------------------------

def classify_with_nvidia(
    filename: str,
    extracted_text: str,
    rule_category: str,
    rule_confidence: float,
    rule_scores: dict[str, float],
    base_url: str,
    model: str,
) -> Optional[dict[str, Any]]:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key or not model:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        LOG.warning("openai package missing; NVIDIA fallback skipped.")
        return None

    allowed_categories = ", ".join(CATEGORIES)
    prompt = f"""
Classify this Indian legal PDF. Return JSON only.

Allowed categories:
{allowed_categories}

Allowed legal domains:
{", ".join(LEGAL_DOMAINS)}

Rules:
- Choose exactly one category from the allowed list.
- If evidence is weak, choose unclassified.
- Do not invent metadata.
- Confidence must be from 0 to 1.
- Provide concise reasons.
- Extract metadata only when visible in the supplied text.

Filename: {filename}
Rule classifier category: {rule_category}
Rule confidence: {rule_confidence}
Top rule scores: {json.dumps(dict(list(rule_scores.items())[:8]))}

Document excerpt:
{extracted_text[:35_000]}

Return this JSON schema:
{{
  "category": "...",
  "confidence": 0.0,
  "legal_domain": "...",
  "title": null,
  "court": null,
  "case_number": null,
  "year": null,
  "act_name": null,
  "reasons": ["..."]
}}
"""
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You classify legal documents. Output valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=900,
    )
    content = response.choices[0].message.content or ""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        LOG.warning("NVIDIA returned non-JSON classification.")
        return None
    if data.get("category") not in CATEGORIES:
        return None
    if data.get("legal_domain") not in LEGAL_DOMAINS:
        data["legal_domain"] = "general_or_mixed"
    return data


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------

class Classifier:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.raw = Path(args.raw).resolve()
        self.category = Path(args.category).resolve()
        self.reports = Path(args.reports).resolve()
        self.registry = Registry(Path(args.database).resolve())
        self.ocr = not args.no_ocr and configure_ocr(
            Path(args.tesseract_cmd).resolve() if args.tesseract_cmd else None
        )
        self.category.mkdir(parents=True, exist_ok=True)
        self.reports.mkdir(parents=True, exist_ok=True)
        for folder in CATEGORIES:
            (self.category / folder).mkdir(parents=True, exist_ok=True)
        self.existing_hashes = self.scan_category_hashes()

    def scan_category_hashes(self) -> dict[str, Path]:
        result: dict[str, Path] = {}
        for path in iter_pdfs(self.category):
            try:
                result.setdefault(sha256_file(path), path)
            except OSError:
                pass
        return result

    def destination(self, source: Path, category: str, digest: str) -> Path:
        candidate = self.category / category / sanitize_filename(source.name)
        if not candidate.exists():
            return candidate
        try:
            if sha256_file(candidate) == digest:
                return candidate
        except OSError:
            pass
        return candidate.with_name(
            f"{candidate.stem}_{digest[:12]}{candidate.suffix}"
        )

    def write_metadata(self, pdf_path: Path, metadata: LegalMetadata) -> Path:
        path = pdf_path.with_suffix(pdf_path.suffix + ".metadata.json")
        path.write_text(
            json.dumps(asdict(metadata), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def build_metadata(
        self,
        source: Path,
        digest: str,
        extraction: ExtractedDocument,
        category: str,
        confidence: float,
        method: str,
        scores: dict[str, float],
        reasons: list[str],
        nvidia_data: Optional[dict[str, Any]],
    ) -> LegalMetadata:
        text = extraction.text
        title = (
            nvidia_data.get("title")
            if nvidia_data and nvidia_data.get("title")
            else title_from_text(text, source.name)
        )
        court = (
            nvidia_data.get("court")
            if nvidia_data and nvidia_data.get("court")
            else extract_court(text)
        )
        case_number = (
            nvidia_data.get("case_number")
            if nvidia_data and nvidia_data.get("case_number")
            else extract_case_number(text)
        )
        year = (
            int(nvidia_data["year"])
            if nvidia_data and str(nvidia_data.get("year", "")).isdigit()
            else extract_year(text, source.name)
        )
        domain = (
            nvidia_data.get("legal_domain")
            if nvidia_data and nvidia_data.get("legal_domain") in LEGAL_DOMAINS
            else detect_domain(text, title)
        )
        neutral, reported = extract_citations(text)
        authority, weight = authority_for(category)
        act_match = re.search(
            r"\bTHE\s+([A-Z][A-Z ,()'-]{3,150}\s+ACT),?\s*(18|19|20)\d{2}\b",
            text[:25_000],
            re.I,
        )
        act_name = (
            nvidia_data.get("act_name")
            if nvidia_data and nvidia_data.get("act_name")
            else normalize_space(act_match.group(0)) if act_match else None
        )

        return LegalMetadata(
            title=title,
            document_category=category,
            classification_confidence=confidence,
            classification_method=method,
            legal_domain=domain,
            authority_level=authority,
            authority_weight=weight,
            jurisdiction="India",
            court=court,
            bench=[],
            judges=extract_judges(text),
            parties=extract_parties(text),
            case_number=case_number,
            neutral_citation=neutral,
            reported_citations=reported,
            act_name=act_name,
            year=year,
            decision_date=extract_dates(text),
            notification_number=extract_notification_number(text),
            sections=extract_sections(text),
            rules=extract_rules(text),
            articles=extract_articles(text),
            keywords=keyword_extract(text, title),
            language=language_guess(text),
            source_filename=source.name,
            sha256=digest,
            file_size=source.stat().st_size,
            page_count=extraction.page_count,
            native_text_pages=extraction.native_pages,
            ocr_pages=extraction.ocr_pages,
            extraction_warnings=extraction.warnings,
            classification_reasons=reasons,
            category_scores=scores,
            generated_at=utc_now(),
        )

    def process(self, source: Path) -> str:
        if not stable_file(source):
            LOG.info("File is still changing; skipping: %s", source)
            return "unstable"

        digest = sha256_file(source)
        existing = self.registry.document(digest)
        if existing:
            destination = Path(existing["destination_path"]) if existing["destination_path"] else None
            # If the categorized copy was manually moved, learning mode handles it.
            if destination and destination.exists():
                self.registry.touch(source, digest)
                LOG.info("Already processed: %s", source.name)
                return "duplicate"

        if digest in self.existing_hashes:
            LOG.info("Already exists in Category: %s", source.name)
            return "duplicate"

        extraction = extract_pdf(
            source,
            ocr_enabled=self.ocr,
            ocr_language=self.args.ocr_language,
        )
        feedback_text = f"{source.name}\n{extraction.text[:20_000]}"
        feedback = self.registry.feedback_boosts(feedback_text)

        category, confidence, scores, reasons = classify_rules(
            source.name,
            extraction.text,
            feedback,
            self.args.confidence_threshold,
        )

        nvidia_data = None
        method = "rules"
        if (
            self.args.use_nvidia_fallback
            and (
                category == "unclassified"
                or confidence < self.args.nvidia_fallback_threshold
            )
        ):
            LOG.info("Using NVIDIA fallback for: %s", source.name)
            nvidia_data = classify_with_nvidia(
                source.name,
                extraction.text,
                category,
                confidence,
                scores,
                self.args.nvidia_base_url,
                self.args.nvidia_model,
            )
            if nvidia_data:
                nvidia_conf = float(nvidia_data.get("confidence", 0.0))
                if (
                    nvidia_data["category"] != "unclassified"
                    and nvidia_conf >= self.args.confidence_threshold
                ):
                    category = nvidia_data["category"]
                    confidence = nvidia_conf
                    method = "rules+nvidia"
                    reasons.extend(
                        [f"NVIDIA: {reason}" for reason in nvidia_data.get("reasons", [])]
                    )

        destination = self.destination(source, category, digest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = destination.with_suffix(destination.suffix + ".part")
            shutil.copy2(source, temporary)
            temporary.replace(destination)

        metadata = self.build_metadata(
            source,
            digest,
            extraction,
            category,
            confidence,
            method,
            scores,
            reasons,
            nvidia_data,
        )
        metadata_path = self.write_metadata(destination, metadata)
        self.registry.save_document(digest, source, destination, metadata)
        self.existing_hashes[digest] = destination

        append_jsonl(self.reports / "classification_manifest.jsonl", asdict(metadata))
        append_csv(
            self.reports / "classified.csv",
            {
                "processed_at": metadata.generated_at,
                "source": str(source),
                "destination": str(destination),
                "category": category,
                "confidence": confidence,
                "method": method,
                "legal_domain": metadata.legal_domain,
                "authority": metadata.authority_level,
                "title": metadata.title,
                "metadata_path": str(metadata_path),
            },
        )
        if category == "unclassified":
            append_csv(
                self.reports / "unclassified.csv",
                {
                    "processed_at": metadata.generated_at,
                    "source": str(source),
                    "confidence": confidence,
                    "top_scores": json.dumps(dict(list(scores.items())[:8])),
                    "warnings": " | ".join(extraction.warnings),
                },
            )

        LOG.info(
            "Classified %-45s -> %-35s %.3f (%s)",
            source.name[:45],
            category,
            confidence,
            method,
        )
        return "classified"

    def learn_corrections(self) -> dict[str, int]:
        """
        Detect PDFs manually moved between Category subfolders.

        The file hash links the moved copy to the prior registry record.
        """
        result = {"scanned": 0, "corrections": 0, "new_unregistered": 0}
        for path in iter_pdfs(self.category):
            result["scanned"] += 1
            digest = sha256_file(path)
            row = self.registry.document(digest)
            new_category = path.parent.name
            if new_category not in CATEGORIES:
                continue
            if not row:
                result["new_unregistered"] += 1
                continue

            old_category = row["category"]
            old_path = row["destination_path"]
            if old_category == new_category and old_path == str(path):
                continue

            metadata_path = path.with_suffix(path.suffix + ".metadata.json")
            title = row["title"] or path.stem
            feedback_text = f"{path.name} {title}"
            if metadata_path.exists():
                try:
                    data = json.loads(metadata_path.read_text(encoding="utf-8"))
                    feedback_text += " " + " ".join(data.get("keywords", []))
                    data["document_category"] = new_category
                    data["classification_method"] = "manual_correction"
                    data["classification_confidence"] = 1.0
                    data["generated_at"] = utc_now()
                    authority, weight = authority_for(new_category)
                    data["authority_level"] = authority
                    data["authority_weight"] = weight
                    metadata_path.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                except Exception as exc:
                    LOG.warning("Could not update metadata for %s: %s", path, exc)

            self.registry.record_correction(
                digest,
                old_category,
                new_category,
                path,
                feedback_text,
            )
            append_csv(
                self.reports / "manual_corrections.csv",
                {
                    "corrected_at": utc_now(),
                    "sha256": digest,
                    "old_category": old_category,
                    "new_category": new_category,
                    "path": str(path),
                },
            )
            result["corrections"] += 1
            LOG.info(
                "Learned manual correction: %s -> %s (%s)",
                old_category,
                new_category,
                path.name,
            )
        return result

    def run(self) -> dict[str, int]:
        if not self.raw.exists():
            raise FileNotFoundError(f"Raw folder not found: {self.raw}")
        summary = {
            "found": 0,
            "classified": 0,
            "duplicate": 0,
            "unstable": 0,
            "error": 0,
        }
        files = sorted(iter_pdfs(self.raw), key=lambda path: str(path).lower())
        summary["found"] = len(files)
        for source in files:
            try:
                status = self.process(source)
                summary[status] += 1
            except Exception as exc:
                summary["error"] += 1
                LOG.exception("Failed: %s", source)
                append_csv(
                    self.reports / "errors.csv",
                    {
                        "time": utc_now(),
                        "source": str(source),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
        append_jsonl(
            self.reports / "run_history.jsonl",
            {"completed_at": utc_now(), **summary},
        )
        return summary

    def close(self) -> None:
        self.registry.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Nova Legal Classifier")
    p.add_argument("--raw", default=str(DEFAULT_RAW))
    p.add_argument("--category", default=str(DEFAULT_CATEGORY))
    p.add_argument("--database", default=str(DEFAULT_DB))
    p.add_argument("--reports", default=str(DEFAULT_REPORTS))
    p.add_argument("--confidence-threshold", type=float, default=DEFAULT_THRESHOLD)
    p.add_argument("--no-ocr", action="store_true")
    p.add_argument("--ocr-language", default="eng")
    p.add_argument("--tesseract-cmd", default=str(DEFAULT_TESSERACT))
    p.add_argument("--use-nvidia-fallback", action="store_true")
    p.add_argument("--nvidia-base-url", default=DEFAULT_NVIDIA_BASE_URL)
    p.add_argument("--nvidia-model", default=DEFAULT_NVIDIA_MODEL)
    p.add_argument("--nvidia-fallback-threshold", type=float, default=0.76)
    p.add_argument("--learn-corrections", action="store_true")
    p.add_argument("--verbose", action="store_true")
    return p


def main() -> int:
    args = parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    app = Classifier(args)
    try:
        if args.learn_corrections:
            result = app.learn_corrections()
            print(json.dumps(result, indent=2))
            return 0

        summary = app.run()
        print("\nNOVA LEGAL CLASSIFIER")
        print(json.dumps(summary, indent=2))
        return 0 if summary["error"] == 0 else 1
    except Exception:
        LOG.exception("Classifier stopped.")
        return 1
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
