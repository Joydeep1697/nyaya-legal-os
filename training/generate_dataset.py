import json
import os
import random
import glob
from pathlib import Path

# Paths
BASE_DIR = Path(r"d:\Nova Legal")
CHUNKS_FILE = BASE_DIR / "Indian Legal" / "processed_corpus" / "rag" / "chunks.jsonl"
CATEGORY_DIR = BASE_DIR / "Indian Legal" / "Category"
OUT_DIR = BASE_DIR / "training"
DATASET_FILE = OUT_DIR / "dataset.jsonl"
EVAL_FILE = OUT_DIR / "dataset_eval.jsonl"

def generate_dataset():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    chunks = []
    if CHUNKS_FILE.exists():
        with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
    else:
        print(f"Warning: Chunks file not found at {CHUNKS_FILE}")
        
    metadata_files = list(CATEGORY_DIR.glob("**/*.metadata.json"))
    metadata_list = []
    for mf in metadata_files:
        with open(mf, 'r', encoding='utf-8') as f:
            metadata_list.append(json.load(f))
            
    dataset = []
    
    # Type 1: Legal Q&A
    for chunk in chunks:
        title = chunk.get("title", "Unknown Document")
        heading = chunk.get("heading", "")
        text = chunk.get("text", "")
        if not text:
            continue
            
        questions = [
            f"What does {title} say about {heading}?",
            f"Explain the provisions related to {heading} in {title}",
            f"What are the key points of {title} regarding {heading}?",
            f"Summarize the content of {heading} from {title}"
        ]
        
        q = random.choice(questions)
        dataset.append({
            "type": "qa",
            "instruction": q,
            "input": "",
            "output": text.strip()
        })
        
    # Type 2: Classification
    for md in metadata_list:
        text_excerpt = md.get("title", "Legal Document")
        category = md.get("category", "Unknown")
        domain = md.get("domain", "Unknown")
        auth_level = md.get("authority_level", "Unknown")
        
        dataset.append({
            "type": "classification",
            "instruction": "Classify the following legal document excerpt.",
            "input": text_excerpt,
            "output": f"Category: {category}\nDomain: {domain}\nAuthority Level: {auth_level}"
        })
        
    # Type 3: Summarization
    for chunk in chunks:
        text = chunk.get("text", "")
        title = chunk.get("title", "Unknown")
        if len(text) > 500:
            dataset.append({
                "type": "summarization",
                "instruction": f"Summarize this excerpt from {title}:",
                "input": text[:2000],
                "output": f"This text from {title} discusses key provisions relating to its main subject matter." # Placeholder for actual summary
            })
            
    # Type 4: Legal Reasoning (simplified)
    if len(chunks) > 1:
        for _ in range(min(1000, len(chunks))):
            c1, c2 = random.sample(chunks, 2)
            t1, t2 = c1.get("title", ""), c2.get("title", "")
            if t1 and t2:
                dataset.append({
                    "type": "reasoning",
                    "instruction": f"Compare or connect the concepts from {t1} and {t2}.",
                    "input": f"Doc 1: {c1.get('text', '')[:500]}\nDoc 2: {c2.get('text', '')[:500]}",
                    "output": "Both documents relate to Indian legal frameworks, providing different contexts or provisions."
                })
                
    # Type 5: Entity Extraction
    for md in metadata_list:
        text_excerpt = md.get("title", "Legal Document")
        entities = {
            "court": md.get("court", "N/A"),
            "year": md.get("year", "N/A")
        }
        dataset.append({
            "type": "extraction",
            "instruction": "Extract the legal entities (Court, Year) from the following text.",
            "input": text_excerpt,
            "output": json.dumps(entities)
        })
        
    random.shuffle(dataset)
    
    # Split eval
    eval_dataset = dataset[:100]
    train_dataset = dataset[100:]
    
    with open(DATASET_FILE, 'w', encoding='utf-8') as f:
        for item in train_dataset:
            json.dump({"instruction": item["instruction"], "input": item["input"], "output": item["output"]}, f)
            f.write("\n")
            
    with open(EVAL_FILE, 'w', encoding='utf-8') as f:
        for item in eval_dataset:
            json.dump({"instruction": item["instruction"], "input": item["input"], "output": item["output"]}, f)
            f.write("\n")
            
    print(f"Generated {len(train_dataset)} training examples and {len(eval_dataset)} eval examples.")

if __name__ == "__main__":
    generate_dataset()
