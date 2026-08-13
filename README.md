# Nova Legal OS

**AI-powered Legal Intelligence Operating System for Indian Law**

Powered by **NoveLaw** — a fine-tuned Indian Legal LLM trained on 252+ Indian legal documents spanning 36 categories and 22 legal domains.

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** (recommended)
- **Ollama** — [download here](https://ollama.com/download) (for local LLM inference)
- **Tesseract OCR** — [download here](https://github.com/UB-Mannheim/tesseract/wiki) (optional, for scanned PDFs)

### 1. Install Dependencies

```powershell
cd "D:\Nova Legal"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```powershell
copy .env.example .env
# Edit .env with your settings
```

**For local NoveLaw model (recommended):**
```
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=novelaw
```

**For NVIDIA NIM (cloud API):**
```
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-key
NVIDIA_LLM_MODEL=nvidia/llama-3.3-nemotron-super-49b-v1
```

### 3. Start the Server

```powershell
python run.py
```

### 4. Open Nova Legal OS

Navigate to **http://localhost:8000** in your browser.

---

## 🏗️ Architecture

```
Nova Legal OS
├── app/                          # FastAPI web application
│   ├── main.py                   # App entry point + lifespan
│   ├── config.py                 # Environment & path config
│   ├── database.py               # SQLite schema (11 tables)
│   ├── models.py                 # Pydantic request/response schemas
│   ├── routers/                  # API endpoints
│   │   ├── vault.py              # Knowledge Vault (upload, search, CRUD)
│   │   ├── chat.py               # AI Chat with RAG
│   │   ├── classifier.py         # Document classification
│   │   ├── dashboard.py          # Dashboard & analytics
│   │   ├── knowledge_graph.py    # Citation network
│   │   └── proactive.py          # Compliance gaps & deadlines
│   ├── intelligence/             # AI brain modules
│   │   ├── summarizer.py         # Document summaries & briefings
│   │   ├── clause_detector.py    # Legal clause detection
│   │   ├── risk_scorer.py        # Risk analysis
│   │   ├── knowledge_graph.py    # Citation graph builder
│   │   ├── deadline_extractor.py # Date/deadline extraction
│   │   └── search_engine.py      # Enhanced semantic search
│   └── static/
│       └── index.html            # Nova Legal OS v6 frontend
│
├── Indian Legal/                 # Backend engines (existing, unmodified)
│   ├── nova_legal_rag_nvidia.py  # FAISS + BM25 hybrid RAG
│   ├── nova_legal_classifier.py  # 36-category legal classifier
│   ├── nova_legal_corpus_builder.py  # PDF → text pipeline
│   ├── raw/                      # Uploaded PDFs
│   ├── processed_corpus/         # Processed text chunks
│   ├── Category/                 # Classified documents
│   └── nova_rag_index/           # FAISS vector index
│
├── training/                     # NoveLaw LLM training pipeline
│   ├── generate_dataset.py       # Generate training data from corpus
│   ├── finetune_colab.py         # QLoRA fine-tuning (Google Colab)
│   ├── evaluate.py               # Indian Legal Benchmark
│   ├── deploy_ollama.py          # Local Ollama deployment
│   ├── Modelfile                 # Ollama model configuration
│   └── README.md                 # Training documentation
│
├── requirements.txt
├── run.py
├── .env.example
└── README.md                     # ← You are here
```

## 🧠 Intelligence Features

| Feature | Description |
|---------|-------------|
| **RAG-Powered Chat** | Ask questions about Indian law — answers cite specific sections and pages |
| **Streaming Responses** | See the AI think in real-time with reasoning chain visualization |
| **Smart Document Processing** | Upload a PDF → auto-classify, extract entities, detect clauses, score risk |
| **Knowledge Graph** | Documents auto-link via shared citations and section references |
| **Semantic Search** | Natural language search: "contracts about data protection from 2023" |
| **Proactive Alerts** | Compliance gaps, outdated references, and deadline tracking |
| **AI Daily Briefing** | Dashboard shows AI-generated summary of your corpus state |

## 🎓 Training NoveLaw (Your Own LLM)

See [training/README.md](training/README.md) for complete instructions on:
1. Generating training data from your legal corpus
2. Fine-tuning Phi-3.5-mini on Google Colab (free)
3. Evaluating on the Indian Legal Benchmark
4. Deploying locally with Ollama

## 📡 API Reference

Once running, visit **http://localhost:8000/docs** for the interactive Swagger API documentation.

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/vault/upload` | POST | Upload a PDF for processing |
| `/api/vault/documents` | GET | List all documents |
| `/api/vault/search` | POST | Semantic search |
| `/api/chat/ask` | POST | Ask a legal question |
| `/api/chat/ask/stream` | POST | Streaming RAG response |
| `/api/dashboard/stats` | GET | Dashboard statistics |
| `/api/dashboard/briefing` | GET | AI daily briefing |
| `/api/graph/network` | GET | Citation network data |
| `/api/proactive/compliance-gaps` | GET | Compliance gap analysis |

## 📄 License

NoveLaw is fine-tuned from [Phi-3.5-mini-instruct](https://huggingface.co/microsoft/Phi-3.5-mini-instruct) (MIT License). The fine-tuned weights and all application code are proprietary to Nova Legal.

---

*Built with ❤️ for Indian Legal Intelligence*
