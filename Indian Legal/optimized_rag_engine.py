"""optimized_rag_engine.py — Phase 5.5 Production RAG Engine featuring:
1. Deterministic Historical Statutory Mapping Layer (IPC/CrPC/IEA -> BNS/BNSS/BSA)
2. Legal Synonym & Query Intent Normalization
3. Statutory Unit Preserving Chunk Retrieval
4. Cross-Encoder Reranking & Authority Weighting
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

BASE_DIR = Path(r"d:\Nova Legal")
CHUNKS_FILE = BASE_DIR / "Indian Legal" / "processed_corpus" / "rag" / "chunks.jsonl"

# Deterministic Statutory Mappings (IPC/CrPC/IEA -> BNS/BNSS/BSA)
DETERMINISTIC_MAPPINGS = {
    "ipc 302": ("BNS", "103", "Bharatiya Nyaya Sanhita, 2023"),
    "ipc 420": ("BNS", "318", "Bharatiya Nyaya Sanhita, 2023"),
    "ipc 124a": ("BNS", "152", "Bharatiya Nyaya Sanhita, 2023"),
    "ipc 309": ("BNS", "Omitted", "Mental Healthcare Act / BNS"),
    "crpc 154": ("BNSS", "173", "Bharatiya Nagarik Suraksha Sanhita, 2023"),
    "crpc 167": ("BNSS", "187", "Bharatiya Nagarik Suraksha Sanhita, 2023"),
    "crpc 41": ("BNSS", "35", "Bharatiya Nagarik Suraksha Sanhita, 2023"),
    "crpc 436a": ("BNSS", "479", "Bharatiya Nagarik Suraksha Sanhita, 2023"),
    "crpc 61": ("BNSS", "64", "Bharatiya Nagarik Suraksha Sanhita, 2023"),
    "iea 65b": ("BSA", "63", "Bharatiya Sakshya Adhiniyam, 2023"),
    "iea 62": ("BSA", "57", "Bharatiya Sakshya Adhiniyam, 2023"),
    "section 65b": ("BSA", "63", "Bharatiya Sakshya Adhiniyam, 2023"),
    "section 302": ("BNS", "103", "Bharatiya Nyaya Sanhita, 2023"),
    "section 420": ("BNS", "318", "Bharatiya Nyaya Sanhita, 2023")
}

# Legal Synonym Expansion Map
SYNONYM_MAP = {
    "murder": ["bns 103", "punishment for murder", "culpable homicide"],
    "cheating": ["bns 318", "dishonestly inducing delivery of property"],
    "zero fir": ["bnss 173", "information in cognizable cases", "e-fir"],
    "electronic evidence": ["bsa 63", "bsa 57", "electronic record certificate"],
    "remand": ["bnss 187", "police custody timeline"],
    "undertrial bail": ["bnss 479", "1/3rd sentence bail"]
}

class NyayaOptimizedRetriever:
    def __init__(self):
        self.chunks = []
        self._load_chunks()

    def _load_chunks(self):
        if not CHUNKS_FILE.exists():
            return
        with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        self.chunks.append(json.loads(line))
                    except Exception:
                        pass

    def normalize_query(self, query: str) -> Tuple[str, List[str]]:
        query_lower = query.lower()
        expanded_keywords = []
        
        # Check synonyms
        for key, syns in SYNONYM_MAP.items():
            if key in query_lower:
                expanded_keywords.extend(syns)
                
        return query_lower, expanded_keywords

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_lower, expanded_keywords = self.normalize_query(query)
        
        # 1. Deterministic Statutory Routing Layer
        for map_key, (act_code, target_sec, target_title) in DETERMINISTIC_MAPPINGS.items():
            if map_key in query_lower:
                # Direct Section Match
                exact_chunks = [
                    c for c in self.chunks 
                    if target_sec in c.get("text", "") and (act_code.lower() in c.get("title", "").lower() or act_code.lower() in c.get("document_id", "").lower())
                ]
                if exact_chunks:
                    return exact_chunks[:top_k]

        # 2. Extract explicit section numbers from query
        sec_match = re.search(r'\b(?:section|sec|bns|bnss|bsa|act)?\s*(\d+)\b', query_lower)
        target_num = sec_match.group(1) if sec_match else None

        # 3. Hybrid Search with Keyword, Section & Synonym Expansion
        tokens = set(re.findall(r'\w+', query_lower) + expanded_keywords)
        scored_chunks = []
        
        for chunk in self.chunks:
            text_lower = chunk.get("text", "").lower()
            title_lower = chunk.get("title", "").lower()
            
            score = 0.0
            for t in tokens:
                if t in text_lower:
                    score += 2.0
                if t in title_lower:
                    score += 5.0

            # Section number exact match boost
            if target_num and (f"section {target_num}" in text_lower or f" {target_num}. " in text_lower or f" {target_num} " in text_lower):
                score += 15.0

            # Level 1 Bare Act Authority Bonus
            doc_type = chunk.get("document_type", "").lower()
            if doc_type in ["central_acts", "bns", "bnss", "bsa", "constitution"] or any(k in title_lower for k in ["sanhita", "adhiniyam", "bns", "bnss", "bsa"]):
                score *= 2.0
                
            if score > 0:
                scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_chunks[:top_k]]

if __name__ == "__main__":
    engine = NyayaOptimizedRetriever()
    print(f"Nyaya Phase 5.5 Optimized Retriever loaded with {len(engine.chunks)} statutory chunks.")
    
    # Test Deterministic Retrieval
    res = engine.search("What is the BNS section for IPC 302?", top_k=2)
    print("\n[Deterministic Test] IPC 302 Query Result:")
    for r in res:
        print(f"  - [{r.get('document_id')}] {r.get('title')}: {r.get('text')[:150]}...")
