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
        exp_sec = str(item.get("expected_section", "")).strip()
        exp_act = str(item.get("expected_act", "")).strip()
        ans_text = str(item.get("model_answer", ""))
        is_trap = item.get("is_hallucination_trap", False)

        if is_trap:
            if "does not exist" in ans_text.lower() or "not exist" in ans_text.lower() or "repealed" in ans_text.lower() or "omitted" in ans_text.lower() or "no section" in ans_text.lower():
                correct_section += 1
                correct_act += 1
        else:
            if exp_sec and (exp_sec.lower() in ans_text.lower() or exp_sec in ans_text):
                correct_section += 1
            if exp_act and (exp_act.lower() in ans_text.lower() or exp_act in ans_text):
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
