"""Scrape French health professionals from sante.fr via a real browser
(Playwright), with Google Places API enrichment for missing phones.

Run:
    pip install -r scripts/requirements.txt
    playwright install chromium
    python scripts/scrape-france.py --source sante --specialty gynecologie --max-pages 20
    python scripts/scrape-france.py --source sante --specialty urologie    --max-pages 20
    python scripts/scrape-france.py --source maps  --enrich data/fr-sante-gynecologie.json

Sources
-------

`sante` (sante.fr) — public registry. The site is a Vue SPA behind Imperva,
so HTTP-only scraping returns nothing. This module drives a real Chromium
through Playwright instead. Selectors are tuned to the December-2024 DOM
(li.block-content-item.content-item-new-bloc); if they break, run
scripts/_recon_sante.py to dump the rendered HTML and re-tune.

`maps` (Google Places API, official) — enrichment only. Reads an existing
file and fills missing phones / geocoords via the paid Places API. Requires
GOOGLE_PLACES_API_KEY (we auto-load from .env.local).

`doctolib` — left as a documented stub. Doctolib's ToS forbids scraping and
they use Datadome aggressively. Even Playwright is unreliable without a
residential-proxy + stealth setup. Not implemented.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (
    DATA_DIR, fetch, fr_geo_from_postal, log, make_address, make_phone,
    make_record, make_session, polite_sleep, read_json, write_jsonl,
)

SANTE_BASE = "https://www.sante.fr"

SPECIALTIES = {
    "urologie": {"search": "urologue", "label": "Chirurgien urologue"},
    "gynecologie": {"search": "gynecologue", "label": "Gynécologue"},
    "gynecologie-obstetrique": {"search": "gynecologue-obstetricien",
                                "label": "Gynécologue-obstétricien"},
    "dermato": {"search": "dermatologue", "label": "Dermatologue"},
}


def scrape_sante(specialty: str, max_pages: int = 50) -> list[dict]:
    """Drive sante.fr via Playwright. Returns deduped records."""
    from playwright.sync_api import sync_playwright

    cfg = SPECIALTIES[specialty]
    out: list[dict] = []
    seen: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            locale="fr-FR",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
        )
        page = ctx.new_page()

        for page_n in range(1, max_pages + 1):
            url = f"{SANTE_BASE}/recherche/trouver/{cfg['search']}?page={page_n}"
            log(f"sante.fr {specialty} page {page_n} -> {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_selector("li.block-content-item.content-item-new-bloc",
                                       timeout=20000)
                page.wait_for_timeout(1500)  # let cards finish hydrating
            except Exception as e:
                log(f"  page failed: {e}")
                break

            html = page.content()
            new_on_page = parse_sante_listing(html, specialty, out, seen)
            log(f"  parsed {new_on_page} new records (total {len(out)})")
            if new_on_page == 0:
                log("  no new cards, stopping pagination")
                break

        browser.close()
    return out


def parse_sante_listing(html: str, specialty: str, out: list[dict],
                        seen: set[str]) -> int:
    from bs4 import BeautifulSoup
    cfg = SPECIALTIES[specialty]
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("li.block-content-item.content-item-new-bloc")
    added = 0

    for card in cards:
        title_a = card.select_one(".card-title h2 a")
        if not title_a:
            continue
        name = title_a.get_text(" ", strip=True)
        profile_url = urljoin(SANTE_BASE, title_a.get("href", ""))
        if profile_url in seen:
            continue
        seen.add(profile_url)

        type_el = card.select_one(".temp-type-card")
        kind = (type_el.get_text(strip=True) if type_el else "").strip()
        if kind not in ("professionnel_de_sante", "health_institution"):
            kind = "professionnel_de_sante"

        pos_el = card.select_one(".b-position")
        specialty_label = pos_el.get_text(" ", strip=True) if pos_el else cfg["label"]

        sub_el = card.select_one(".list-specialities li")
        sub_specialty = sub_el.get_text(" ", strip=True) if sub_el else ""

        # Address card: .card-elm-item containing .icon-pin
        address = ""
        lat = lng = None
        maps_url = ""
        for item in card.select(".card-elm-item"):
            if item.select_one(".icon-pin"):
                a = item.select_one("a[href*='maps']")
                if a:
                    address = a.get_text(" ", strip=True)
                    maps_url = a.get("href", "")
                    m = re.search(r"/([-\d.]+),([-\d.]+)$", maps_url)
                    if m:
                        try:
                            lat = float(m.group(1)); lng = float(m.group(2))
                        except ValueError:
                            pass
                break
        postal = ""
        city = ""
        pm = re.search(r"\b(\d{5})\b\s+([^,\n]+)$", address)
        if pm:
            postal = pm.group(1)
            city = pm.group(2).strip()
        dept, region = fr_geo_from_postal(postal)

        # Convention card: .card-elm-item containing .icon-card
        convention = None
        for item in card.select(".card-elm-item"):
            if item.select_one(".icon-card"):
                lbl = item.select_one(".labels")
                if lbl:
                    convention = lbl.get_text(" ", strip=True)
                break

        # Phone card: .card-elm-item containing .icon-cards-phone
        phone_raw = ""
        for item in card.select(".card-elm-item"):
            if item.select_one(".icon-cards-phone"):
                tel = item.select_one("a[href^='tel:']")
                if tel:
                    phone_raw = tel.get("href", "")[4:]
                else:
                    txt = item.get_text(" ", strip=True)
                    m = re.search(r"(?:\+33\s?|0)[1-9](?:[\s.-]?\d{2}){4}", txt)
                    if m:
                        phone_raw = m.group(0)
                break

        out.append(make_record(
            country="FR",
            type_=kind,
            name=name,
            specialty=specialty_label,
            sub_specialty=sub_specialty,
            profile_url=profile_url,
            phones=[make_phone("FR", phone_raw)] if phone_raw else [],
            addresses=[make_address(
                address=address, city=city, postal_code=postal,
                department=dept, region=region,
                lat=lat, lng=lng, maps_url=maps_url,
            )] if address else [],
            convention=convention,
        ))
        added += 1
    return added


# --- Google Places API enrichment ---

def enrich_with_places(input_path: Path) -> list[dict]:
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        log("GOOGLE_PLACES_API_KEY not set (looked in .env.local too).")
        return []

    records = read_json(input_path)
    session = make_session()
    out: list[dict] = []
    enriched_count = 0

    for i, rec in enumerate(records):
        needs_phone = not rec.get("phones")
        addr0 = (rec.get("addresses") or [{}])[0]
        needs_geo = addr0 and (addr0.get("lat") is None or addr0.get("lng") is None)
        if not needs_phone and not needs_geo:
            out.append(rec)
            continue

        query = " ".join(filter(None, [
            rec.get("name", ""), addr0.get("address", ""),
            addr0.get("postalCode", ""), addr0.get("city", ""),
        ]))
        find_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        r = fetch(session, find_url, params={
            "input": query, "inputtype": "textquery",
            "fields": "place_id,formatted_address,geometry", "key": api_key,
        })
        if not r:
            out.append(rec); continue
        cand = (r.json().get("candidates") or [None])[0]
        if not cand:
            out.append(rec); continue

        d = fetch(session, "https://maps.googleapis.com/maps/api/place/details/json",
                  params={"place_id": cand["place_id"],
                          "fields": "formatted_phone_number,international_phone_number,"
                                    "website,geometry",
                          "key": api_key})
        details = (d.json().get("result") if d else {}) or {}

        new_phone = details.get("formatted_phone_number") or details.get(
            "international_phone_number")
        if new_phone and needs_phone:
            rec["phones"] = [make_phone("FR", new_phone)]
        loc = (details.get("geometry") or {}).get("location") or {}
        if loc and addr0:
            addr0["lat"] = loc.get("lat") or addr0.get("lat")
            addr0["lng"] = loc.get("lng") or addr0.get("lng")
        if not rec.get("profileUrl") and details.get("website"):
            rec["profileUrl"] = details["website"]

        out.append(rec)
        enriched_count += 1
        if i % 25 == 0:
            log(f"places: processed {i}/{len(records)} (enriched {enriched_count})")
        polite_sleep(0.2, 0.4)

    log(f"places: enriched {enriched_count} records")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["sante", "maps"], required=True)
    ap.add_argument("--specialty", choices=list(SPECIALTIES), default="urologie")
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--enrich", type=Path, help="(maps) input JSON to enrich")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    if args.source == "sante":
        records = scrape_sante(args.specialty, max_pages=args.max_pages)
        out = args.out or (DATA_DIR / f"fr-sante-{args.specialty}.json")
    else:
        if not args.enrich:
            ap.error("--enrich PATH required for source=maps")
        records = enrich_with_places(args.enrich)
        out = args.out or args.enrich.with_name(args.enrich.stem + "-enriched.json")

    write_jsonl(out, records)
    log(f"wrote {len(records)} records -> {out}")


if __name__ == "__main__":
    main()
