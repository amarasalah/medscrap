"""Scan public/doctors.json for residual duplicates beyond what merge-sources.py
catches, and (optionally) collapse them.

Signals checked:
  - Same primary phone (raw digits) within country
  - Same lat/lng rounded to ~10m precision (4 decimals) within country
  - Same exact normalized address within country

Run:
    python scripts/audit-dedup.py                # report only
    python scripts/audit-dedup.py --apply        # write deduped doctors.json
    python scripts/audit-dedup.py --apply --strict-phone-only
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import PUBLIC_DIR, log


def norm(s: str | None) -> str:
    return (s or "").strip().lower()


def name_root(name: str) -> str:
    """Strip common honorifics so 'Dr. Jean X' and 'Jean X' match."""
    n = norm(name)
    for prefix in ("dr. ", "dr ", "docteur ", "pr. ", "pr ", "professeur ",
                   "cabinet ", "cabinet du dr ", "cabinet du docteur "):
        if n.startswith(prefix):
            n = n[len(prefix):]
    return n.strip()


def addr_norm(a: dict) -> str:
    return f"{norm(a.get('address'))}|{norm(a.get('city'))}|{a.get('postalCode') or ''}"


def coord_key(a: dict, country: str) -> str | None:
    lat = a.get("lat")
    lng = a.get("lng")
    if lat is None or lng is None:
        return None
    return f"{country}|{round(float(lat), 4)}|{round(float(lng), 4)}"


def primary_phone(rec: dict) -> str | None:
    phs = rec.get("phones") or []
    return (phs[0].get("raw") if phs else None) or None


def merge_into(target: dict, incoming: dict) -> None:
    """Union addresses/phones; keep richer string fields."""
    addrs = {addr_norm(a): a for a in target.get("addresses") or []}
    for a in incoming.get("addresses") or []:
        addrs.setdefault(addr_norm(a), a)
    target["addresses"] = list(addrs.values())

    phones = {(p.get("raw") or ""): p for p in target.get("phones") or []}
    for p in incoming.get("phones") or []:
        if p.get("raw"):
            phones.setdefault(p.get("raw"), p)
    target["phones"] = [p for k, p in phones.items() if k]

    for field in ("email", "profileUrl", "website", "specialty",
                  "subSpecialty", "convention"):
        if not target.get(field) and incoming.get(field):
            target[field] = incoming[field]
    # Prefer the longer/more complete name
    if len(incoming.get("name", "")) > len(target.get("name", "")):
        target["name"] = incoming["name"]


def union_find(n: int):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    return find, union


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=PUBLIC_DIR / "doctors.json")
    ap.add_argument("--apply", action="store_true",
                    help="write the deduped result back to --input")
    ap.add_argument("--strict-phone-only", action="store_true",
                    help="only collapse on shared phone (skip coord/address signals)")
    args = ap.parse_args()

    records: list[dict] = json.loads(args.input.read_text(encoding="utf-8"))
    log(f"loaded {len(records)} records from {args.input}")

    # Build collision groups
    by_phone: dict[str, list[int]] = defaultdict(list)
    by_coord: dict[str, list[int]] = defaultdict(list)
    by_addr: dict[str, list[int]] = defaultdict(list)

    for i, r in enumerate(records):
        country = r.get("country") or ""
        ph = primary_phone(r)
        if ph and len(ph) >= 7:
            by_phone[f"{country}|{ph}"].append(i)
        for a in r.get("addresses") or []:
            ck = coord_key(a, country)
            if ck:
                by_coord[ck].append(i)
            ak = f"{country}|{addr_norm(a)}"
            if a.get("address"):
                by_addr[ak].append(i)

    def colliding(d):
        return {k: v for k, v in d.items() if len(v) > 1}

    phone_dups = colliding(by_phone)
    coord_dups = colliding(by_coord)
    addr_dups = colliding(by_addr)

    log(f"phone collisions: {len(phone_dups)} groups, "
        f"{sum(len(v) for v in phone_dups.values())} records affected")
    log(f"coord collisions: {len(coord_dups)} groups, "
        f"{sum(len(v) for v in coord_dups.values())} records affected")
    log(f"address collisions: {len(addr_dups)} groups, "
        f"{sum(len(v) for v in addr_dups.values())} records affected")

    # Sample
    log("\nsample phone collisions (top 5):")
    for k, ids in list(phone_dups.items())[:5]:
        names = [records[i]["name"] for i in ids]
        log(f"  {k} → {names}")

    # Build union-find of records that should merge
    find, union = union_find(len(records))
    sources = [phone_dups]
    if not args.strict_phone_only:
        sources += [coord_dups, addr_dups]

    for groups in sources:
        for ids in groups.values():
            for j in ids[1:]:
                # Only merge when name roots are similar OR identical
                # (to avoid collapsing distinct doctors sharing a clinic phone).
                # Heuristic: same name_root OR one is substring of the other.
                a_name = name_root(records[ids[0]]["name"])
                b_name = name_root(records[j]["name"])
                if (a_name and b_name and (a_name == b_name
                        or a_name in b_name or b_name in a_name)):
                    union(ids[0], j)

    # Group and merge
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(records)):
        groups[find(i)].append(i)

    merged: list[dict] = []
    collapsed = 0
    for root, idxs in groups.items():
        if len(idxs) == 1:
            merged.append(records[idxs[0]])
            continue
        # Merge all in idxs into the first
        target = dict(records[idxs[0]])
        for j in idxs[1:]:
            merge_into(target, records[j])
            collapsed += 1
        merged.append(target)

    # Re-number ids per country
    by_country: dict[str, list[dict]] = defaultdict(list)
    for r in merged:
        by_country[r.get("country") or "FR"].append(r)
    out: list[dict] = []
    for country, items in by_country.items():
        items.sort(key=lambda r: (r.get("name") or "").lower())
        prefix = country.lower()
        for i, item in enumerate(items, start=1):
            item["id"] = f"{prefix}-{i}"
            out.append(item)

    log(f"\nwould collapse {collapsed} duplicate records")
    log(f"final total: {len(out)} (was {len(records)})")

    if not args.apply:
        log("(dry run — pass --apply to write)")
        return

    args.input.write_text(json.dumps(out, ensure_ascii=False, indent=None),
                          encoding="utf-8")
    log(f"wrote → {args.input}")


if __name__ == "__main__":
    main()
