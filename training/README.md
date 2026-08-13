# NoveLaw Training Pipeline

## 1. Overview
NoveLaw is a specialized AI legal research assistant fine-tuned on Indian legal documents. It leverages the microsoft/Phi-3.5-mini-instruct base model and is quantized to 4-bit GGUF for efficient local inference on consumer hardware.

## 2. Prerequisites
- Python 3.11
- Google Colab account (Free Tier T4 GPU)
- HuggingFace account
- Ollama (for local inference)

## 3. Dataset Generation
Run `generate_dataset.py` to create the fine-tuning dataset from the processed corpus.
```cmd
python d:\Nova Legal\training\generate_dataset.py
```
This produces `dataset.jsonl` (training) and `dataset_eval.jsonl` (evaluation).

## 4. Fine-tuning on Colab
1. Open Google Colab and create a new notebook.
2. Select T4 GPU runtime.
3. Upload `dataset.jsonl` to the Colab environment.
4. Copy the contents of `finetune_colab.py` into the notebook and run it.
5. Once complete, download the LoRA adapter or the merged model.
6. Convert to GGUF format using `llama.cpp` and quantize to `q4_k_m`.

## 5. Evaluation and Benchmarking
Run `evaluate.py` to test the model's performance on the holdout evaluation set.
```cmd
python d:\Nova Legal\training\evaluate.py --model novelaw
```

## 6. Local Deployment with Ollama
Use `deploy_ollama.py` to set up the model locally.
```cmd
python d:\Nova Legal\training\deploy_ollama.py --gguf path/to/novelaw-phi3.5-indian-legal-q4_k_m.gguf
```

## 7. Model Card
- **Base Model**: microsoft/Phi-3.5-mini-instruct (3.8B parameters)
- **Training Data**: 252 Indian legal documents (Constitution, Acts, Judgments)
- **License**: MIT (Commercial use OK)
- **Intended Use**: Legal research, summarization, entity extraction

## 8. Investor Metrics
NoveLaw enables efficient, precise legal research capabilities while running entirely locally, ensuring data privacy and reducing cloud inference costs.

## 9. Troubleshooting
- Ensure Ollama is running before executing `deploy_ollama.py`.
- If memory errors occur in Colab, reduce `per_device_train_batch_size`.
