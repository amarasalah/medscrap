"""Scrape UK aesthetic-dermatology + urology — STATUS: PARTIAL.

Free, scrape-friendly UK sources for this niche are scarce. Here's what
I verified live:

  * NHS Find-a-Service: the previous /service-search/find-a-clinic endpoint
    is 404. NHS.uk's redesign removed specialist clinic search; there's no
    canonical replacement URL. The current site only lists GPs/pharmacies.

  * CQC public API (api.cqc.org.uk): now returns 403 / requires registered
    subscription key. Free anonymous access is gone.

  * GMC Specialist Register: searchable, but no bulk export and no contact
    details (only credentials).

  * Doctify, Top Doctors, PrivateHealth.co.uk: commercial directories with
    aggressive anti-bot (Cloudflare/Datadome). Plausible with Playwright +
    residential IP, but ToS-restricted.

Realistic options
-----------------

1. Register a CQC API subscription key (free, manual). Their docs:
   https://api-portal.service.cqc.org.uk/. Then use the api.cqc.org.uk
   endpoints below — they return name + address + phone for every
   registered location, including private aesthetic clinics.

2. Use NHS ODS (Organisation Data Service) flat-file downloads from
   https://digital.nhs.uk/services/organisation-data-service — covers all
   NHS hospital/specialist trusts, no individual doctors.

3. Manually scrape one of the private directories with Playwright on a
   residential IP. Stub provided.

Once you have a CQC key, set it in .env.local:
    CQC_SUBSCRIPTION_KEY=...

Run:
    python scripts/scrape-uk.py --source cqc --keyword "dermatology"
    python scripts/scrape-uk.py --source cqc --keyword "aesthetic"
    python scripts/scrape-uk.py --source cqc --keyword "urology"
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (
    DATA_DIR, UK_COUNTY_REGION, log, make_address, make_phone, make_record,
    make_session, polite_sleep, write_jsonl,
)


def scrape_cqc(keyword: str, max_pages: int = 100) -> list[dict]:
    key = os.environ.get("CQC_SUBSCRIPTION_KEY")
    if not key:
        log("CQC_SUBSCRIPTION_KEY not set in .env.local; see module docstring.")
        return []

    session = make_session()
    session.headers["Ocp-Apim-Subscription-Key"] = key
    session.headers["Accept"] = "application/json"

    out: list[dict] = []
    base = "https://api.cqc.org.uk/public/v1/locations"

    for page in range(1, max_pages + 1):
        params = {"page": page, "perPage": 100}
        r = session.get(f"{base}?{urlencode(params)}", timeout=30)
        if r.status_code != 200:
            log(f"cqc page {page} HTTP {r.status_code}: {r.text[:200]}")
            break
        data = r.json()
        locs = data.get("locations") or []
        if not locs:
            break
        log(f"cqc page {page}: {len(locs)} locations")

        for loc in locs:
            name = (loc.get("name") or "").strip()
            if keyword.lower() not in name.lower():
                continue
            d = session.get(f"{base}/{loc.get('locationId')}", timeout=30)
            if d.status_code != 200:
                continue
            x = d.json()
            postal = x.get("postalCode") or ""
            county = x.get("postalAddressCounty") or ""
            region = UK_COUNTY_REGION.get(county, x.get("region") or "")
            out.append(make_record(
                country="GB",
                type_="health_institution",
                name=name,
                specialty=keyword.capitalize(),
                profile_url=f"https://www.cqc.org.uk/location/{x.get('locationId')}",
                phones=([make_phone("GB", x.get("mainPhoneNumber") or "")]
                        if x.get("mainPhoneNumber") else []),
                addresses=[make_address(
                    address=", ".join(filter(None, [
                        x.get("postalAddressLine1"),
                        x.get("postalAddressLine2"),
                        x.get("postalAddressTownCity"),
                    ])),
                    city=x.get("postalAddressTownCity") or "",
                    postal_code=postal,
                    department=county,
                    region=region,
                    lat=x.get("onspdLatitude"),
                    lng=x.get("onspdLongitude"),
                )],
            ))
            polite_sleep(0.2, 0.5)
        polite_sleep()
    return out


def scrape_doctify_playwright(specialty: str) -> list[dict]:
    """Best-effort Playwright path against doctify.com.

    Doctify uses Cloudflare. Sometimes lets headless browsers through,
    sometimes serves a challenge. Run from a residential IP for any chance
    of success. Selectors are tuned to Dec-2024; check after any redesign.
    """
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup
    import re
    from urllib.parse import urljoin

    BASE = "https://www.doctify.com"
    url = f"{BASE}/uk/search?treatment={specialty}"
    out: list[dict] = []
    seen: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="en-GB")
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            log(f"doctify nav failed: {e}")
            browser.close()
            return out

        body = page.content().lower()
        if "cloudflare" in body or "checking your browser" in body:
            log("doctify served Cloudflare challenge; aborting.")
            browser.close()
            return out

        try:
            page.wait_for_selector("a[href*='/uk/specialist/']", timeout=15000)
        except Exception:
            log("doctify: no specialist cards rendered.")
            browser.close()
            return out

        for _ in range(15):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(500)

        soup = BeautifulSoup(page.content(), "lxml")
        for a in soup.select("a[href*='/uk/specialist/']"):
            href = urljoin(BASE, a["href"])
            if href in seen:
                continue
            seen.add(href)
            card = a
            for _ in range(5):
                card = card.parent
                if not card or "card" in " ".join(card.get("class") or []):
                    break
            name_el = card.select_one("h2, h3, [class*='name']")
            name = name_el.get_text(" ", strip=True) if name_el else ""
            if not name:
                continue
            txt = card.get_text("\n", strip=True)
            postal = ""
            m = re.search(r"\b([A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2})\b", txt)
            if m:
                postal = m.group(1)
            out.append(make_record(
                country="GB",
                name=name,
                specialty=specialty.capitalize(),
                profile_url=href,
                addresses=[make_address(postal_code=postal)] if postal else [],
            ))
        browser.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["cqc", "doctify"], default="cqc")
    ap.add_argument("--keyword", default="dermatology",
                    help="search keyword (e.g. dermatology, aesthetic, urology)")
    ap.add_argument("--max-pages", type=int, default=100)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    if args.source == "cqc":
        records = scrape_cqc(args.keyword, max_pages=args.max_pages)
    else:
        records = scrape_doctify_playwright(args.keyword)

    out = args.out or (DATA_DIR / f"gb-{args.keyword}-{args.source}.json")
    write_jsonl(out, records)
    log(f"wrote {len(records)} records -> {out}")


if __name__ == "__main__":
    main()
