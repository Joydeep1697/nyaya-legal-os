"""Import existing processed documents into Nova Legal app database.

Reads all .metadata.json files from Category/ and populates vault_documents,
document_entities, and related tables so the UI shows all 252 documents.

Usage:  .venv\\Scripts\\python import_existing.py
"""

import json
import sys
import os
import hashlib
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("LLM_PROVIDER", "nvidia")

from app.database import get_db

CATEGORY_DIR = Path("Indian Legal/Category")
RAW_DIR = Path("Indian Legal/raw")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    db = get_db()

    # Check how many already imported
    existing = db.count_documents()
    if existing > 0:
        print(f"Database already has {existing} documents. Skipping import.")
        print("To re-import, delete app/nova_app.sqlite3 and run again.")
        return

    metadata_files = list(CATEGORY_DIR.rglob("*.metadata.json"))
    print(f"Found {len(metadata_files)} metadata files to import", flush=True)

    raw_file_map = {p.name.lower(): p for p in RAW_DIR.glob("*") if p.is_file()}

    imported = 0
    entities_count = 0

    for meta_path in metadata_files:
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            # Find the PDF filename
            pdf_name = meta_path.stem.replace(".metadata", "")
            if not pdf_name.endswith(".pdf") and not pdf_name.endswith(".PDF"):
                pdf_name += ".pdf"

            raw_path = raw_file_map.get(pdf_name.lower())
            file_size = raw_path.stat().st_size if raw_path and raw_path.exists() else 0
            sha256 = sha256_file(raw_path) if raw_path and raw_path.exists() else None

            # Use db.create_document + db.update_document
            doc_id = db.create_document(
                filename=pdf_name,
                file_size=file_size,
                raw_path=str(raw_path) if raw_path and raw_path.exists() else "",
            )

            # Update with classification metadata
            db.update_document(
                doc_id,
                sha256=sha256,
                status="indexed",
                category=meta.get("document_category", ""),
                domain=meta.get("legal_domain", ""),
                authority_level=meta.get("authority_level", "unknown"),
                authority_weight=meta.get("authority_weight", 0.5),
                pages=meta.get("page_count", 0),
                summary=meta.get("title", pdf_name),
                process_time=datetime.now().isoformat(),
            )

            # Build entities list
            entities = []

            if meta.get("court"):
                entities.append({"type": "court", "value": meta["court"]})

            for judge in meta.get("judges", []):
                entities.append({"type": "judge", "value": judge})

            if meta.get("parties", {}).get("petitioner_or_appellant"):
                entities.append({"type": "petitioner", "value": meta["parties"]["petitioner_or_appellant"]})

            if meta.get("parties", {}).get("respondent"):
                entities.append({"type": "respondent", "value": meta["parties"]["respondent"]})

            if meta.get("case_number"):
                entities.append({"type": "case_number", "value": meta["case_number"]})

            if meta.get("act_name"):
                entities.append({"type": "act_name", "value": meta["act_name"]})

            for sec in meta.get("sections", []):
                entities.append({"type": "section", "value": f"Section {sec}"})

            for rule in meta.get("rules", []):
                entities.append({"type": "rule", "value": f"Rule {rule}"})

            for article in meta.get("articles", []):
                entities.append({"type": "article", "value": f"Article {article}"})

            if meta.get("neutral_citation"):
                entities.append({"type": "citation", "value": meta["neutral_citation"]})

            for cit in meta.get("reported_citations", []):
                entities.append({"type": "citation", "value": cit})

            if meta.get("year"):
                entities.append({"type": "year", "value": str(meta["year"])})

            if meta.get("decision_date"):
                entities.append({"type": "decision_date", "value": meta["decision_date"]})

            if entities:
                db.add_entities(doc_id, entities)
                entities_count += len(entities)

            # Add section index entries
            section_entries = []
            for sec in meta.get("sections", []):
                section_entries.append({"ref": f"Section {sec}", "context_type": "contains"})
            for art in meta.get("articles", []):
                section_entries.append({"ref": f"Article {art}", "context_type": "contains"})
            if section_entries:
                db.add_section_entries(doc_id, section_entries)

            imported += 1
            if imported % 50 == 0:
                print(f"  ... imported {imported}/{len(metadata_files)}")

        except Exception as e:
            print(f"  ⚠ Error importing {meta_path.name}: {e}")

    # Log activity
    db.log_activity("system", "bulk_import", f"Imported {imported} existing documents into app database")

    print(f"\n✅ Import complete!")
    print(f"   Documents: {imported}")
    print(f"   Entities:  {entities_count}")
    print(f"   Database:  app/nova_app.sqlite3")
    print(f"\n   Open http://localhost:8000 to see them in the UI!")


if __name__ == "__main__":
    main()
