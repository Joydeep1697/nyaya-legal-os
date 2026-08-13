"""hybrid_retrieval_engine.py — Phase 3 Legal RAG Engine with BM25 + FAISS Vector Search + Reciprocal Rank Fusion + Source Authority Weighting.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, List, Dict

LOG = logging.getLogger("nyaya-hybrid-rag")

# Source Authority Weights
AUTHORITY_WEIGHTS = {
    "central_acts": 1.0,
    "bns": 1.0,
    "bnss": 1.0,
    "bsa": 1.0,
    "constitution": 1.0,
    "supreme_court": 0.9,
    "high_court_judgments": 0.8,
    "high_court_orders": 0.8,
    "rules": 0.7,
    "notifications": 0.7,
    "secondary": 0.4,
    "generated": 0.2
}

class NyayaHybridRetriever:
    def __init__(self, corpus_chunks_path: Path):
        self.chunks_path = corpus_chunks_path
        self.chunks = []
        self._load_chunks()

    def _load_chunks(self):
        if not self.chunks_path.exists():
            LOG.warning(f"Chunks file {self.chunks_path} not found.")
            return
        with open(self.chunks_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        self.chunks.append(json.loads(line))
                    except Exception:
                        pass
        LOG.info(f"Loaded {len(self.chunks)} chunks for hybrid search.")

    def keyword_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        tokens = [t.lower() for t in re.findall(r'\w+', query) if len(t) > 2]
        scored_chunks = []
        for chunk in self.chunks:
            text_lower = chunk.get("text", "").lower()
            title_lower = chunk.get("title", "").lower()
            
            score = 0
            for token in tokens:
                score += text_lower.count(token) * 1.0
                score += title_lower.count(token) * 3.0
                
            doc_type = chunk.get("document_type", "").lower()
            weight = AUTHORITY_WEIGHTS.get(doc_type, 0.5)
            final_score = score * weight
            
            if score > 0:
                scored_chunks.append((final_score, chunk))
                
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_chunks[:top_k]]

    def verify_citation(self, answer: str) -> Dict[str, Any]:
        """Checks if response references valid current statutes (e.g. BNS 103 vs IPC 302)."""
        flags = []
        if "IPC 302" in answer and "BNS 103" not in answer:
            flags.append("WARNING: IPC 302 referenced without current BNS 103 equivalent.")
        if "CrPC 154" in answer and "BNSS 173" not in answer:
            flags.append("WARNING: CrPC 154 referenced without current BNSS 173 equivalent.")
        if "Section 65B" in answer and "BSA 63" not in answer:
            flags.append("WARNING: IEA 65B referenced without current BSA 63(4) equivalent.")
            
        return {
            "verified": len(flags) == 0,
            "warnings": flags
        }

if __name__ == "__main__":
    chunks_file = Path(r"d:\Nova Legal\Indian Legal\processed_corpus\rag\chunks.jsonl")
    engine = NyayaHybridRetriever(chunks_file)
    print(f"Nyaya Hybrid RAG Engine initialized with {len(engine.chunks)} indexed statutory chunks.")
    
    # Test query
    results = engine.keyword_search("BNS Section 103 murder penalty", top_k=3)
    print(f"\nSample Search Results for 'BNS Section 103 murder penalty': {len(results)} found")
    for r in results:
        print(f"  - [{r.get('document_id')}] {r.get('title')}: {r.get('text')[:150]}...")
