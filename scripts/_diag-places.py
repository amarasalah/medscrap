"""Diagnose why Places Text Search returns 0 results.

Calls the API directly and prints the full status + error_message so we can see
if it's REQUEST_DENIED, OVER_QUERY_LIMIT, INVALID_REQUEST, ZERO_RESULTS, etc.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

# Load .env.local manually (so we don't depend on dotenv being installed)
env_path = Path(__file__).resolve().parent.parent / ".env.local"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

key = os.environ.get("GOOGLE_PLACES_API_KEY")
if not key:
    print("ERROR: GOOGLE_PLACES_API_KEY not set")
    sys.exit(1)

print(f"key: ...{key[-6:]} (len {len(key)})")

queries = [
    ("Text Search (legacy)",
     "https://maps.googleapis.com/maps/api/place/textsearch/json?"
     + urlencode({"query": "urologue in Paris, FR", "key": key})),
    ("Find Place (legacy)",
     "https://maps.googleapis.com/maps/api/place/findplacefromtext/json?"
     + urlencode({"input": "Eiffel Tower", "inputtype": "textquery",
                  "fields": "place_id,name", "key": key})),
]

for label, url in queries:
    print(f"\n=== {label} ===")
    try:
        with urlopen(url, timeout=20) as resp:
            data = json.load(resp)
    except Exception as e:
        print(f"  HTTP error: {e}")
        continue
    print(f"  status: {data.get('status')}")
    if data.get("error_message"):
        print(f"  error_message: {data.get('error_message')}")
    print(f"  results count: {len(data.get('results') or data.get('candidates') or [])}")
