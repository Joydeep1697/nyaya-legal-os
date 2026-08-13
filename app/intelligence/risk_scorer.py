import logging
import re
from datetime import datetime

logger = logging.getLogger("nova-legal-app")

def score_document(text: str, metadata: dict, clauses: list[dict], entities: list[dict]) -> int:
    """
    Returns 0-100 risk score for a document based on various risk factors.
    """
    score = 0
    try:
        doc_type = metadata.get("doc_type", "").lower()
        clause_types = {c["type"] for c in clauses}
        
        # Missing common clauses for doc type
        if "contract" in doc_type or "agreement" in doc_type:
            if "arbitration" not in clause_types:
                score += 15
            if "governing_law" not in clause_types:
                score += 10
                
        # High-risk clauses found
        for c in clauses:
            if c.get("risk") == "high":
                score += 20
                break # count once
                
        # OCR quality issues
        warnings = metadata.get("warnings", [])
        if len(warnings) > 0:
            score += 10
            
        # Outdated references
        doc_year = metadata.get("year")
        if doc_year:
            try:
                if datetime.now().year - int(doc_year) > 10:
                    score += 10
            except ValueError:
                pass
                
        # Ambiguous language patterns
        ambiguous_terms = [r'\bmay\b', r'\bat discretion\b', r'\breasonable efforts\b']
        ambiguous_count = 0
        for term in ambiguous_terms:
            ambiguous_count += len(re.findall(term, text, re.IGNORECASE))
        
        score += min(ambiguous_count * 5, 15)
        
        return min(score, 100)
    except Exception as e:
        logger.error(f"Error scoring document: {e}")
        return score

def scan_corpus_gaps(documents_by_domain: dict) -> list[dict]:
    """
    Check which legal domains have coverage gaps.
    documents_by_domain expects: { "employment_law": [doc1, doc2], ... }
    Returns list of {domain, gap_description, severity} dicts.
    """
    gaps = []
    try:
        # Check Employment Law
        emp_docs = documents_by_domain.get("employment_law", [])
        emp_text = " ".join([d.get("text", "").lower() for d in emp_docs])
        if "posh act" not in emp_text and "sexual harassment" not in emp_text:
            gaps.append({
                "domain": "employment_law",
                "gap_description": "Missing sexual harassment policy (POSH Act)",
                "severity": "high"
            })
            
        # Check Corporate Law
        corp_docs = documents_by_domain.get("corporate_law", [])
        corp_text = " ".join([d.get("text", "").lower() for d in corp_docs])
        if "board resolution" not in corp_text:
            gaps.append({
                "domain": "corporate_law",
                "gap_description": "Missing board resolution templates",
                "severity": "medium"
            })
            
        # Check Data Protection
        dp_docs = documents_by_domain.get("data_protection", [])
        dp_text = " ".join([d.get("text", "").lower() for d in dp_docs])
        if "privacy policy" not in dp_text:
            gaps.append({
                "domain": "data_protection",
                "gap_description": "Missing privacy policy",
                "severity": "high"
            })
            
        # Check Tax Law
        tax_docs = documents_by_domain.get("tax_law", [])
        tax_text = " ".join([d.get("text", "").lower() for d in tax_docs])
        if "gst" not in tax_text:
            gaps.append({
                "domain": "tax_law",
                "gap_description": "Missing GST compliance docs",
                "severity": "high"
            })
            
    except Exception as e:
        logger.error(f"Error scanning corpus gaps: {e}")
        
    return gaps
