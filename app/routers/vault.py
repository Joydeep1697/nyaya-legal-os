import logging
import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from app.database import get_db, Database
from app.models import DocumentResponse, SearchResponse, SearchRequest
from app.config import RAW_DIR, get_llm_client_kwargs

logger = logging.getLogger("nova-legal-app")
router = APIRouter()

# WebSocket connections tracking
_ws_connections: dict[str, list[WebSocket]] = {}

async def broadcast_progress(doc_id: str, message: dict):
    if doc_id in _ws_connections:
        dead_connections = []
        for ws in _ws_connections[doc_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)
        for dead_ws in dead_connections:
            _ws_connections[doc_id].remove(dead_ws)

def process_document(doc_id: str, file_path: str):
    db = get_db()
    try:
        # Step 1: Save file -> update status
        asyncio.run(broadcast_progress(doc_id, {"status": "extracting", "progress": 10}))
        db.update_document_status(doc_id, "extracting")
        
        # Imports from backend
        try:
            from nova_legal_classifier import (
                extract_pdf, classify_rules, detect_domain, authority_for,
                extract_sections, extract_rules, extract_articles, extract_court,
                extract_judges, extract_parties, extract_citations, extract_case_number,
                extract_dates, extract_year, title_from_text
            )
            from app.config import OCR_ENABLED, OCR_LANGUAGE
        except ImportError as e:
            logger.error(f"Failed to import backend modules: {e}")
            db.update_document_status(doc_id, "failed")
            asyncio.run(broadcast_progress(doc_id, {"status": "failed", "error": "Backend modules unavailable"}))
            return

        # Step 2: extract_pdf
        try:
            extracted = extract_pdf(file_path, OCR_ENABLED, OCR_LANGUAGE)
            pages = extracted.page_count
            text = extracted.text
        except Exception as e:
            logger.error(f"Failed to extract PDF: {e}")
            db.update_document_status(doc_id, "failed")
            asyncio.run(broadcast_progress(doc_id, {"status": "failed", "error": "PDF extraction failed"}))
            return
            
        asyncio.run(broadcast_progress(doc_id, {"status": "classifying", "progress": 40}))
        
        # Step 3: Classify
        filename = Path(file_path).name
        try:
            title = title_from_text(text, filename)
            category, confidence, _, _ = classify_rules(filename, text, None, 0.5)
            domain = detect_domain(text, title)
            authority_level, _ = authority_for(category)
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            category, domain, authority_level = "Unknown", "Unknown", 0
            
        asyncio.run(broadcast_progress(doc_id, {"status": "extracting_entities", "progress": 60}))

        # Step 4: Extract entities
        try:
            sections = extract_sections(text)
            rules = extract_rules(text)
            articles = extract_articles(text)
            court = extract_court(text)
            judges = extract_judges(text)
            parties = extract_parties(text)
            citations = extract_citations(text)
            case_num = extract_case_number(text)
            dates = extract_dates(text)
            year = extract_year(text, filename)
            
            # Save to DB - assuming appropriate db methods exist
            # db.save_entities(doc_id, entities=...)
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")

        asyncio.run(broadcast_progress(doc_id, {"status": "analyzing_clauses", "progress": 80}))

        # Step 5 & 6: Clauses and Knowledge Graph
        try:
            from app.intelligence.clause_detector import extract_clauses
            from app.intelligence.knowledge_graph import build_links
            # In a real system, invoke and save these
        except ImportError:
            pass

        # Step 7: Done
        db.update_document_status(doc_id, "indexed")
        # In a real system: db.set_process_time(doc_id, ...)
        asyncio.run(broadcast_progress(doc_id, {"status": "indexed", "progress": 100}))

    except Exception as e:
        logger.exception("Unexpected error in process_document")
        db.update_document_status(doc_id, "failed")
        asyncio.run(broadcast_progress(doc_id, {"status": "failed", "error": str(e)}))

@router.post("/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Database = Depends(get_db)):
    """Upload a PDF and start background processing."""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files are supported")
    
    # Ensure RAW_DIR exists
    os.makedirs(RAW_DIR, exist_ok=True)
    file_path = RAW_DIR / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    doc_id = db.create_document_record(file.filename, str(file_path))
    background_tasks.add_task(process_document, doc_id, str(file_path))
    return {"doc_id": doc_id, "status": "processing"}

@router.get("/documents")
async def list_documents(status: Optional[str] = None, category: Optional[str] = None, domain: Optional[str] = None, limit: int = 10, offset: int = 0, db: Database = Depends(get_db)):
    """List documents with optional filters and pagination."""
    docs = db.get_documents(status=status, category=category, domain=domain, limit=limit, offset=offset)
    return {"documents": docs}

@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, db: Database = Depends(get_db)):
    """Get full details of a specific document including entities, clauses, deadlines, and links."""
    doc = db.get_document_details(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, db: Database = Depends(get_db)):
    """Delete a document from DB and filesystem."""
    doc = db.get_document(doc_id)
    if doc:
        try:
            if os.path.exists(doc['file_path']):
                os.remove(doc['file_path'])
        except Exception:
            pass
        db.delete_document(doc_id)
    return {"status": "success"}

@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest, db: Database = Depends(get_db)):
    """Intelligent search using local_search."""
    try:
        from nova_legal_rag_nvidia import local_search
        from app.config import INDEX_DIR
        results = await asyncio.to_thread(local_search, req.query, INDEX_DIR)
        return SearchResponse(results=results)
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(500, "Search failed")

@router.get("/stats")
async def get_stats(db: Database = Depends(get_db)):
    """Return vault statistics from DB."""
    return db.get_document_stats()

@router.websocket("/ws/processing")
async def ws_processing(websocket: WebSocket, doc_id: str = Query(...)):
    """WebSocket endpoint to stream background processing progress."""
    await websocket.accept()
    if doc_id not in _ws_connections:
        _ws_connections[doc_id] = []
    _ws_connections[doc_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if doc_id in _ws_connections and websocket in _ws_connections[doc_id]:
            _ws_connections[doc_id].remove(websocket)
