"""Download the official French commune list from geo.api.gouv.fr (free, no key)
and write a sorted-by-population seed file for places.py.

Output: data/_fr-communes.json — list of {city, department, region, population}
sorted population DESC. Used as seeds via:

    python scripts/places.py search --query fr-urology \\
        --seeds-file data/_fr-communes.json --min-pop 50000 --max-calls 1500

Run:
    python scripts/fetch-communes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import DATA_DIR, FR_DEPT, FR_REGION, log

API = ("https://geo.api.gouv.fr/communes"
       "?fields=nom,code,codeDepartement,codeRegion,population"
       "&format=json")

# geo.api.gouv.fr returns codeRegion as the INSEE region code; map → name.
FR_REGION_BY_CODE = {
    "11": "Île-de-France", "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté", "28": "Normandie",
    "32": "Hauts-de-France", "44": "Grand Est",
    "52": "Pays de la Loire", "53": "Bretagne",
    "75": "Nouvelle-Aquitaine", "76": "Occitanie",
    "84": "Auvergne-Rhône-Alpes", "93": "Provence-Alpes-Côte d'Azur",
    "94": "Corse",
    # Outre-mer (single region label to match _lib.FR_REGION mapping)
    "01": "Outre-mer", "02": "Outre-mer", "03": "Outre-mer",
    "04": "Outre-mer", "06": "Outre-mer",
}


def main() -> None:
    log(f"GET {API}")
    r = requests.get(API, timeout=60)
    r.raise_for_status()
    raw = r.json()
    log(f"received {len(raw)} communes")

    out: list[dict] = []
    for c in raw:
        pop = c.get("population") or 0
        if not pop:
            continue  # skip communes with no INSEE population data
        dept_code = (c.get("codeDepartement") or "").strip()
        region_code = (c.get("codeRegion") or "").strip()
        dept = FR_DEPT.get(dept_code, "")
        region = FR_REGION_BY_CODE.get(region_code) or FR_REGION.get(dept, "")
        out.append({
            "city": c.get("nom", "").strip(),
            "department": dept,
            "region": region,
            "population": pop,
            "inseeCode": c.get("code", ""),
        })

    out.sort(key=lambda x: -x["population"])

    path = DATA_DIR / "_fr-communes.json"
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    # Stats
    tiers = [50_000, 20_000, 10_000, 5_000, 2_000]
    log(f"wrote {len(out)} communes → {path}")
    for t in tiers:
        n = sum(1 for c in out if c["population"] >= t)
        log(f"  pop >= {t:>6}: {n} communes")


if __name__ == "__main__":
    main()
