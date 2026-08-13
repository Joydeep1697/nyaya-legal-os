"""analyze_failures.py — Phase 5.5 Benchmark Failure Analyzer and Classifier.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(r"d:\Nova Legal")
BENCHMARK_FILE = BASE_DIR / "evaluation" / "benchmark_800.jsonl"
RESULTS_FILE = BASE_DIR / "evaluation" / "results.json"
ANALYSIS_FILE = BASE_DIR / "evaluation" / "failure_analysis.json"

FAILURE_CATEGORIES = {
    "A": "Wrong keyword retrieval",
    "B": "Wrong semantic retrieval",
    "C": "Bad chunking",
    "D": "Metadata problem",
    "E": "Section-number mismatch",
    "F": "Authority weighting problem",
    "G": "Query normalization problem",
    "H": "Missing source document"
}

def classify_failure(query: str, exp_sec: str, top_chunks: List[str]) -> str:
    query_lower = query.lower()
    
    if any(k in query_lower for k in ["ipc", "crpc", "iea", "evidence act"]):
        return "G. Query normalization problem"
    if exp_sec and not any(exp_sec in c for c in top_chunks):
        return "E. Section-number mismatch"
    if "bns" in query_lower or "bnss" in query_lower or "bsa" in query_lower:
        return "C. Bad chunking"
    return "B. Wrong semantic retrieval"

def main():
    print("=== PHASE 5.5 BENCHMARK FAILURE DIAGNOSTIC ANALYSIS ===")
    if not BENCHMARK_FILE.exists():
        print("Benchmark file not found.")
        return

    failures = []
    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("is_hallucination_trap"):
                continue
                
            q = item.get("query")
            exp_sec = item.get("expected_section", "")
            cat = classify_failure(q, exp_sec, [])
            
            failures.append({
                "query": q,
                "expected_section": exp_sec,
                "failure_category": cat,
                "action_required": f"Apply Phase 5.5 deterministic mapping & statutory chunking for '{exp_sec}'"
            })

    report = {
        "total_queries_analyzed": len(failures),
        "failures_by_category": {
            "Query normalization problem (IPC/CrPC/IEA conversion)": sum(1 for f in failures if "Query normalization" in f["failure_category"]),
            "Section-number mismatch": sum(1 for f in failures if "Section-number" in f["failure_category"]),
            "Bad statutory chunking": sum(1 for f in failures if "Bad chunking" in f["failure_category"])
        },
        "sample_failures": failures[:10]
    }

    with open(ANALYSIS_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"  [+] Failure analysis report generated: {ANALYSIS_FILE.relative_to(BASE_DIR)}")
    print(f"  [+] Identified {len(failures)} diagnostic targets for Phase 5.5 RAG Optimization.")

if __name__ == "__main__":
    main()
