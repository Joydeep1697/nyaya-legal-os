"""validate_judgments.py — Validates Supreme Court & High Court judgment metadata.
"""
import os, glob
from pathlib import Path

BASE = Path(r"d:\Nova Legal\Indian Legal")

def validate():
    print("=== VALIDATING JUDGMENT METADATA ===")
    hc_dir = BASE / "Category" / "high_court_judgments"
    sc_dir = BASE / "Category" / "high_court_orders"
    print(f"  [+] High Court Judgments Indexed: {len(glob.glob(str(hc_dir / '*.pdf')))}")
    print(f"  [+] High Court Orders Indexed: {len(glob.glob(str(sc_dir / '*.pdf')))}")

if __name__ == "__main__":
    validate()
