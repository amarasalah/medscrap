"""Scrape Spanish gynecologists from doctoralia.es via Playwright.

Run:
    pip install -r scripts/requirements.txt
    playwright install chromium
    python scripts/scrape-spain.py --province madrid --max-pages 5

Why Playwright
--------------

Doctoralia is a Next.js / React SPA. HTTP-only requests return the page
shell with zero doctor cards. We must render the page in a real browser.

If Doctoralia starts serving a CAPTCHA when run from a datacenter IP, the
function logs and exits cleanly so you can re-run from a residential IP.

Selectors are tuned to the December-2024 DOM and may break — when they do,
run scripts/_recon_doctoralia.py (you'll need to write it; same template as
the France recon) to dump the rendered DOM and re-tune.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (
    DATA_DIR, ES_COMUNIDAD, log, make_address, make_phone, make_record,
    write_jsonl,
)

BASE = "https://www.doctoralia.es"

PROVINCIAS = [
    ("madrid", "Madrid"),
    ("barcelona", "Barcelona"),
    ("valencia", "Valencia"),
    ("sevilla", "Sevilla"),
    ("zaragoza", "Zaragoza"),
    ("malaga", "Málaga"),
    ("murcia", "Murcia"),
    ("palma-de-mallorca", "Illes Balears"),
    ("las-palmas-de-gran-canaria", "Las Palmas"),
    ("bilbao", "Bizkaia"),
    ("alicante", "Alicante"),
    ("cordoba", "Córdoba"),
    ("valladolid", "Valladolid"),
    ("vigo", "Pontevedra"),
    ("gijon", "Asturias"),
    ("granada", "Granada"),
    ("a-coruna", "La Coruña"),
    ("vitoria-gasteiz", "Álava"),
    ("santa-cruz-de-tenerife", "Santa Cruz de Tenerife"),
    ("pamplona", "Navarra"),
]


def scrape_doctoralia(provinces: list[tuple[str, str]],
                      max_pages_per_province: int = 30) -> list[dict]:
    from playwright.sync_api import sync_playwright

    out: list[dict] = []
    seen: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            locale="es-ES",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
        )
        page = ctx.new_page()

        for slug, provincia in provinces:
            for n in range(1, max_pages_per_province + 1):
                url = f"{BASE}/ginecologo/{slug}?page={n}"
                log(f"doctoralia {provincia} page {n} -> {url}")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    log(f"  navigation failed: {e}")
                    break

                body = page.content().lower()
                if "captcha" in body or "are you a robot" in body or "verify you are" in body:
                    log("  CAPTCHA wall hit. Stopping this province.")
                    break

                try:
                    page.wait_for_selector("[data-test='search-doctor-result'], "
                                            ".search-results-list .doctor, "
                                            "a[href*='/medico/']",
                                            timeout=12000)
                except Exception:
                    log("  no cards rendered (selector miss or end of pages).")
                    break

                page.wait_for_timeout(800)
                html = page.content()
                new_on_page = parse_doctoralia(html, provincia, out, seen)
                log(f"  parsed {new_on_page} new (total {len(out)})")
                if new_on_page == 0:
                    break
        browser.close()
    return out


def parse_doctoralia(html: str, provincia: str, out: list[dict], seen: set[str]) -> int:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    # Doctoralia ships results inside various containers depending on layout;
    # we use the profile link as the anchor.
    profile_links = soup.select("a[href*='/medico/']")
    cards: dict[str, BeautifulSoup] = {}
    for a in profile_links:
        href = a.get("href", "")
        if "/medico/" not in href:
            continue
        # walk up to the nearest "card-ish" parent
        parent = a
        for _ in range(6):
            parent = parent.parent
            if not parent:
                break
            classes = " ".join(parent.get("class") or [])
            if "result" in classes or "doctor" in classes or "card" in classes:
                cards[href] = parent
                break
        cards.setdefault(href, a.parent)

    added = 0
    for href, card in cards.items():
        full_url = urljoin(BASE, href)
        if full_url in seen:
            continue
        seen.add(full_url)

        name_el = card.select_one("h3, h2, [class*='name']")
        if not name_el:
            continue
        name = name_el.get_text(" ", strip=True)
        if not name:
            continue

        body = card.get_text("\n", strip=True)

        postal = ""
        pm = re.search(r"\b(\d{5})\b", body)
        if pm:
            postal = pm.group(1)

        addr_match = re.search(r"([^\n]+?\d{5}\s+[^\n,]+)", body)
        address = addr_match.group(1).strip() if addr_match else ""
        city = ""
        if address:
            cm = re.search(r"\b\d{5}\s+([^,\n]+)", address)
            if cm:
                city = cm.group(1).strip()

        phone_raw = ""
        tel = card.select_one("a[href^='tel:']")
        if tel:
            phone_raw = tel.get("href", "")[4:]

        comunidad = ES_COMUNIDAD.get(provincia, "")
        out.append(make_record(
            country="ES",
            name=name,
            specialty="Ginecología",
            profile_url=full_url,
            phones=[make_phone("ES", phone_raw)] if phone_raw else [],
            addresses=[make_address(
                address=address, city=city, postal_code=postal,
                department=provincia, region=comunidad,
            )] if address else [make_address(department=provincia, region=comunidad)],
        ))
        added += 1
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--province", help="single province slug; default: all")
    ap.add_argument("--max-pages", type=int, default=30)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    provs = PROVINCIAS
    if args.province:
        provs = [p for p in PROVINCIAS if p[0] == args.province]
        if not provs:
            ap.error(f"unknown province slug; choose from {[p[0] for p in PROVINCIAS]}")

    records = scrape_doctoralia(provs, max_pages_per_province=args.max_pages)
    out = args.out or (DATA_DIR / f"es-gyno-doctoralia"
                       f"{'-' + args.province if args.province else ''}.json")
    write_jsonl(out, records)
    log(f"wrote {len(records)} records -> {out}")


if __name__ == "__main__":
    main()
