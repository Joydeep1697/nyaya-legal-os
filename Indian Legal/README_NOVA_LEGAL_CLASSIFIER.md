# Nova Legal Classifier v2

## What this version adds

- More detailed legal-document taxonomy
- Legal-domain detection
- Authority-level weighting for RAG
- Court, case number, judges, parties and citations
- Sections, Rules and Articles
- One `.metadata.json` file beside each categorized PDF
- NVIDIA classification fallback only for uncertain files
- Learning from manual folder corrections
- Exact duplicate protection
- Two-hour Windows scheduling

NVIDIA NIM LLMs expose an OpenAI-compatible `/v1/chat/completions` API, so the
script uses the OpenAI Python client with NVIDIA's API base URL.

## Installation

Copy these files to:

```text
D:\Nova Legal\Indian Legal
```

Create the environment:

```powershell
cd "D:\Nova Legal\Indian Legal"

python -m venv .classifiervenv
.classifiervenv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements_nova_legal_classifier_v2.txt
```

## Configure NVIDIA

Set your API key and select a model available to your NVIDIA account:

```powershell
$env:NVIDIA_API_KEY="nvapi-your-key"
$env:NVIDIA_CLASSIFIER_MODEL="your-model-id"
```

For a persistent scheduled-task environment, store the variables for your user:

```powershell
[Environment]::SetEnvironmentVariable(
  "NVIDIA_API_KEY",
  "nvapi-your-key",
  "User"
)

[Environment]::SetEnvironmentVariable(
  "NVIDIA_CLASSIFIER_MODEL",
  "your-model-id",
  "User"
)
```

Open a new terminal after setting persistent variables.

The rules classifier always runs first. NVIDIA is called only when the result is
unclassified or below the fallback threshold.

## Manual test

```powershell
python nova_legal_classifier_v2.py `
  --raw "D:\Nova Legal\Indian Legal\raw" `
  --category "D:\Nova Legal\Indian Legal\Category" `
  --database "D:\Nova Legal\Indian Legal\category_registry_v2.sqlite3" `
  --reports "D:\Nova Legal\Indian Legal\classification_reports_v2" `
  --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe" `
  --ocr-language "eng" `
  --use-nvidia-fallback
```

## Metadata output

For:

```text
Category\central_acts\CPA2019.pdf
```

the classifier creates:

```text
Category\central_acts\CPA2019.pdf.metadata.json
```

The metadata includes:

```json
{
  "document_category": "central_acts",
  "legal_domain": "consumer_law",
  "authority_level": "central_act",
  "authority_weight": 1.25,
  "sections": ["2", "6"],
  "court": null,
  "case_number": null
}
```

This metadata should later be carried into `chunks.jsonl` and used for
intent-aware RAG filtering and authority weighting.

## Learn from your corrections

Suppose the program puts a judgment in:

```text
Category\high_court_orders
```

but it belongs in:

```text
Category\high_court_judgments
```

Move both files:

```text
example.pdf
example.pdf.metadata.json
```

to the correct folder, then run:

```powershell
python nova_legal_classifier_v2.py `
  --category "D:\Nova Legal\Indian Legal\Category" `
  --database "D:\Nova Legal\Indian Legal\category_registry_v2.sqlite3" `
  --reports "D:\Nova Legal\Indian Legal\classification_reports_v2" `
  --learn-corrections
```

Or double-click:

```text
learn_nova_legal_corrections.bat
```

The program updates the registry and learns positive filename/title/keyword
signals for that category. This is lightweight feedback learning, not model
fine-tuning.

## Schedule every two hours

Test:

```powershell
& "D:\Nova Legal\Indian Legal\run_nova_legal_classifier_v2.bat"
```

Create the scheduled task from Administrator PowerShell:

```powershell
schtasks /Create `
  /TN "Nova Legal Classifier v2" `
  /TR '"D:\Nova Legal\Indian Legal\run_nova_legal_classifier_v2.bat"' `
  /SC HOURLY `
  /MO 2 `
  /F
```

Run now:

```powershell
schtasks /Run /TN "Nova Legal Classifier v2"
```

Inspect:

```powershell
schtasks /Query /TN "Nova Legal Classifier v2" /V /FO LIST
```

## Important limitations

- Classification is evidence-based but not guaranteed to be legally perfect.
- Review `unclassified` and low-confidence metadata.
- NVIDIA receives only the filename and a bounded extracted-text excerpt for
  ambiguous files.
- This organizes and enriches documents; it does not rebuild your RAG index.
