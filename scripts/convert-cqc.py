"""Convert the CQC monthly directory CSV into the unified schema.

The CQC publishes a free, no-key-required CSV at
https://www.cqc.org.uk/about-us/transparency/using-cqc-data each month.
Every registered care location in England is listed with name, address,
postcode, phone, region, and a 'Specialisms/services' string.

Run:
    python scripts/convert-cqc.py data/cqc-directory.csv \\
        --keywords dermatology aesthetic cosmetic skin urology
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (
    DATA_DIR, UK_COUNTY_REGION, log, make_address, make_phone, make_record,
    write_jsonl,
)

HEADER_LINE = 4  # 0-indexed; preamble is 4 rows before the column header

SPECIALTY_LABEL = {
    "dermatology": "Dermatology",
    "aesthetic": "Aesthetic medicine",
    "cosmetic": "Aesthetic medicine",
    "skin": "Dermatology",
    "urology": "Urology",
    "urological": "Urology",
}


def classify(haystack: str, keywords: list[str]) -> tuple[bool, str]:
    low = haystack.lower()
    for kw in keywords:
        if kw.lower() in low:
            return True, SPECIALTY_LABEL.get(kw.lower(), kw.title())
    return False, ""


def convert(csv_path: Path, keywords: list[str]) -> list[dict]:
    out: list[dict] = []
    with csv_path.open(encoding="utf-8-sig", errors="replace", newline="") as f:
        rdr = csv.reader(f)
        for _ in range(HEADER_LINE):
            next(rdr, None)
        header = next(rdr)
        idx = {name: i for i, name in enumerate(header)}

        def col(row, name):
            i = idx.get(name)
            return (row[i].strip() if i is not None and i < len(row) else "") or ""

        for row in rdr:
            if not row or not any(row):
                continue
            specialisms = col(row, "Specialisms/services")
            service_types = col(row, "Service types")
            name = col(row, "Name")
            haystack = f"{name} | {specialisms} | {service_types}"
            ok, specialty = classify(haystack, keywords)
            if not ok:
                continue

            postcode = col(row, "Postcode")
            address = col(row, "Address")
            phone = col(row, "Phone number")
            county = col(row, "Local authority")
            region = col(row, "Region") or UK_COUNTY_REGION.get(county, "")
            website = col(row, "Service's website (if available)")
            location_url = col(row, "Location URL")
            loc_id = col(row, "CQC Location ID (for office use only)")

            full_address = ", ".join(filter(None, [address, postcode])).strip(", ")

            out.append(make_record(
                country="GB",
                type_="health_institution",
                name=name,
                specialty=specialty,
                sub_specialty=specialisms[:200],
                profile_url=location_url or website,
                phones=[make_phone("GB", phone)] if phone else [],
                addresses=[make_address(
                    address=full_address,
                    postal_code=postcode,
                    department=county,
                    region=region,
                )],
            ))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--keywords", nargs="+",
                    default=["dermatology", "aesthetic", "cosmetic", "skin", "urology"])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    records = convert(args.csv, args.keywords)
    out = args.out or (DATA_DIR / "gb-cqc-derm-uro.json")
    write_jsonl(out, records)
    log(f"converted {len(records)} CQC locations -> {out}")

    # Stats per specialty for sanity
    by_spec: dict[str, int] = {}
    for r in records:
        by_spec[r["specialty"]] = by_spec.get(r["specialty"], 0) + 1
    for k, v in sorted(by_spec.items()):
        log(f"  {k}: {v}")


if __name__ == "__main__":
    main()
