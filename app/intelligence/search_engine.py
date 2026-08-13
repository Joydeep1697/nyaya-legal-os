import logging
import re
from pathlib import Path
from app import config

logger = logging.getLogger("nova-legal-app")

try:
    # Import existing RAG engine after config has set up the path
    import nova_legal_rag_nvidia as rag
except ImportError as e:
    logger.warning(f"Failed to import nova_legal_rag_nvidia: {e}")
    rag = None

def parse_natural_language_filters(query: str) -> tuple[str, dict]:
    """
    Extract structured filters from a natural language query.
    Returns (cleaned_query, filters_dict)
    """
    filters = {}
    cleaned_query = query
    try:
        # Extract Year
        year_match = re.search(r'(?:from|in|after)\s+(20\d{2})', query, re.IGNORECASE)
        if year_match:
            filters['year'] = int(year_match.group(1))
            cleaned_query = cleaned_query.replace(year_match.group(0), "").strip()
            
        # Extract Type
        type_match = re.search(r'\b(contracts?|judgments?|acts?|rules?)\b', query, re.IGNORECASE)
        if type_match:
            filters['doc_type'] = type_match.group(1).lower().rstrip('s')
            cleaned_query = cleaned_query.replace(type_match.group(0), "").strip()
            
        # Extract Domain
        domain_match = re.search(r'\b(employment|corporate|tax)\b', query, re.IGNORECASE)
        if domain_match:
            filters['domain'] = f"{domain_match.group(1).lower()}_law"
            cleaned_query = cleaned_query.replace(domain_match.group(0), "").strip()
            
    except Exception as e:
        logger.error(f"Error parsing filters: {e}")
        
    return cleaned_query, filters

def intelligent_search(query: str, filters: dict, index_dir: Path) -> dict:
    """
    Enhanced search wrapping the existing RAG engine.
    """
    results = {
        "results": [],
        "total": 0,
        "query_expanded": query,
        "facets": {"category": {}, "domain": {}}
    }
    try:
        if not rag:
            raise ImportError("nova_legal_rag_nvidia is not available.")
            
        # 1. Parse natural language filters
        cleaned_query, parsed_filters = parse_natural_language_filters(query)
        filters.update(parsed_filters)
        
        # 2. Expand legal terms
        expanded_query = rag.rewrite_legal_query(cleaned_query)
        results["query_expanded"] = expanded_query
        
        # 3. Call local search
        raw_hits = rag.local_search(
            question=expanded_query,
            index_dir=index_dir,
            candidates=40,
            document_type=filters.get('doc_type'),
            year=filters.get('year'),
            court=filters.get('court')
        )
        
        # 4. Rerank if NVIDIA is configured
        if config.RERANK_MODEL and hasattr(rag, 'rerank_with_nvidia'):
            raw_hits = rag.rerank_with_nvidia(
                question=expanded_query,
                candidates=raw_hits,
                model=config.RERANK_MODEL,
                base_url=config.RERANK_BASE_URL,
                top_k=15,
                timeout=10.0
            )
            
        # 5. Diversify chunks per document
        final_hits = rag.diversified_top_k(raw_hits, top_k=10, max_chunks_per_document=2)
        
        results["results"] = final_hits
        results["total"] = len(final_hits)
        
        # Compute facets
        for hit in final_hits:
            cat = hit.get("category", "unknown")
            dom = hit.get("domain", "unknown")
            results["facets"]["category"][cat] = results["facets"]["category"].get(cat, 0) + 1
            results["facets"]["domain"][dom] = results["facets"]["domain"].get(dom, 0) + 1
            
    except Exception as e:
        logger.error(f"Error in intelligent search: {e}")
        
    return results

def suggest_related(doc_id: str, index_dir: Path, db) -> list[dict]:
    """
    Get document's embedding, find nearest neighbors via FAISS, return top 5.
    """
    related = []
    try:
        if not rag:
            return related
            
        # In a real setup, we would retrieve the doc text or embedding from DB,
        # then query the FAISS index (rag.load_index) using vector search.
        # This is a stub for the FAISS logic wrapper.
        pass
    except Exception as e:
        logger.error(f"Error suggesting related documents: {e}")
        
    return related
