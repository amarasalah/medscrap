"""Google Places API: search-for-new and enrich-existing modes.

Requires GOOGLE_PLACES_API_KEY (read from .env.local).

Commands
--------

  search  Run "<specialty> in <city>" Text Search across a set of seed
          cities, paginate up to 3 pages, fetch Place Details, save to JSON.

  enrich  Read an existing JSON file in the unified schema; for every record
          missing phone / lat / website, run FindPlace + Details and fill in.
          Modifies the file in place (writes a *.bak first).

Cost
----

Both Text Search and FindPlace are billed as the "Find Place" SKU
($32/1000 in May 2026). Place Details "Contact + Atmosphere" SKUs run
~$17–22/1000. Each completed record therefore costs ~$0.04–0.05. Use
`--max-calls` to cap a run.

Schema mapping
--------------

Google does NOT return email addresses. We populate name, phones,
addresses (with lat/lng + maps URL), profileUrl (= Place website),
and inferred department/region. Email enrichment lives in a separate
script (`enrich-emails.py`).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Iterable

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (
    DATA_DIR, ES_COMUNIDAD, FR_DEPT, FR_REGION, UK_COUNTY_REGION,
    fr_geo_from_postal, log, make_address, make_phone, make_record,
    make_session, polite_sleep, write_jsonl,
)

SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
FIND_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"


# --- Seed cities per country (chosen for coverage breadth) ---

UK_SEEDS = [
    ("London", "Greater London", "London"),
    ("Birmingham", "West Midlands", "West Midlands"),
    ("Manchester", "Greater Manchester", "North West"),
    ("Leeds", "West Yorkshire", "Yorkshire and the Humber"),
    ("Liverpool", "Merseyside", "North West"),
    ("Sheffield", "South Yorkshire", "Yorkshire and the Humber"),
    ("Bristol", "Bristol", "South West"),
    ("Newcastle upon Tyne", "Tyne and Wear", "North East"),
    ("Nottingham", "Nottinghamshire", "East Midlands"),
    ("Cardiff", "Wales", "Wales"),
    ("Edinburgh", "Scotland", "Scotland"),
    ("Glasgow", "Scotland", "Scotland"),
    ("Belfast", "Northern Ireland", "Northern Ireland"),
    ("Brighton", "East Sussex", "South East"),
    ("Southampton", "Hampshire", "South East"),
    ("Oxford", "Oxfordshire", "South East"),
    ("Cambridge", "Cambridgeshire", "East of England"),
    ("Reading", "Berkshire", "South East"),
    ("Coventry", "West Midlands", "West Midlands"),
    ("Leicester", "Leicestershire", "East Midlands"),
    ("Plymouth", "Devon", "South West"),
    ("York", "North Yorkshire", "Yorkshire and the Humber"),
    ("Aberdeen", "Scotland", "Scotland"),
    ("Norwich", "Norfolk", "East of England"),
    ("Portsmouth", "Hampshire", "South East"),
    ("Hull", "East Riding of Yorkshire", "Yorkshire and the Humber"),
    ("Stoke-on-Trent", "Staffordshire", "West Midlands"),
    ("Wolverhampton", "West Midlands", "West Midlands"),
    ("Derby", "Derbyshire", "East Midlands"),
    ("Swansea", "Wales", "Wales"),
]

ES_SEEDS = [
    ("Madrid", "Madrid", "Comunidad de Madrid"),
    ("Barcelona", "Barcelona", "Cataluña"),
    ("Valencia", "Valencia", "Comunidad Valenciana"),
    ("Sevilla", "Sevilla", "Andalucía"),
    ("Zaragoza", "Zaragoza", "Aragón"),
    ("Málaga", "Málaga", "Andalucía"),
    ("Murcia", "Murcia", "Región de Murcia"),
    ("Palma", "Illes Balears", "Islas Baleares"),
    ("Las Palmas de Gran Canaria", "Las Palmas", "Canarias"),
    ("Bilbao", "Bizkaia", "País Vasco"),
    ("Alicante", "Alicante", "Comunidad Valenciana"),
    ("Córdoba", "Córdoba", "Andalucía"),
    ("Valladolid", "Valladolid", "Castilla y León"),
    ("Vigo", "Pontevedra", "Galicia"),
    ("Gijón", "Asturias", "Asturias"),
    ("Granada", "Granada", "Andalucía"),
    ("A Coruña", "La Coruña", "Galicia"),
    ("Vitoria-Gasteiz", "Álava", "País Vasco"),
    ("Santa Cruz de Tenerife", "Santa Cruz de Tenerife", "Canarias"),
    ("Pamplona", "Navarra", "Navarra"),
    ("Almería", "Almería", "Andalucía"),
    ("San Sebastián", "Gipuzkoa", "País Vasco"),
    ("Santander", "Cantabria", "Cantabria"),
    ("Toledo", "Toledo", "Castilla-La Mancha"),
    ("Burgos", "Burgos", "Castilla y León"),
    ("Salamanca", "Salamanca", "Castilla y León"),
    ("Logroño", "La Rioja", "La Rioja"),
    ("Cádiz", "Cádiz", "Andalucía"),
    ("Huelva", "Huelva", "Andalucía"),
    ("Tarragona", "Tarragona", "Cataluña"),
    ("Lleida", "Lleida", "Cataluña"),
    ("Girona", "Girona", "Cataluña"),
    ("Castellón", "Castellón", "Comunidad Valenciana"),
    ("Albacete", "Albacete", "Castilla-La Mancha"),
    ("León", "León", "Castilla y León"),
    ("Cáceres", "Cáceres", "Extremadura"),
    ("Badajoz", "Badajoz", "Extremadura"),
    ("Oviedo", "Asturias", "Asturias"),
    ("Jaén", "Jaén", "Andalucía"),
    ("Mérida", "Badajoz", "Extremadura"),
]

FR_SEEDS = [
    ("Paris", "Paris", "Île-de-France"),
    ("Marseille", "Bouches-du-Rhône", "Provence-Alpes-Côte d'Azur"),
    ("Lyon", "Rhône", "Auvergne-Rhône-Alpes"),
    ("Toulouse", "Haute-Garonne", "Occitanie"),
    ("Nice", "Alpes-Maritimes", "Provence-Alpes-Côte d'Azur"),
    ("Nantes", "Loire-Atlantique", "Pays de la Loire"),
    ("Strasbourg", "Bas-Rhin", "Grand Est"),
    ("Montpellier", "Hérault", "Occitanie"),
    ("Bordeaux", "Gironde", "Nouvelle-Aquitaine"),
    ("Lille", "Nord", "Hauts-de-France"),
    ("Rennes", "Ille-et-Vilaine", "Bretagne"),
    ("Reims", "Marne", "Grand Est"),
    ("Saint-Étienne", "Loire", "Auvergne-Rhône-Alpes"),
    ("Le Havre", "Seine-Maritime", "Normandie"),
    ("Toulon", "Var", "Provence-Alpes-Côte d'Azur"),
    ("Grenoble", "Isère", "Auvergne-Rhône-Alpes"),
    ("Dijon", "Côte-d'Or", "Bourgogne-Franche-Comté"),
    ("Angers", "Maine-et-Loire", "Pays de la Loire"),
    ("Nîmes", "Gard", "Occitanie"),
    ("Villeurbanne", "Rhône", "Auvergne-Rhône-Alpes"),
    ("Saint-Denis", "La Réunion", "Outre-mer"),
    ("Le Mans", "Sarthe", "Pays de la Loire"),
    ("Aix-en-Provence", "Bouches-du-Rhône", "Provence-Alpes-Côte d'Azur"),
    ("Brest", "Finistère", "Bretagne"),
    ("Tours", "Indre-et-Loire", "Centre-Val de Loire"),
    ("Amiens", "Somme", "Hauts-de-France"),
    ("Limoges", "Haute-Vienne", "Nouvelle-Aquitaine"),
    ("Clermont-Ferrand", "Puy-de-Dôme", "Auvergne-Rhône-Alpes"),
    ("Besançon", "Doubs", "Bourgogne-Franche-Comté"),
    ("Metz", "Moselle", "Grand Est"),
]

# Arrondissements — added separately so we can target them with --cities
# without re-billing the already-covered base FR_SEEDS list.
FR_PARIS_ARDTS = [
    (f"Paris {n}{'er' if n == 1 else 'e'}", "Paris", "Île-de-France")
    for n in range(1, 21)
]
FR_LYON_ARDTS = [
    (f"Lyon {n}{'er' if n == 1 else 'e'}", "Rhône", "Auvergne-Rhône-Alpes")
    for n in range(1, 10)
]
FR_MARSEILLE_ARDTS = [
    (f"Marseille {n}{'er' if n == 1 else 'e'}", "Bouches-du-Rhône",
     "Provence-Alpes-Côte d'Azur")
    for n in range(1, 17)
]
FR_SEEDS = FR_SEEDS + FR_PARIS_ARDTS + FR_LYON_ARDTS + FR_MARSEILLE_ARDTS


# --- Specialty query templates ---

QUERIES = {
    "uk-aesthetic": (
        "GB",
        ["aesthetic clinic", "cosmetic dermatology clinic", "medical aesthetic"],
        "Aesthetic medicine",
    ),
    "uk-dermatology": (
        "GB",
        ["dermatologist", "dermatology clinic"],
        "Dermatology",
    ),
    "uk-urology": (
        "GB",
        ["urologist", "urology clinic"],
        "Urology",
    ),
    "es-gynecology": (
        "ES",
        ["ginecologo", "clinica ginecologica"],
        "Ginecología",
    ),
    "fr-andrology": (
        "FR",
        ["andrologue", "andrologie"],
        "Andrologue",
    ),
    "fr-gynecology": (
        "FR",
        ["gynécologue", "clinique gynécologique", "cabinet gynécologie"],
        "Gynécologue",
    ),
    "fr-urology": (
        "FR",
        ["urologue", "clinique urologique", "cabinet urologie"],
        "Urologue",
    ),
    "fr-dermatology": (
        "FR",
        ["dermatologue", "clinique dermatologique", "cabinet dermatologie"],
        "Dermatologue",
    ),
    "fr-aesthetic": (
        "FR",
        ["médecine esthétique", "clinique esthétique", "médecin esthétique"],
        "Médecine esthétique",
    ),
}


# --- API call wrappers with call counter ---

class Budget:
    def __init__(self, max_calls: int):
        self.max = max_calls
        self.used = 0

    def can_spend(self) -> bool:
        return self.used < self.max

    def hit(self) -> None:
        self.used += 1


def text_search(session, api_key, query, region, budget, pagetoken=None) -> dict | None:
    if not budget.can_spend():
        return None
    params = {"query": query, "key": api_key}
    if region:
        params["region"] = region.lower()
    if pagetoken:
        params["pagetoken"] = pagetoken
    try:
        r = session.get(SEARCH_URL, params=params, timeout=30)
    except requests.RequestException as e:
        log(f"text_search error: {e}")
        return None
    budget.hit()
    if r.status_code != 200:
        log(f"text_search HTTP {r.status_code}: {r.text[:200]}")
        return None
    return r.json()


def place_details(session, api_key, place_id, budget) -> dict | None:
    if not budget.can_spend():
        return None
    params = {
        "place_id": place_id,
        "fields": ("name,formatted_address,formatted_phone_number,"
                   "international_phone_number,website,geometry,address_component,"
                   "url,business_status,types"),
        "key": api_key,
    }
    try:
        r = session.get(DETAILS_URL, params=params, timeout=30)
    except requests.RequestException as e:
        log(f"place_details error: {e}")
        return None
    budget.hit()
    if r.status_code != 200:
        return None
    return (r.json().get("result") or {}) or None


def find_place(session, api_key, text, budget) -> str | None:
    if not budget.can_spend():
        return None
    params = {
        "input": text, "inputtype": "textquery",
        "fields": "place_id", "key": api_key,
    }
    try:
        r = session.get(FIND_URL, params=params, timeout=30)
    except requests.RequestException as e:
        log(f"find_place error: {e}")
        return None
    budget.hit()
    if r.status_code != 200:
        return None
    cands = (r.json().get("candidates") or [])
    return cands[0]["place_id"] if cands else None


# --- Result → record conversion ---

def details_to_record(country: str, specialty_label: str,
                      details: dict, seed_dept: str = "", seed_region: str = "") -> dict:
    name = details.get("name") or ""
    addr = details.get("formatted_address") or ""
    phone = details.get("formatted_phone_number") or details.get(
        "international_phone_number") or ""
    website = details.get("website") or ""
    maps_url = details.get("url") or ""
    geo = (details.get("geometry") or {}).get("location") or {}
    lat = geo.get("lat")
    lng = geo.get("lng")

    # Parse address components
    postal = ""; city = ""; dept = seed_dept; region = seed_region
    for comp in details.get("address_components", []):
        types = comp.get("types") or []
        if "postal_code" in types:
            postal = comp.get("long_name") or postal
        elif "locality" in types or "postal_town" in types:
            city = comp.get("long_name") or city
        elif "administrative_area_level_2" in types and not dept:
            dept = comp.get("long_name")
        elif "administrative_area_level_1" in types and not region:
            region = comp.get("long_name")

    if country == "FR" and postal:
        d, r = fr_geo_from_postal(postal)
        dept = d or dept
        region = r or region
    elif country == "GB":
        region = UK_COUNTY_REGION.get(dept, region) or region
    elif country == "ES":
        region = ES_COMUNIDAD.get(dept, region) or region

    types = set(details.get("types") or [])
    type_ = ("health_institution"
             if (types & {"hospital", "health"}) and "doctor" not in types
             else "professionnel_de_sante")

    return make_record(
        country=country,
        type_=type_,
        name=name,
        specialty=specialty_label,
        profile_url=website or maps_url,
        website=website,
        phones=[make_phone(country, phone)] if phone else [],
        addresses=[make_address(
            address=addr, city=city, postal_code=postal,
            department=dept, region=region,
            lat=lat, lng=lng, maps_url=maps_url,
        )] if addr else [],
    )


# --- Cross-run place_id cache (saves Place Details $$ on already-known places) ---

CACHE_PATH = DATA_DIR / ".places-cache.json"


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False),
                          encoding="utf-8")


def load_seeds_file(path: Path, min_pop: int, top_n: int) -> list[tuple]:
    """Load a JSON seed file (list of {city, department, region, population})
    and return (city, dept, region) tuples, filtered/sorted."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = [r for r in raw if (r.get("population") or 0) >= min_pop]
    items.sort(key=lambda r: -(r.get("population") or 0))
    if top_n:
        items = items[:top_n]
    return [(r["city"], r.get("department", ""), r.get("region", ""))
            for r in items]


# --- search subcommand ---

def cmd_search(args, api_key: str):
    if args.query not in QUERIES:
        sys.exit(f"unknown query: {args.query}. Options: {list(QUERIES)}")
    country, queries, label = QUERIES[args.query]

    if args.seeds_file:
        seeds = load_seeds_file(args.seeds_file, args.min_pop, args.top_n)
        log(f"--seeds-file: {len(seeds)} seeds (min-pop={args.min_pop}, "
            f"top-n={args.top_n or 'all'})")
    else:
        seeds = {"FR": FR_SEEDS, "GB": UK_SEEDS, "ES": ES_SEEDS}[country]

    if args.cities:
        wanted = [c.strip().lower() for c in args.cities.split(",") if c.strip()]
        seeds = [s for s in seeds if any(w in s[0].lower() for w in wanted)]
        log(f"--cities filter: {len(seeds)} seeds match {wanted}")
        if not seeds:
            sys.exit("no seeds match --cities filter")

    cache = load_cache()
    log(f"place_id cache: {len(cache)} known ids")

    session = make_session()
    session.headers["Accept"] = "application/json"
    budget = Budget(args.max_calls)
    out: list[dict] = []
    seen: set[str] = set()
    skipped_cached = 0
    topic = args.query.split('-', 1)[1]
    suffix = f"-{args.out_suffix}" if args.out_suffix else ""
    out_path = DATA_DIR / f"{country.lower()}-places-{topic}{suffix}.json"

    try:
        for city, dept, region in seeds:
            if not budget.can_spend():
                log(f"budget exhausted at {budget.used}/{budget.max}, stopping")
                break
            for q in queries:
                full_q = f"{q} in {city}, {country}"
                log(f"search: {full_q}")
                data = text_search(session, api_key, full_q, country, budget)
                results = (data or {}).get("results") or []
                log(f"  page 1: {len(results)} results")

                # Pagination — Google requires a small delay before the next_page_token is valid
                pages = [results]
                tok = (data or {}).get("next_page_token")
                page_n = 1
                while tok and page_n < 3 and budget.can_spend():
                    time.sleep(2)
                    data2 = text_search(session, api_key, full_q, country, budget,
                                        pagetoken=tok)
                    if not data2:
                        break
                    rs = data2.get("results") or []
                    log(f"  page {page_n + 1}: {len(rs)} results")
                    pages.append(rs)
                    tok = data2.get("next_page_token")
                    page_n += 1

                for results in pages:
                    for r in results:
                        pid = r.get("place_id")
                        if not pid or pid in seen:
                            continue
                        seen.add(pid)
                        if pid in cache:
                            skipped_cached += 1
                            continue
                        det = place_details(session, api_key, pid, budget)
                        if not det:
                            continue
                        rec = details_to_record(country, label, det, dept, region)
                        if rec["name"]:
                            out.append(rec)
                            cache[pid] = {"name": rec["name"],
                                          "country": country,
                                          "topic": topic}
                        polite_sleep(0.1, 0.3)
                        if not budget.can_spend():
                            break
                    if not budget.can_spend():
                        break
    finally:
        save_cache(cache)

    write_jsonl(out_path, out)
    log(f"wrote {len(out)} new records to {out_path}; "
        f"skipped {skipped_cached} already-cached place_ids; "
        f"used {budget.used}/{budget.max} calls")


# --- enrich subcommand ---

def cmd_enrich(args, api_key: str):
    in_path = args.input
    records = json.loads(in_path.read_text(encoding="utf-8"))
    session = make_session()
    session.headers["Accept"] = "application/json"
    budget = Budget(args.max_calls)
    fixed = 0

    for i, rec in enumerate(records):
        if not budget.can_spend():
            log(f"budget exhausted at {budget.used}/{budget.max}, stopping")
            break

        addr0 = (rec.get("addresses") or [{}])[0]
        has_phone = bool(rec.get("phones"))
        has_geo = addr0 and (addr0.get("lat") is not None
                              and addr0.get("lng") is not None)
        has_site = bool(rec.get("profileUrl"))
        has_website = bool(rec.get("website"))
        if has_phone and has_geo and has_site and has_website:
            continue

        # Build a high-precision query: name + address + city + country
        country = rec.get("country") or ""
        parts = [rec.get("name", ""),
                 addr0.get("address", "") or addr0.get("city", ""),
                 country]
        query = " ".join(p for p in parts if p)
        pid = find_place(session, api_key, query, budget)
        if not pid:
            continue
        det = place_details(session, api_key, pid, budget)
        if not det:
            continue

        new_phone = det.get("formatted_phone_number") or det.get(
            "international_phone_number")
        if new_phone and not has_phone:
            rec["phones"] = [make_phone(country, new_phone)]
            fixed += 1
        geo = (det.get("geometry") or {}).get("location") or {}
        if geo and addr0 and not has_geo:
            addr0["lat"] = geo.get("lat")
            addr0["lng"] = geo.get("lng")
            addr0["mapsUrl"] = det.get("url") or addr0.get("mapsUrl") or ""
        # Always store the Places-known website separately so the email
        # enricher can use it even when profileUrl already points at the
        # directory (sante.fr / cqc / etc).
        if det.get("website"):
            rec["website"] = det["website"]
            if not has_site:
                rec["profileUrl"] = det["website"]

        if (i + 1) % 50 == 0:
            log(f"enrich: {i + 1}/{len(records)} (fixed {fixed}, calls {budget.used})")
        polite_sleep(0.1, 0.25)

    # Backup + write
    bak = in_path.with_suffix(in_path.suffix + ".bak")
    if not bak.exists():
        bak.write_text(json.dumps(records, ensure_ascii=False),
                       encoding="utf-8")
    in_path.write_text(json.dumps(records, ensure_ascii=False),
                       encoding="utf-8")
    log(f"enrich done; fixed {fixed} records, used {budget.used}/{budget.max} calls")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["search", "enrich"])
    ap.add_argument("--query", help="(search) query key, e.g. uk-aesthetic")
    ap.add_argument("--input", type=Path,
                    help="(enrich) path to a doctors.json-shaped file")
    ap.add_argument("--max-calls", type=int, default=2000,
                    help="hard cap on total API calls this run")
    ap.add_argument("--cities", default="",
                    help="(search) comma-separated case-insensitive substrings; "
                    "only seeds whose city name contains one of these run. "
                    "Example: --cities 'Paris 1er,Paris 2e'")
    ap.add_argument("--out-suffix", default="",
                    help="(search) appended to the output filename, e.g. "
                    "--out-suffix arrdt writes fr-places-urology-arrdt.json")
    ap.add_argument("--seeds-file", type=Path, default=None,
                    help="(search) JSON list of {city,department,region,population}; "
                    "overrides built-in FR_SEEDS/UK_SEEDS/ES_SEEDS.")
    ap.add_argument("--min-pop", type=int, default=0,
                    help="(search) only seed entries with population >= this.")
    ap.add_argument("--top-n", type=int, default=0,
                    help="(search) after sorting by population desc, keep only top N.")
    args = ap.parse_args()

    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        sys.exit("GOOGLE_PLACES_API_KEY not set (check .env.local).")

    if args.mode == "search":
        if not args.query:
            sys.exit("--query required for search mode. Options: "
                     f"{list(QUERIES)}")
        cmd_search(args, api_key)
    else:
        if not args.input:
            sys.exit("--input required for enrich mode.")
        cmd_enrich(args, api_key)


if __name__ == "__main__":
    main()
