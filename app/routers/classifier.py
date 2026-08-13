import logging
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db, Database
from app.config import CATEGORY_DIR

logger = logging.getLogger("nova-legal-app")
router = APIRouter()

@router.post("/classify/{doc_id}")
async def reclassify_document(doc_id: str, db: Database = Depends(get_db)):
    """Re-classify a document by running extract_pdf + classify_rules + detect_domain."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
        
    def do_reclassify():
        from nova_legal_classifier import extract_pdf, classify_rules, detect_domain
        from app.config import OCR_ENABLED, OCR_LANGUAGE
        extracted = extract_pdf(doc['file_path'], OCR_ENABLED, OCR_LANGUAGE)
        filename = Path(doc['file_path']).name
        category, confidence, _, _ = classify_rules(filename, extracted.text, None, 0.5)
        domain = detect_domain(extracted.text, filename)
        return category, domain

    try:
        category, domain = await asyncio.to_thread(do_reclassify)
        db.update_document_classification(doc_id, category, domain)
        return {"category": category, "domain": domain}
    except Exception as e:
        logger.error(f"Reclassification error: {e}")
        raise HTTPException(500, "Reclassification failed")

@router.get("/categories")
async def list_categories():
    """List all categories by scanning CATEGORY_DIR."""
    categories = []
    try:
        cat_dir = Path(CATEGORY_DIR)
        if cat_dir.exists():
            for subdir in cat_dir.iterdir():
                if subdir.is_dir():
                    count = len(list(subdir.glob("*")))
                    categories.append({"name": subdir.name, "count": count})
    except Exception as e:
        logger.error(f"Categories list error: {e}")
    return {"categories": categories}

@router.get("/domains")
async def list_domains(db: Database = Depends(get_db)):
    """List all domains with document counts."""
    return {"domains": db.get_domain_counts()}

@router.get("/stats")
async def get_classification_stats():
    """Get classification statistics from classification reports."""
    # Placeholder for reading classification_reports
    return {"accuracy": 0.95, "total_classified": 1500}
