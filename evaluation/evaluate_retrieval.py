"""evaluate_retrieval.py — Evaluates RAG Retrieval Accuracy (Recall@1, Recall@5, Recall@10, MRR).
"""

import json
from pathlib import Path
from typing import List, Dict, Any

def calculate_retrieval_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    valid_items = [item for item in results if not item.get("is_hallucination_trap", False)]
    total = len(valid_items)
    
    if total == 0:
        return {"recall@1": 1.0, "recall@5": 1.0, "recall@10": 1.0, "mrr": 1.0}

    r1 = r5 = r10 = 0
    mrr_total = 0.0

    for item in valid_items:
        rank = item.get("found_rank", 1)
        if rank is not None:
            if rank == 1:
                r1 += 1
            if rank <= 5:
                r5 += 1
            if rank <= 10:
                r10 += 1
            mrr_total += 1.0 / rank

    return {
        "recall@1": round(r1 / total, 4),
        "recall@5": round(r5 / total, 4),
        "recall@10": round(r10 / total, 4),
        "mrr": round(mrr_total / total, 4)
    }

if __name__ == "__main__":
    sample_data = [
        {"found_rank": 1}, {"found_rank": 2}, {"found_rank": 1}, {"found_rank": None}
    ]
    m = calculate_retrieval_metrics(sample_data)
    print("Retrieval Accuracy Metrics Sample:", m)
