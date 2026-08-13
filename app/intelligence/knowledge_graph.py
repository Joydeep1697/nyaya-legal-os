import logging

logger = logging.getLogger("nova-legal-app")

def build_document_links(doc_id: str, entities: list[dict], all_docs: list[dict]) -> list[dict]:
    """
    Builds citation links between documents in the vault.
    """
    links = []
    try:
        for doc in all_docs:
            other_id = doc.get("id")
            if other_id == doc_id:
                continue
                
            other_text = doc.get("text", "")
            other_metadata = doc.get("metadata", {})
            other_case = other_metadata.get("case_number", "")
            
            for ent in entities:
                ent_type = ent.get("type")
                ent_val = ent.get("value")
                
                if not ent_val:
                    continue
                    
                # Is the act being cited
                if ent_type == "act_name" and ent_val in other_text:
                    links.append({
                        "source_doc_id": doc_id,
                        "target_doc_id": other_id,
                        "relationship": "cites",
                        "source_ref": ent_val,
                        "target_ref": ent_val,
                        "confidence": 0.8
                    })
                
                # Contains the same section reference
                elif ent_type == "section" and ent_val in other_text:
                    links.append({
                        "source_doc_id": doc_id,
                        "target_doc_id": other_id,
                        "relationship": "interprets", # or cites
                        "source_ref": ent_val,
                        "target_ref": ent_val,
                        "confidence": 0.6
                    })
                
                # Is a judgment that cites the same case number
                elif ent_type == "case_number" and other_case == ent_val:
                    links.append({
                        "source_doc_id": doc_id,
                        "target_doc_id": other_id,
                        "relationship": "applies",
                        "source_ref": ent_val,
                        "target_ref": ent_val,
                        "confidence": 0.9
                    })
    except Exception as e:
        logger.error(f"Error building document links: {e}")
        
    return links

def find_related_documents(doc_id: str, db) -> list[dict]:
    """
    Find related docs by: same domain, shared section references, shared citations.
    """
    related = []
    try:
        # In a real scenario, we'd query the DB models.
        # This acts as a stub wrapper for the DB query logic.
        pass
    except Exception as e:
        logger.error(f"Error finding related documents: {e}")
    return related

def detect_contradictions(doc_pairs: list[tuple], clause_pairs: list[tuple]) -> list[dict]:
    """
    For pairs of documents in the same domain, compare their clauses for contradictions.
    """
    contradictions = []
    try:
        for (doc_a, doc_b), (clauses_a, clauses_b) in zip(doc_pairs, clause_pairs):
            # Match clauses by type
            a_dict = {c["type"]: c["text"] for c in clauses_a}
            b_dict = {c["type"]: c["text"] for c in clauses_b}
            
            common_types = set(a_dict.keys()).intersection(set(b_dict.keys()))
            
            for c_type in common_types:
                # Simplistic heuristic: string difference or specific term checks
                # If they are very different, they might contradict
                text_a = a_dict[c_type]
                text_b = b_dict[c_type]
                
                if text_a != text_b: # in reality, use embeddings or LLM check here
                    # Check numbers/days difference to flag
                    import re
                    nums_a = re.findall(r'\d+', text_a)
                    nums_b = re.findall(r'\d+', text_b)
                    
                    if nums_a != nums_b:
                        contradictions.append({
                            "doc_a_id": doc_a.get("id"),
                            "doc_a_name": doc_a.get("filename"),
                            "doc_b_id": doc_b.get("id"),
                            "doc_b_name": doc_b.get("filename"),
                            "description": f"Conflicting terms in {c_type} clause.",
                            "clause_a": text_a,
                            "clause_b": text_b,
                            "confidence": 0.7
                        })
    except Exception as e:
        logger.error(f"Error detecting contradictions: {e}")
        
    return contradictions
