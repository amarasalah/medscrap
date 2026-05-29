#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data" / "fr-urology-filtered-fast.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total records: {len(data)}")
print()

# Check for specific keywords
target_keywords = [
    "prp", "shockwave", "penoplastie", "pénoplastie", "implant", 
    "cellules souches", "regenerative", "onde de choc", "ondes de choc",
    "acide hyaluronique", "botox", "peyronie", "injection"
]

for kw in target_keywords:
    count = sum(
        1 for d in data 
        if kw.lower() in str(d.get("enriched_description", "")).lower()
        or kw.lower() in str(d.get("name", "")).lower()
        or kw.lower() in str(d.get("specialty", "")).lower()
        or any(kw.lower() in mk.lower() for mk in d.get("matched_keywords", []))
    )
    print(f"  {kw}: {count} records")

# Show records with advanced keywords
print("\n=== Records with 'implant' ===")
for d in data:
    text = str(d.get("enriched_description", "")) + str(d.get("name", ""))
    if "implant" in text.lower():
        print(f"  {d['name']} | {d.get('specialty')} | {d.get('matched_keywords')[:3]}")
        if d.get("enriched_description"):
            desc = d["enriched_description"][:100] + "..."
            print(f"    Desc: {desc}")
        print()
