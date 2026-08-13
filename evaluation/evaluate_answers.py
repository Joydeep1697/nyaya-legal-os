"""evaluate_answers.py — Evaluates Legal & Citation Accuracy against ground truth sections.
"""

from typing import List, Dict, Any

def evaluate_legal_accuracy(predictions: List[Dict[str, Any]]) -> Dict[str, float]:
    correct_section = 0
    correct_act = 0
    total = len(predictions)
    
    if total == 0:
        return {"section_accuracy": 0.0, "act_accuracy": 0.0}

    for item in predictions:
        exp_sec = item.get("expected_section", "")
        exp_act = item.get("expected_act", "")
        ans_text = item.get("model_answer", "")

        if exp_sec and exp_sec in ans_text:
            correct_section += 1
        if exp_act and exp_act in ans_text:
            correct_act += 1

    return {
        "section_accuracy": round(correct_section / total, 4),
        "act_accuracy": round(correct_act / total, 4)
    }

if __name__ == "__main__":
    sample = [
        {"expected_section": "103", "expected_act": "BNS", "model_answer": "Under BNS Section 103, murder is punishable..."},
        {"expected_section": "173", "expected_act": "BNSS", "model_answer": "Zero FIR is governed under BNSS Section 173."}
    ]
    print("Legal Accuracy Metrics Sample:", evaluate_legal_accuracy(sample))
