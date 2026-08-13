import os
import json
import csv
from pathlib import Path

# ============================================
# CHANGE THIS
# ============================================

CORPUS = Path(r"D:\Nova Legal\Indian Legal\processed_corpus")

# ============================================

REPORT = CORPUS / "reports" / "corpus_analysis.txt"

categories = [
    "acts",
    "rules",
    "judgments",
    "orders",
    "notifications",
    "circulars",
    "recruitment",
    "examinations",
    "guides",
    "unknown",
]


def folder_size(folder):
    total = 0
    for root, _, files in os.walk(folder):
        for f in files:
            path = os.path.join(root, f)
            try:
                total += os.path.getsize(path)
            except:
                pass
    return total


def readable(size):
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0

    while size > 1024 and i < len(units)-1:
        size /= 1024
        i += 1

    return f"{size:.2f} {units[i]}"


print("=" * 70)
print(" NOVA LEGAL CORPUS ANALYZER")
print("=" * 70)

total_files = 0
pdfs = 0
txts = 0
jsons = 0
jsonls = 0
csvs = 0

for root, _, files in os.walk(CORPUS):
    for file in files:
        total_files += 1

        ext = Path(file).suffix.lower()

        if ext == ".pdf":
            pdfs += 1

        elif ext == ".txt":
            txts += 1

        elif ext == ".json":
            jsons += 1

        elif ext == ".jsonl":
            jsonls += 1

        elif ext == ".csv":
            csvs += 1

print(f"\nTotal Files : {total_files}")
print(f"PDFs        : {pdfs}")
print(f"TXT         : {txts}")
print(f"JSON        : {jsons}")
print(f"JSONL       : {jsonls}")
print(f"CSV         : {csvs}")

print("\n" + "=" * 70)
print("CATEGORY COUNTS")
print("=" * 70)

category_counts = {}

unique_folder = CORPUS / "unique_pdfs"

for cat in categories:

    folder = unique_folder / cat

    count = 0

    if folder.exists():
        count = len(list(folder.glob("*.pdf")))

    category_counts[cat] = count

    print(f"{cat:<20} {count}")

print("\n" + "=" * 70)
print("RAG")
print("=" * 70)

rag_file = CORPUS / "rag" / "chunks.jsonl"

chunk_count = 0

if rag_file.exists():

    with open(rag_file, "r", encoding="utf8") as f:

        for _ in f:
            chunk_count += 1

print("Chunks:", chunk_count)

print("\n" + "=" * 70)
print("REPORTS")
print("=" * 70)

duplicates = 0
manual = 0
errors = 0

dup_file = CORPUS / "reports" / "duplicates.csv"

if dup_file.exists():
    with open(dup_file, encoding="utf8") as f:
        duplicates = max(sum(1 for _ in f)-1,0)

manual_file = CORPUS / "reports" / "manual_review.csv"

if manual_file.exists():
    with open(manual_file, encoding="utf8") as f:
        manual = max(sum(1 for _ in f)-1,0)

error_file = CORPUS / "reports" / "errors.csv"

if error_file.exists():
    with open(error_file, encoding="utf8") as f:
        errors = max(sum(1 for _ in f)-1,0)

print("Duplicates :", duplicates)
print("Manual     :", manual)
print("Errors     :", errors)

print("\n" + "=" * 70)
print("FOLDER SIZES")
print("=" * 70)

for folder in [
    "unique_pdfs",
    "clean_text",
    "structured",
    "rag",
    "reports",
]:

    path = CORPUS / folder

    if path.exists():
        print(f"{folder:<20}{readable(folder_size(path))}")

print("\n" + "=" * 70)

total_size = readable(folder_size(CORPUS))

print("TOTAL SIZE :", total_size)

print("=" * 70)

# -----------------------------------------
# SAVE REPORT
# -----------------------------------------

REPORT.parent.mkdir(exist_ok=True)

with open(REPORT, "w", encoding="utf8") as f:

    f.write("NOVA LEGAL CORPUS REPORT\n")
    f.write("="*60 + "\n\n")

    f.write(f"Total Files : {total_files}\n")
    f.write(f"PDFs : {pdfs}\n")
    f.write(f"TXT : {txts}\n")
    f.write(f"JSON : {jsons}\n")
    f.write(f"JSONL : {jsonls}\n")
    f.write(f"CSV : {csvs}\n\n")

    f.write("Categories\n")
    f.write("-"*40 + "\n")

    for k,v in category_counts.items():
        f.write(f"{k:<20}{v}\n")

    f.write("\n")

    f.write(f"RAG Chunks : {chunk_count}\n")
    f.write(f"Duplicates : {duplicates}\n")
    f.write(f"Manual Review : {manual}\n")
    f.write(f"Errors : {errors}\n")
    f.write(f"Total Size : {total_size}\n")

print("\nSaved report to:\n")
print(REPORT)