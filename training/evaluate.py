import json
import argparse
import requests
import math
from collections import Counter
from pathlib import Path

# Naive TF-IDF for Q&A relevance
def get_cosine_similarity(text1, text2):
    vec1 = Counter(text1.lower().split())
    vec2 = Counter(text2.lower().split())
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])
    sum1 = sum([vec1[x]**2 for x in vec1.keys()])
    sum2 = sum([vec2[x]**2 for x in vec2.keys()])
    denominator = math.sqrt(sum1) * math.sqrt(sum2)
    if not denominator:
        return 0.0
    else:
        return float(numerator) / denominator

def evaluate_model(model_name):
    eval_file = Path(r"d:\Nova Legal\training\dataset_eval.jsonl")
    if not eval_file.exists():
        print("Eval file not found!")
        return

    eval_data = []
    with open(eval_file, 'r', encoding='utf-8') as f:
        for line in f:
            eval_data.append(json.loads(line))

    results = []
    scores = []
    
    print(f"Evaluating {model_name} on {len(eval_data)} examples...")
    for idx, item in enumerate(eval_data):
        prompt = f"<|user|>\n{item['instruction']}\n{item['input']}<|end|>\n<|assistant|>\n"
        
        # Local Ollama API
        try:
            res = requests.post('http://localhost:11434/api/generate', json={
                "model": model_name,
                "prompt": prompt,
                "stream": False
            })
            generated = res.json().get('response', '')
        except Exception as e:
            generated = ""
            
        expected = item['output']
        score = get_cosine_similarity(expected, generated)
        scores.append(score)
        
        results.append({
            "instruction": item['instruction'],
            "expected": expected,
            "generated": generated,
            "score": score
        })
        
        if (idx + 1) % 10 == 0:
            print(f"Processed {idx + 1}/{len(eval_data)}")
            
    avg_score = sum(scores) / len(scores) if scores else 0
    
    print("\n--- Evaluation Report ---")
    print(f"Model: {model_name}")
    print(f"Overall Score: {avg_score:.4f}")
    
    with open(r"d:\Nova Legal\training\eval_results.json", 'w', encoding='utf-8') as f:
        json.dump({"model": model_name, "average_score": avg_score, "results": results}, f, indent=2)
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="novelaw", help="Model name in Ollama")
    args = parser.parse_args()
    evaluate_model(args.model)
