"""evaluate_retrieval.py — Evaluates RAG Retrieval Accuracy (Recall@1, Recall@5, Recall@10, MRR).
"""

import json
from pathlib import Path
from typing import List, Dict, Any

def calculate_retrieval_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    r1 = r5 = r10 = 0
    mrr_total = 0.0
    total = len(results)
    
    if total == 0:
        return {"recall@1": 0.0, "recall@5": 0.0, "recall@10": 0.0, "mrr": 0.0}

    for item in results:
        rank = item.get("found_rank", None)
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
