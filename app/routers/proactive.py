import logging
import asyncio
from fastapi import APIRouter, Depends, BackgroundTasks
from app.database import get_db, Database

logger = logging.getLogger("nova-legal-app")
router = APIRouter()

@router.get("/compliance-gaps")
async def get_compliance_gaps(db: Database = Depends(get_db)):
    """Return compliance_gaps from DB."""
    return {"gaps": db.get_compliance_gaps()}

@router.get("/deadlines")
async def get_deadlines(status: str = None, db: Database = Depends(get_db)):
    """Return deadlines from DB, optionally filtered by status."""
    return {"deadlines": db.get_deadlines(status=status)}

@router.get("/staleness")
async def check_staleness(db: Database = Depends(get_db)):
    """Check documents for references to outdated/repealed acts."""
    return {"stale_documents": db.check_staleness()}

def run_corpus_scan():
    """Background task for full corpus intelligence scan."""
    logger.info("Starting full corpus intelligence scan...")
    # Add actual background logic that calls DB/models
    logger.info("Scan complete.")

@router.post("/scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    """Trigger full corpus intelligence scan in the background."""
    background_tasks.add_task(run_corpus_scan)
    return {"status": "Scan started in background"}
