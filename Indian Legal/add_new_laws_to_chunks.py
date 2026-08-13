"""add_new_laws_to_chunks.py — Converts BNS, BNSS, and BSA bare acts into chunk objects and appends to chunks.jsonl
"""

import json
import re
import fitz
from pathlib import Path

BASE_DIR = Path(r"d:\Nova Legal\Indian Legal")
CHUNKS_FILE = BASE_DIR / "processed_corpus" / "rag" / "chunks.jsonl"
RAW_DIR = BASE_DIR / "raw"

FILES = [
    ("BNS", RAW_DIR / "250883_english_01042024 (1).pdf", "Bharatiya Nyaya Sanhita, 2023", "central_acts"),
    ("BNSS", RAW_DIR / "A202346.pdf", "Bharatiya Nagarik Suraksha Sanhita, 2023", "central_acts"),
    ("BSA", RAW_DIR / "aa202347.pdf", "Bharatiya Sakshya Adhiniyam, 2023", "central_acts")
]

def chunk_pdf(doc_code, pdf_path, title, category):
    doc = fitz.open(pdf_path)
    chunks = []
    chunk_size = 3500
    
    current_text = ""
    start_page = 1
    chunk_idx = 1
    
    for page_num, page in enumerate(doc, 1):
        text = page.get_text()
        current_text += f"\n--- Page {page_num} ---\n" + text
        
        if len(current_text) >= chunk_size or page_num == len(doc):
            chunk_obj = {
                "row_id": 900000 + hash(f"{doc_code}_{chunk_idx}") % 100000,
                "chunk_id": f"{doc_code}_chunk_{chunk_idx}",
                "document_id": doc_code,
                "document_type": category,
                "title": title,
                "text": current_text.strip(),
                "page_start": start_page,
                "page_end": page_num,
                "heading": f"{title} - Part {chunk_idx}",
                "sha256": "",
                "source_file": pdf_path.name,
                "stored_pdf": pdf_path.name,
                "warnings": [],
                "quality_score": 1.0
            }
            chunks.append(chunk_obj)
            chunk_idx += 1
            current_text = ""
            start_page = page_num + 1
            
    return chunks

def main():
    print("Extracting chunks for new criminal laws...")
    new_chunks = []
    for code, path, title, cat in FILES:
        if path.exists():
            c = chunk_pdf(code, path, title, cat)
            new_chunks.extend(c)
            print(f"  [+] Generated {len(c)} chunks for {title}")
            
    if CHUNKS_FILE.exists():
        with open(CHUNKS_FILE, "a", encoding="utf-8") as f:
            for ch in new_chunks:
                f.write(json.dumps(ch, ensure_ascii=False) + "\n")
        print(f"Appended {len(new_chunks)} chunks to {CHUNKS_FILE}")

if __name__ == "__main__":
    main()
