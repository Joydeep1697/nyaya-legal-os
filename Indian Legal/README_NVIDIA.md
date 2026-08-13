# Nova Legal RAG with NVIDIA NIM

This version keeps embeddings, FAISS, SQLite, keyword search, PDFs and metadata local. NVIDIA receives only the user's question and the small set of retrieved excerpts used to generate an answer. The optional reranker sends candidate excerpts to NVIDIA before generation.

## Required inputs

```text
processed_corpus/
├── rag/chunks.jsonl
├── reports/manifest.jsonl
└── unique_pdfs/
```

## 1. Install

```powershell
cd "D:\Nova Legal\Indian Legal"
python -m venv .ragvenv
.ragvenv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements_nova_legal_rag_nvidia.txt
```

## 2. Validate

```powershell
python nova_legal_rag_nvidia.py validate `
  --corpus "D:\Nova Legal\Indian Legal\processed_corpus" `
  --save "D:\Nova Legal\Indian Legal\nova_rag_index\validation.json"
```

## 3. Build local index

```powershell
python nova_legal_rag_nvidia.py build `
  --corpus "D:\Nova Legal\Indian Legal\processed_corpus" `
  --output "D:\Nova Legal\Indian Legal\nova_rag_index"
```

No NVIDIA key is needed for validation, indexing or local search.

## 4. Test local search

```powershell
python nova_legal_rag_nvidia.py search `
  --index "D:\Nova Legal\Indian Legal\nova_rag_index" `
  --question "What are the powers of the National Investigation Agency?"
```

## 5. Configure NVIDIA hosted NIM

Create an NVIDIA API key, then set it for the current PowerShell session:

```powershell
$env:NVIDIA_API_KEY="nvapi-your-key"
```

Copy a chat-capable model ID exactly from its NVIDIA API page and set it:

```powershell
$env:NVIDIA_LLM_MODEL="YOUR-NVIDIA-MODEL-ID"
```

Optional reranker model:

```powershell
$env:NVIDIA_RERANK_MODEL="nvidia/llama-nemotron-rerank-1b-v2"
```

## 6. Ask Nova Legal

Without NVIDIA reranking:

```powershell
python nova_legal_rag_nvidia.py ask `
  --index "D:\Nova Legal\Indian Legal\nova_rag_index" `
  --question "Explain the relevant provision and cite the source pages."
```

With NVIDIA reranking:

```powershell
python nova_legal_rag_nvidia.py ask `
  --index "D:\Nova Legal\Indian Legal\nova_rag_index" `
  --use-nvidia-reranker `
  --question "Explain the relevant provision and cite the source pages."
```

## 7. Interactive chat

```powershell
python nova_legal_rag_nvidia.py chat `
  --index "D:\Nova Legal\Indian Legal\nova_rag_index" `
  --use-nvidia-reranker
```

Type `exit` to stop.

## 8. Local or self-hosted NIM later

A self-hosted NIM exposes OpenAI-compatible endpoints. Point the same script at the local NIM URL:

```powershell
python nova_legal_rag_nvidia.py ask `
  --index "D:\Nova Legal\Indian Legal\nova_rag_index" `
  --nvidia-base-url "http://localhost:8000/v1" `
  --nvidia-model "MODEL-ID-FROM-LOCAL-V1-MODELS" `
  --question "Summarize the applicable law with citations."
```

For a local reranking NIM, also use:

```powershell
--rerank-base-url "http://localhost:8000/v1"
```

The generation NIM and reranking NIM may run on different ports. In that case, pass the correct base URL for each service.

## Default corpus filtering

The index excludes recruitment, examinations, guides, unknown documents, low-quality documents, empty chunks and duplicate chunk IDs. Use these only when deliberately required:

```text
--include-admin
--include-unknown
--include-low-quality
```

## Important

The exact hosted model ID must be copied from NVIDIA's current model page. Model availability can change. Always verify the original cited PDF before relying on an answer. This is a legal research tool, not legal advice.
