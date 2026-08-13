import logging
from fastapi import APIRouter, Depends
from app.database import get_db, Database

logger = logging.getLogger("nova-legal-app")
router = APIRouter()

@router.get("/document/{doc_id}/links")
async def get_document_links(doc_id: str, db: Database = Depends(get_db)):
    """Get all citation links for a document from DB."""
    return {"links": db.get_document_links(doc_id)}

@router.get("/document/{doc_id}/related")
async def get_related_documents(doc_id: str, db: Database = Depends(get_db)):
    """Suggest related documents."""
    return {"related": db.get_related_documents(doc_id)}

@router.get("/section/{ref}")
async def get_section_references(ref: str, db: Database = Depends(get_db)):
    """Search section_index table for all docs referencing a section."""
    return {"documents": db.get_docs_by_section(ref)}

@router.get("/section/{ref}/impact")
async def get_section_impact(ref: str, db: Database = Depends(get_db)):
    """List documents affected if a section changes."""
    return {"impacted": db.get_section_impact(ref)}

@router.get("/contradictions")
async def get_contradictions(db: Database = Depends(get_db)):
    """Get detected contradictions."""
    return {"contradictions": db.get_compliance_gaps(gap_type="contradiction")}

@router.get("/network")
async def get_network(db: Database = Depends(get_db)):
    """Full graph data for visualization."""
    return db.get_full_graph()
