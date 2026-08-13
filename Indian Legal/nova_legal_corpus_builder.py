from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import shutil
import sys
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional

try:
    import pymupdf  # PyMuPDF
except ImportError as exc:
    raise SystemExit("Missing PyMuPDF. Install with: pip install pymupdf") from exc

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit("Missing Pillow. Install with: pip install pillow") from exc

try:
    import pytesseract
except ImportError as exc:
    raise SystemExit("Missing pytesseract. Install with: pip install pytesseract") from exc

try:
    from tqdm import tqdm
except ImportError as exc:
    raise SystemExit("Missing tqdm. Install with: pip install tqdm") from exc


LOGGER = logging.getLogger("nova-legal-corpus")

DOCUMENT_RULES: dict[str, tuple[str, ...]] = {
    "acts": (
        r"\bact\b", r"\bacts\b", r"bare act", r"amendment act",
        r"act,?\s+\d{4}", r"act no\.?\s*\d+",
    ),
    "rules": (
        r"\brules?\b", r"regulations?", r"scheme", r"code of procedure",
    ),
    "judgments": (
        r"judg(e)?ment", r"versus", r"\bvs\.?\b", r"petitioner",
        r"respondent", r"coram", r"hon['’]?ble", r"reserved on",
        r"pronounced on", r"neutral citation",
    ),
    "orders": (
        r"\border\b", r"interim order", r"office order", r"order dated",
    ),
    "notifications": (
        r"notification", r"gazette", r"extraordinary", r"s\.o\.\s*\d+",
    ),
    "circulars": (
        r"circular", r"memorandum", r"office memorandum", r"advisory",
    ),
    "recruitment": (
        r"recruitment", r"vacancy", r"application form", r"advertisement",
        r"eligible candidates", r"selection process", r"job notification",
    ),
    "examinations": (
        r"admit card", r"answer key", r"examination", r"exam pattern",
        r"question paper", r"result of", r"syllabus",
    ),
    "guides": (
        r"guide", r"handbook", r"manual", r"frequently asked questions",
        r"faq", r"user manual",
    ),
}

COURT_PATTERNS = (
    r"supreme court of india",
    r"high court of [a-z ]+",
    r"district court[s]? of [a-z ]+",
    r"court of [a-z ]+",
    r"national company law tribunal",
    r"national company law appellate tribunal",
    r"central administrative tribunal",
)

CASE_NUMBER_PATTERNS = (
    r"(?:w\.p\.|wp|writ petition)\s*\(?[a-z.]*\)?\s*no\.?\s*[\w/-]+",
    r"(?:crl\.?\s*m\.?c\.?|crlmm|criminal misc(?:ellaneous)?)\s*no\.?\s*[\w/-]+",
    r"(?:civil appeal|criminal appeal|special leave petition|slp)\s*no\.?\s*[\w/-]+",
    r"(?:bail application|ba)\s*no\.?\s*[\w/-]+",
    r"(?:case|petition|appeal|application)\s*no\.?\s*[\w/-]+",
)

DATE_PATTERNS = (
    r"\b(?:0?[1-9]|[12]\d|3[01])[-/.](?:0?[1-9]|1[0-2])[-/.](?:19|20)\d{2}\b",
    r"\b(?:0?[1-9]|[12]\d|3[01])\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(?:19|20)\d{2}\b",
)

HEADING_RE = re.compile(
    r"^(?:"
    r"(?:chapter|part|schedule|section|article|rule|regulation|annexure|appendix)\s+[\w.-]+"
    r"|\d+(?:\.\d+)*[.)-]?\s+[A-Z]"
    r"|[A-Z][A-Z\s,&()'’/-]{4,}"
    r")$",
    flags=re.IGNORECASE,
)


@dataclass
class PageRecord:
    page_number: int
    text: str
    extraction_method: str
    native_characters: int
    final_characters: int


@dataclass
class DocumentRecord:
    document_id: str
    sha256: str
    source_file: str
    stored_pdf: str
    file_size: int
    page_count: int
    document_type: str
    classification_score: int
    title: str
    year: Optional[int]
    court: Optional[str]
    case_number: Optional[str]
    decision_date: Optional[str]
    used_ocr: bool
    ocr_page_count: int
    native_page_count: int
    extracted_characters: int
    status: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ChunkRecord:
    chunk_id: str
    document_id: str
    document_type: str
    title: str
    page_start: int
    page_end: int
    heading: Optional[str]
    text: str
    token_estimate: int
    sha256: str
    source_file: str
    stored_pdf: str
    court: Optional[str]
    case_number: Optional[str]
    decision_date: Optional[str]
    year: Optional[int]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_name(name: str, max_length: int = 160) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return (cleaned or "document")[:max_length]


def normalise_line(line: str) -> str:
    value = re.sub(r"\s+", " ", line).strip().lower()
    value = re.sub(r"\bpage\s+\d+(?:\s+of\s+\d+)?\b", "page", value)
    value = re.sub(r"\b\d+\b", "#", value)
    return value


def clean_page_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\u00ad", "")
    text = re.sub(r"-\n(?=[a-z])", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_repeated_headers_footers(page_texts: list[str], threshold: float = 0.60) -> list[str]:
    if len(page_texts) < 3:
        return page_texts

    candidates_per_page: list[list[str]] = []
    counts: Counter[str] = Counter()

    for text in page_texts:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidates = lines[:3] + lines[-3:]
        normalised = {normalise_line(line) for line in candidates if len(line) <= 180}
        candidates_per_page.append(candidates)
        counts.update(normalised)

    repeated = {
        line for line, count in counts.items()
        if line and count / len(page_texts) >= threshold
    }

    cleaned_pages: list[str] = []
    for text in page_texts:
        kept: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and normalise_line(stripped) in repeated:
                continue
            if re.fullmatch(r"(?:page\s*)?\d+(?:\s*of\s*\d+)?", stripped, flags=re.IGNORECASE):
                continue
            kept.append(line)
        cleaned_pages.append(clean_page_text("\n".join(kept)))
    return cleaned_pages


def text_quality_score(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(ch.isprintable() for ch in text)
    alnum = sum(ch.isalnum() for ch in text)
    replacement = text.count("�")
    return max(0.0, (printable + alnum) / (2 * len(text)) - replacement / max(1, len(text)))


def page_needs_ocr(text: str, min_chars: int, min_quality: float) -> bool:
    compact = re.sub(r"\s+", "", text)
    return len(compact) < min_chars or text_quality_score(text) < min_quality


def ocr_page(page: pymupdf.Page, dpi: int, language: str) -> str:
    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    mode = "RGB" if pix.n >= 3 else "L"
    image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    return pytesseract.image_to_string(image, lang=language, config="--oem 3 --psm 6")


def extract_pdf(
    path: Path,
    enable_ocr: bool,
    ocr_language: str,
    ocr_dpi: int,
    min_native_chars: int,
    min_quality: float,
    max_pages: Optional[int] = None,
) -> tuple[list[PageRecord], list[str]]:
    warnings: list[str] = []
    page_records: list[PageRecord] = []

    with pymupdf.open(path) as document:
        page_limit = min(len(document), max_pages) if max_pages else len(document)
        for index in range(page_limit):
            page = document[index]
            native = clean_page_text(page.get_text("text", sort=True) or "")
            final_text = native
            method = "native"

            if page_needs_ocr(native, min_native_chars, min_quality):
                if enable_ocr:
                    try:
                        ocr_text = clean_page_text(ocr_page(page, ocr_dpi, ocr_language))
                        if len(re.sub(r"\s+", "", ocr_text)) > len(re.sub(r"\s+", "", native)):
                            final_text = ocr_text
                            method = "ocr"
                        else:
                            method = "native_low_text"
                    except Exception as exc:  # continue processing other pages
                        method = "ocr_failed"
                        warnings.append(f"OCR failed on page {index + 1}: {exc}")
                else:
                    method = "ocr_required"

            page_records.append(
                PageRecord(
                    page_number=index + 1,
                    text=final_text,
                    extraction_method=method,
                    native_characters=len(native),
                    final_characters=len(final_text),
                )
            )

        if max_pages and len(document) > max_pages:
            warnings.append(f"Only first {max_pages} of {len(document)} pages were processed")

    cleaned = remove_repeated_headers_footers([page.text for page in page_records])
    for page, text in zip(page_records, cleaned):
        page.text = text
        page.final_characters = len(text)
    return page_records, warnings


def classify_document(filename: str, sample_text: str) -> tuple[str, int, dict[str, int]]:
    haystack = f"{filename}\n{sample_text[:30000]}".lower()
    scores: dict[str, int] = {}
    for category, patterns in DOCUMENT_RULES.items():
        scores[category] = sum(len(re.findall(pattern, haystack, flags=re.IGNORECASE)) for pattern in patterns)

    if not scores or max(scores.values(), default=0) == 0:
        return "unknown", 0, scores

    category = max(scores, key=scores.get)
    score = scores[category]

    # Judgments usually contain several characteristic fields; prefer them over a single generic "order".
    if scores.get("judgments", 0) >= 3 and scores.get("judgments", 0) >= scores.get("orders", 0):
        category, score = "judgments", scores["judgments"]
    return category, score, scores


def first_match(patterns: Iterable[str], text: str) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return None


def infer_title(filename: str, pages: list[PageRecord]) -> str:
    lines: list[str] = []
    for page in pages[:2]:
        lines.extend(line.strip() for line in page.text.splitlines() if line.strip())
    for line in lines[:30]:
        if 8 <= len(line) <= 180 and not re.fullmatch(r"\d+", line):
            if not re.match(r"^(page|downloaded|http|www\.)", line, flags=re.IGNORECASE):
                return line
    return Path(filename).stem


def infer_metadata(filename: str, pages: list[PageRecord]) -> dict[str, object]:
    sample = "\n".join(page.text for page in pages[:5])[:60000]
    court = first_match(COURT_PATTERNS, sample)
    case_number = first_match(CASE_NUMBER_PATTERNS, sample)
    decision_date = first_match(DATE_PATTERNS, sample)

    year_match = re.search(r"\b(?:19|20)\d{2}\b", f"{filename}\n{sample[:10000]}")
    year = int(year_match.group(0)) if year_match else None

    return {
        "title": infer_title(filename, pages),
        "court": court.title() if court else None,
        "case_number": case_number,
        "decision_date": decision_date,
        "year": year,
    }


def paragraph_units(pages: list[PageRecord]) -> list[tuple[int, Optional[str], str]]:
    units: list[tuple[int, Optional[str], str]] = []
    current_heading: Optional[str] = None

    for page in pages:
        paragraphs = re.split(r"\n\s*\n", page.text)
        for paragraph in paragraphs:
            paragraph = re.sub(r"\s+", " ", paragraph).strip()
            if not paragraph:
                continue
            if len(paragraph) <= 180 and HEADING_RE.match(paragraph):
                current_heading = paragraph
                continue
            units.append((page.page_number, current_heading, paragraph))
    return units


def split_long_text(text: str, maximum: int) -> list[str]:
    if len(text) <= maximum:
        return [text]
    sentences = re.split(r"(?<=[.!?;:])\s+", text)
    output: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > maximum:
            if current:
                output.append(current.strip())
                current = ""
            for start in range(0, len(sentence), maximum):
                output.append(sentence[start:start + maximum].strip())
            continue
        proposed = f"{current} {sentence}".strip()
        if len(proposed) > maximum and current:
            output.append(current.strip())
            current = sentence
        else:
            current = proposed
    if current:
        output.append(current.strip())
    return output


def make_chunks(
    document: DocumentRecord,
    pages: list[PageRecord],
    chunk_chars: int,
    overlap_chars: int,
) -> list[ChunkRecord]:
    units = paragraph_units(pages)
    chunks: list[ChunkRecord] = []
    current_parts: list[str] = []
    current_start: Optional[int] = None
    current_end: Optional[int] = None
    current_heading: Optional[str] = None

    def flush() -> None:
        nonlocal current_parts, current_start, current_end, current_heading
        text = "\n\n".join(current_parts).strip()
        if not text or current_start is None or current_end is None:
            current_parts, current_start, current_end, current_heading = [], None, None, None
            return
        chunk_index = len(chunks) + 1
        chunk_id = f"{document.document_id}:chunk:{chunk_index:05d}"
        chunks.append(
            ChunkRecord(
                chunk_id=chunk_id,
                document_id=document.document_id,
                document_type=document.document_type,
                title=document.title,
                page_start=current_start,
                page_end=current_end,
                heading=current_heading,
                text=text,
                token_estimate=max(1, len(text) // 4),
                sha256=document.sha256,
                source_file=document.source_file,
                stored_pdf=document.stored_pdf,
                court=document.court,
                case_number=document.case_number,
                decision_date=document.decision_date,
                year=document.year,
            )
        )

        overlap = text[-overlap_chars:] if overlap_chars > 0 else ""
        overlap = overlap.partition(" ")[2] if " " in overlap else overlap
        current_parts = [overlap] if overlap else []
        current_start = current_end if overlap else None
        current_heading = current_heading if overlap else None

    for page_number, heading, paragraph in units:
        for piece in split_long_text(paragraph, chunk_chars):
            proposed_length = len("\n\n".join(current_parts + [piece]))
            if current_parts and proposed_length > chunk_chars:
                flush()
            if current_start is None:
                current_start = page_number
            current_end = page_number
            if heading:
                current_heading = heading
            current_parts.append(piece)
    flush()
    return chunks


def discover_pdfs(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.pdf") if path.is_file())


def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if destination_resolved not in target.parents and target != destination_resolved:
                raise ValueError(f"Unsafe ZIP path: {member.filename}")
        archive.extractall(destination)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_completed_ids(manifest_jsonl: Path) -> set[str]:
    completed: set[str] = set()
    if not manifest_jsonl.exists():
        return completed
    with manifest_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
                if row.get("status") == "processed" and row.get("document_id"):
                    completed.add(str(row["document_id"]))
            except json.JSONDecodeError:
                continue
    return completed


def prepare_input(input_path: Path, work_dir: Path) -> Path:
    if input_path.is_dir():
        return input_path
    if input_path.suffix.lower() != ".zip":
        raise ValueError("Input must be a directory or a .zip archive")
    extracted = work_dir / "extracted_input"
    if not extracted.exists() or not any(extracted.iterdir()):
        LOGGER.info("Extracting ZIP to %s", extracted)
        safe_extract_zip(input_path, extracted)
    return extracted


def process_corpus(args: argparse.Namespace) -> None:
    input_path = Path(args.input).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    work = output / "_work"
    reports = output / "reports"
    structured = output / "structured"
    clean_text_dir = output / "clean_text"
    pdf_store = output / "unique_pdfs"
    rag_jsonl = output / "rag" / "chunks.jsonl"
    manifest_jsonl = reports / "manifest.jsonl"

    for directory in (output, work, reports, structured, clean_text_dir, pdf_store, rag_jsonl.parent):
        directory.mkdir(parents=True, exist_ok=True)

    if args.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = args.tesseract_cmd

    source_root = prepare_input(input_path, work)
    pdfs = discover_pdfs(source_root)
    if not pdfs:
        raise SystemExit(f"No PDF files found under {source_root}")

    completed_ids = load_completed_ids(manifest_jsonl) if args.resume else set()
    seen_hashes: dict[str, Path] = {}
    duplicate_rows: list[dict[str, object]] = []
    error_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    manifest_rows: list[dict[str, object]] = []

    LOGGER.info("Found %d PDF files", len(pdfs))

    for source_pdf in tqdm(pdfs, desc="Processing PDFs", unit="pdf"):
        try:
            file_hash = sha256_file(source_pdf)
            document_id = f"legal:{file_hash[:24]}"

            if file_hash in seen_hashes:
                duplicate_rows.append({
                    "duplicate_file": str(source_pdf),
                    "canonical_file": str(seen_hashes[file_hash]),
                    "sha256": file_hash,
                    "reason": "exact_sha256_duplicate",
                })
                continue
            seen_hashes[file_hash] = source_pdf

            if document_id in completed_ids:
                continue

            pages, warnings = extract_pdf(
                source_pdf,
                enable_ocr=not args.no_ocr,
                ocr_language=args.ocr_language,
                ocr_dpi=args.ocr_dpi,
                min_native_chars=args.min_native_chars,
                min_quality=args.min_text_quality,
                max_pages=args.max_pages_per_pdf,
            )

            sample = "\n".join(page.text for page in pages[:10])
            doc_type, class_score, class_scores = classify_document(source_pdf.name, sample)
            metadata = infer_metadata(source_pdf.name, pages)

            destination_dir = pdf_store / doc_type
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination_name = safe_name(f"{source_pdf.stem}_{file_hash[:12]}.pdf")
            destination_pdf = destination_dir / destination_name
            if not destination_pdf.exists():
                shutil.copy2(source_pdf, destination_pdf)

            ocr_count = sum(page.extraction_method == "ocr" for page in pages)
            native_count = sum(page.extraction_method == "native" for page in pages)
            extracted_chars = sum(page.final_characters for page in pages)

            if class_score < args.min_classification_score:
                warnings.append("Low-confidence document classification")
            if extracted_chars < args.min_document_chars:
                warnings.append("Very little text extracted")
            if pages and ocr_count / len(pages) >= args.ocr_review_ratio:
                warnings.append("OCR used on a high proportion of pages")

            document = DocumentRecord(
                document_id=document_id,
                sha256=file_hash,
                source_file=str(source_pdf),
                stored_pdf=str(destination_pdf),
                file_size=source_pdf.stat().st_size,
                page_count=len(pages),
                document_type=doc_type,
                classification_score=class_score,
                title=str(metadata["title"]),
                year=metadata["year"],
                court=metadata["court"],
                case_number=metadata["case_number"],
                decision_date=metadata["decision_date"],
                used_ocr=ocr_count > 0,
                ocr_page_count=ocr_count,
                native_page_count=native_count,
                extracted_characters=extracted_chars,
                status="processed",
                warnings=warnings,
            )

            structured_record = {
                "document": asdict(document),
                "classification_scores": class_scores,
                "pages": [asdict(page) for page in pages],
                "processed_at": utc_now(),
            }
            (structured / f"{file_hash}.json").write_text(
                json.dumps(structured_record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            clean_text = "\n\n".join(
                f"[PAGE {page.page_number}]\n{page.text}" for page in pages if page.text
            )
            (clean_text_dir / f"{file_hash}.txt").write_text(clean_text, encoding="utf-8")

            chunks = make_chunks(document, pages, args.chunk_chars, args.overlap_chars)
            for chunk in chunks:
                append_jsonl(rag_jsonl, asdict(chunk))

            manifest_record = asdict(document) | {
                "chunk_count": len(chunks),
                "processed_at": utc_now(),
            }
            append_jsonl(manifest_jsonl, manifest_record)
            manifest_rows.append(manifest_record)

            if warnings:
                review_rows.append({
                    "document_id": document_id,
                    "source_file": str(source_pdf),
                    "document_type": doc_type,
                    "classification_score": class_score,
                    "ocr_pages": ocr_count,
                    "page_count": len(pages),
                    "extracted_characters": extracted_chars,
                    "warnings": " | ".join(warnings),
                })

        except Exception as exc:
            LOGGER.exception("Failed to process %s", source_pdf)
            error_rows.append({
                "source_file": str(source_pdf),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    write_csv(
        reports / "duplicates.csv",
        duplicate_rows,
        ["duplicate_file", "canonical_file", "sha256", "reason"],
    )
    write_csv(
        reports / "errors.csv",
        error_rows,
        ["source_file", "error_type", "error"],
    )
    write_csv(
        reports / "manual_review.csv",
        review_rows,
        [
            "document_id", "source_file", "document_type", "classification_score",
            "ocr_pages", "page_count", "extracted_characters", "warnings",
        ],
    )
    if manifest_rows:
        write_csv(
            reports / "manifest_latest_run.csv",
            manifest_rows,
            [
                "document_id", "sha256", "source_file", "stored_pdf", "file_size",
                "page_count", "document_type", "classification_score", "title", "year",
                "court", "case_number", "decision_date", "used_ocr", "ocr_page_count",
                "native_page_count", "extracted_characters", "status", "warnings",
                "chunk_count", "processed_at",
            ],
        )

    summary = {
        "input_pdf_count": len(pdfs),
        "unique_seen_this_run": len(seen_hashes),
        "duplicates": len(duplicate_rows),
        "processed_this_run": len(manifest_rows),
        "manual_review": len(review_rows),
        "errors": len(error_rows),
        "rag_jsonl": str(rag_jsonl),
        "manifest_jsonl": str(manifest_jsonl),
        "completed_at": utc_now(),
    }
    (reports / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\nCorpus build completed")
    print(json.dumps(summary, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare legal PDFs for RAG and later supervised fine-tuning.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Input ZIP file or directory containing PDFs")
    parser.add_argument("--output", required=True, help="Output corpus directory")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR and only extract embedded PDF text")
    parser.add_argument("--tesseract-cmd", help=r"Full path to tesseract.exe on Windows")
    parser.add_argument("--ocr-language", default="eng", help="Tesseract language, e.g. eng or eng+hin")
    parser.add_argument("--ocr-dpi", type=int, default=220, help="Rendering resolution for OCR")
    parser.add_argument("--min-native-chars", type=int, default=80, help="OCR page when native text is below this")
    parser.add_argument("--min-text-quality", type=float, default=0.55, help="OCR page when text quality is below this")
    parser.add_argument("--min-document-chars", type=int, default=300, help="Flag documents with less extracted text")
    parser.add_argument("--chunk-chars", type=int, default=5000, help="Approximate maximum characters per RAG chunk")
    parser.add_argument("--overlap-chars", type=int, default=500, help="Text overlap between consecutive chunks")
    parser.add_argument("--min-classification-score", type=int, default=2, help="Flag classifications below this score")
    parser.add_argument("--ocr-review-ratio", type=float, default=0.70, help="Flag files when OCR page ratio exceeds this")
    parser.add_argument("--max-pages-per-pdf", type=int, help="Optional page cap for testing")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True, help="Skip successfully processed document hashes")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    try:
        process_corpus(args)
        return 0
    except KeyboardInterrupt:
        LOGGER.warning("Stopped by user. Run again with --resume to continue.")
        return 130
    except Exception as exc:
        LOGGER.exception("Corpus build failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
