"""Merge all data/*.json scraper outputs + the existing public/doctors.json
into a single deduped public/doctors.json.

Run:
    python scripts/merge-sources.py            # merges everything under data/
    python scripts/merge-sources.py --dry-run  # prints stats, doesn't write
    python scripts/merge-sources.py --reset    # ignore existing doctors.json

Dedup rule (matches scripts/migrate-and-dedup.mjs):
    Key = (country, lower(name), lower(primary city))
    Collisions are merged: addresses[] and phones[] union'd by canonical form.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import DATA_DIR, PUBLIC_DIR, log


def norm(s: str | None) -> str:
    return (s or "").strip().lower()


def addr_key(a: dict) -> str:
    return "|".join([norm(a.get("address")), norm(a.get("city")), (a.get("postalCode") or "")])


def phone_key(p: dict) -> str:
    return (p.get("raw") or "")


def primary_city(rec: dict) -> str:
    addrs = rec.get("addresses") or []
    return addrs[0].get("city", "") if addrs else ""


def merge_pair(target: dict, incoming: dict) -> dict:
    """Merge `incoming` into `target` in place, returning target."""
    if not target.get("email") and incoming.get("email"):
        target["email"] = incoming["email"]
    for field in ("profileUrl", "specialty", "subSpecialty", "convention"):
        if not target.get(field) and incoming.get(field):
            target[field] = incoming[field]

    addrs = {addr_key(a): a for a in target.get("addresses") or []}
    for a in incoming.get("addresses") or []:
        addrs.setdefault(addr_key(a), a)
    target["addresses"] = list(addrs.values())

    phones = {phone_key(p): p for p in target.get("phones") or []}
    for p in incoming.get("phones") or []:
        if p.get("raw"):
            phones.setdefault(phone_key(p), p)
    target["phones"] = list(phones.values())
    return target


def merge_all(existing: list[dict], new_groups: list[tuple[str, list[dict]]],
              reset: bool = False) -> list[dict]:
    bucket: dict[tuple, dict] = {}

    def add(rec: dict, source: str) -> None:
        if not rec.get("name"):
            return
        country = rec.get("country") or "FR"
        key = (country, norm(rec.get("name")), norm(primary_city(rec)))
        if key in bucket:
            merge_pair(bucket[key], rec)
        else:
            rec.setdefault("country", country)
            bucket[key] = dict(rec)
        bucket[key]["_sources"] = list(set(bucket[key].get("_sources", []) + [source]))

    if not reset:
        for rec in existing:
            add(rec, "existing")

    for source_name, recs in new_groups:
        for rec in recs:
            add(rec, source_name)

    merged = list(bucket.values())

    # Re-number ids per country in stable name order
    by_country: dict[str, list[dict]] = {}
    for r in merged:
        by_country.setdefault(r["country"], []).append(r)
    for country, items in by_country.items():
        items.sort(key=lambda r: r["name"].lower())
        prefix = country.lower()
        for i, item in enumerate(items, start=1):
            item["id"] = f"{prefix}-{i}"
            item.pop("_sources", None)

    return [r for items in by_country.values() for r in items]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--output", type=Path, default=PUBLIC_DIR / "doctors.json")
    ap.add_argument("--reset", action="store_true",
                    help="Ignore existing doctors.json; rebuild from data/ only.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    existing = []
    if args.output.exists():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
    log(f"existing records: {len(existing)}")

    new_groups: list[tuple[str, list[dict]]] = []
    for path in sorted(args.data_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"skip {path.name}: {e}")
            continue
        log(f"+ {path.name}: {len(data)} records")
        new_groups.append((path.stem, data))

    merged = merge_all(existing, new_groups, reset=args.reset)

    # Stats per country
    by_country: dict[str, int] = {}
    for r in merged:
        by_country[r["country"]] = by_country.get(r["country"], 0) + 1
    log("merged totals:")
    for c, n in sorted(by_country.items()):
        log(f"  {c}: {n}")
    log(f"  total: {len(merged)}")

    if args.dry_run:
        log("(dry run — not writing)")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(merged, ensure_ascii=False, indent=None),
                           encoding="utf-8")
    log(f"wrote → {args.output}")


if __name__ == "__main__":
    main()
