import logging
import re

logger = logging.getLogger("nova-legal-app")

CLAUSE_PATTERNS = {
    "indemnity": r"indemnif|hold harmless",
    "limitation_of_liability": r"limitation of liability|aggregate liability|shall not exceed",
    "force_majeure": r"force majeure|act of god|beyond.*?control",
    "termination": r"terminat.*?agreement|right to terminate|notice.*?termination",
    "confidentiality": r"confidential|non-disclosure|proprietary information",
    "governing_law": r"governing law|governed by.*?laws|jurisdiction",
    "arbitration": r"arbitrat|dispute resolution|mediat",
    "ip_assignment": r"intellectual property|assignment.*?rights|work.*?for.*?hire",
    "non_compete": r"non-compet|restrictive covenant|not.*?engage.*?competing",
    "data_protection": r"personal data|data protection|privacy|DPDP|GDPR"
}

HIGH_RISK_TERMS = r"unlimited|waive|sole discretion"
MEDIUM_RISK_TERMS = r"may|at discretion|reasonable efforts"

def detect_clauses(text: str, doc_type: str = "") -> list[dict]:
    """
    Detects legal clauses in document text using regex patterns.
    Returns list of {type, text, risk, page} dicts.
    """
    results = []
    try:
        # Split text into sentences roughly, handling newlines properly
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.replace('\n', ' ')) if s.strip()]
        
        for clause_type, pattern in CLAUSE_PATTERNS.items():
            compiled = re.compile(pattern, re.IGNORECASE)
            
            for i, sentence in enumerate(sentences):
                if compiled.search(sentence):
                    # Extract 2-3 sentences around the match
                    start_idx = max(0, i - 1)
                    end_idx = min(len(sentences), i + 2)
                    clause_text = " ".join(sentences[start_idx:end_idx])
                    
                    # Assess risk_level
                    risk = "low"
                    if re.search(HIGH_RISK_TERMS, clause_text, re.IGNORECASE):
                        risk = "high"
                    elif re.search(MEDIUM_RISK_TERMS, clause_text, re.IGNORECASE):
                        risk = "medium"
                    
                    # Approximate start page by counting form feeds or page breaks before this sentence
                    # (Fallback to splitting original text and finding the sentence)
                    text_before_match = text[:text.find(sentence[:20])] if sentence[:20] in text else ""
                    page = text_before_match.count("\f") + text_before_match.count("--- Page") + 1
                    
                    results.append({
                        "type": clause_type,
                        "text": clause_text,
                        "risk": risk,
                        "page": page
                    })
                    # Move to next clause type once one is found to avoid duplicate spam, 
                    # or continue if we want all instances (breaking for now to get 1 per type)
                    break
                    
    except Exception as e:
        logger.error(f"Error detecting clauses: {e}")
        
    return results
