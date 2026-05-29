#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data" / "fr-urology-filtered-fast.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total urology records: {len(data)}")
print()

# Check for specific advanced keywords
target_keywords = [
    "prp", "shockwave", "penoplastie", "pénoplastie", 
    "implant penien", "implant pénien", "implant",
    "cellules souches", "regenerative", 
    "onde de choc", "ondes de choc",
    "acide hyaluronique", "botox", "peyronie", "la peyronie"
]

print("Advanced keyword counts:")
for kw in target_keywords:
    count = 0
    for d in data:
        text = (d.get("enriched_description", "") + " " + 
                d.get("name", "") + " " + 
                d.get("specialty", "")).lower()
        if kw.lower() in text:
            count += 1
    print(f"  {kw}: {count}")

# Show sample records with specific keywords
print("\n=== Records with 'pénoplastie' or 'penoplastie' ===")
for d in data:
    text = (d.get("enriched_description", "") + d.get("name", "")).lower()
    if "pénoplastie" in text or "penoplastie" in text or "peno plastie" in text:
        print(f"  {d['name']} | {d.get('specialty')}")
        if d.get("enriched_description"):
            print(f"    {d['enriched_description'][:120]}...")
        print()

print("\n=== Records with 'onde de choc' or 'shockwave' ===")
for d in data:
    text = (d.get("enriched_description", "") + d.get("name", "")).lower()
    if "onde de choc" in text or "shockwave" in text:
        print(f"  {d['name']} | {d.get('specialty')}")
        if d.get("enriched_description"):
            print(f"    {d['enriched_description'][:120]}...")
        print()
