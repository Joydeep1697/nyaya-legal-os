"""evaluate_citations.py — Verifies that statutory citations returned in answers are valid and present in Level 1 bare acts.
"""

import re
from typing import List, Dict, Any

VALID_BNS_SECTIONS = set(str(i) for i in range(1, 359))
VALID_BNSS_SECTIONS = set(str(i) for i in range(1, 532))
VALID_BSA_SECTIONS = set(str(i) for i in range(1, 171))

def evaluate_citations(predictions: List[Dict[str, Any]]) -> Dict[str, float]:
    total_citations = 0
    valid_citations = 0

    for item in predictions:
        ans = item.get("model_answer", "")
        # Find BNS citations
        bns_matches = re.findall(r'BNS\s+(?:Section\s+)?(\d+)', ans)
        for m in bns_matches:
            total_citations += 1
            if m in VALID_BNS_SECTIONS:
                valid_citations += 1

        # Find BNSS citations
        bnss_matches = re.findall(r'BNSS\s+(?:Section\s+)?(\d+)', ans)
        for m in bnss_matches:
            total_citations += 1
            if m in VALID_BNSS_SECTIONS:
                valid_citations += 1

        # Find BSA citations
        bsa_matches = re.findall(r'BSA\s+(?:Section\s+)?(\d+)', ans)
        for m in bsa_matches:
            total_citations += 1
            if m in VALID_BSA_SECTIONS:
                valid_citations += 1

    rate = round(valid_citations / total_citations, 4) if total_citations > 0 else 1.0
    return {
        "total_citations_evaluated": total_citations,
        "valid_citations_verified": valid_citations,
        "citation_accuracy_rate": rate
    }

if __name__ == "__main__":
    sample = [
        {"model_answer": "Under BNS Section 103 and BNSS Section 173..."},
        {"model_answer": "According to BNS Section 999..."}
    ]
    print("Citation Verification Sample:", evaluate_citations(sample))
