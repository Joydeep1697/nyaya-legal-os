"""evaluate_hallucinations.py — Measures model resistance against non-existent section traps and obsolete laws.
"""

from typing import List, Dict, Any

def evaluate_hallucination_resistance(predictions: List[Dict[str, Any]]) -> Dict[str, float]:
    traps_handled = 0
    total_traps = 0

    for item in predictions:
        if item.get("is_hallucination_trap", False):
            total_traps += 1
            ans = item.get("model_answer", "").lower()
            if any(phrase in ans for phrase in ["does not exist", "not found", "no provision", "invalid section", "cannot provide"]):
                traps_handled += 1

    rate = round(traps_handled / total_traps, 4) if total_traps > 0 else 1.0
    return {
        "total_traps": total_traps,
        "traps_successfully_refused": traps_handled,
        "hallucination_resistance_rate": rate,
        "hallucination_leakage_rate": round(1.0 - rate, 4)
    }

if __name__ == "__main__":
    sample = [
        {"is_hallucination_trap": True, "model_answer": "Section 999 does not exist in BNS."},
        {"is_hallucination_trap": True, "model_answer": "Section 888 provides 5 years imprisonment."}
    ]
    print("Hallucination Resistance Metrics Sample:", evaluate_hallucination_resistance(sample))
