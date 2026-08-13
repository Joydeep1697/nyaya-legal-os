# Nyaya Darshan Legal Evaluation Benchmark v1 (Phase 5)

## 📌 Benchmark Purpose
The **Nyaya Darshan Legal Benchmark** evaluates the accuracy, retrieval precision, citation validity, obsolete law detection, and hallucination resistance of the **Nyaya Darshan Legal OS** before fine-tuning or public deployment.

## 📊 Held-Out Test Set (800 Questions Across 10 Categories)

| Category | Questions | Description |
| :--- | :---: | :--- |
| **BNS section identification** | 100 | Finding applicable BNS statutory sections |
| **BNSS procedure** | 100 | Procedural rules (remand, Zero FIR, summons) |
| **BSA evidence** | 100 | Evidence admissibility, digital certificates |
| **IPC ➔ BNS** | 75 | Historical provision conversion |
| **CrPC ➔ BNSS** | 75 | Procedural conversion |
| **IEA ➔ BSA** | 75 | Evidence conversion |
| **Legal reasoning** | 100 | Multi-step statutory application |
| **Case-law QA** | 75 | Supreme Court precedent application |
| **Current vs obsolete law** | 50 | Identifying repealed laws (Sedition, IPC 309) |
| **Hallucination / contradiction tests** | 50 | Misleading prompts (e.g., non-existent Section 999) |
| **TOTAL** | **800** | **100% Held-Out Benchmark Test Suite** |

> ⚠️ **CRITICAL GUARDRAIL**: The benchmark questions in `benchmark_800.jsonl` are strictly held out and **NEVER leaked** into the training dataset (`nyaya_darshan_instruction_dataset_v1.jsonl`).

## 🔍 Five Measurement Pillars

1. **Retrieval Accuracy**: Measures `Recall@1`, `Recall@5`, `Recall@10`, and `MRR`.
2. **Legal Accuracy**: Verifies whether the model returns the correct statutory section number and act.
3. **Citation Accuracy**: Verifies that cited sections exist in official Level 1 Bare Acts.
4. **Obsolete-Law Detection**: Verifies that legacy IPC/CrPC/IEA sections are flagged with current BNS/BNSS/BSA equivalents.
5. **Hallucination Resistance**: Verifies that fake/misleading section prompts (e.g. BNS Section 999) are explicitly refused.

## 🚀 Running the Evaluation Benchmark

Run the master evaluation runner:
```bash
python evaluation/run_benchmark.py
```
Outputs report to `evaluation/results.json`.
