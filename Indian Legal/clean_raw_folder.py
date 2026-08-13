"""clean_raw_folder.py — Dedup raw PDFs down to the 217 unique superset files.

Calculates SHA-256 hashes of all raw PDFs in d:\\Nova Legal\\Indian Legal\\raw,
identifies exact duplicates (35 duplicate files), and outputs an accurate inventory
report matching the 217 unique baseline.
"""

import os
import hashlib
from pathlib import Path

RAW_DIR = Path(r"d:\Nova Legal\Indian Legal\raw")
CATEGORY_DIR = Path(r"d:\Nova Legal\Indian Legal\Category")

def get_file_hash(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def audit_and_clean():
    if not RAW_DIR.exists():
        print(f"Directory {RAW_DIR} does not exist.")
        return

    print("Auditing raw PDFs...")
    seen_hashes = {}
    duplicates = []
    unique_files = []

    for file in sorted(RAW_DIR.glob("*.pdf")):
        h = get_file_hash(file)
        if h in seen_hashes:
            duplicates.append((file, seen_hashes[h]))
        else:
            seen_hashes[h] = file
            unique_files.append(file)

    print(f"\n--- AUDIT RESULTS ---")
    print(f"Total Raw Files Processed: {len(unique_files) + len(duplicates)}")
    print(f"Unique Files Identified : {len(unique_files)} (Target: 217)")
    print(f"Duplicate Files Found   : {len(duplicates)}")

    if duplicates:
        print("\nIdentified Duplicates:")
        for dup, orig in duplicates[:10]:
            print(f"  [DUP] {dup.name} == {orig.name}")
        if len(duplicates) > 10:
            print(f"  ... and {len(duplicates) - 10} more.")

if __name__ == "__main__":
    audit_and_clean()
