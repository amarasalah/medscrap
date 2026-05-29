#!/usr/bin/env python3
"""
Deep scraping for advanced urology keywords.
Scrapes main page + key subpages like /services, /traitements, /urologie
"""

import json
import re
import time
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
from threading import Lock

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
PUBLIC_DIR = ROOT / "public"
OUTPUT_FILE = DATA_DIR / "fr-urology-advanced.json"

# Advanced urology keywords to search for
TARGET_KEYWORDS = [
    # User-specified
    ("PRP urologie", "PRP"),
    ("PRP erectile", "PRP-ED"),
    ("shockwave therapy", "Shockwave"),
    ("onde de choc", "Ondes de choc"),
    ("ondes de choc", "Ondes de choc"),
    ("pénoplastie", "Pénoplastie"),
    ("penoplastie", "Pénoplastie"),
    ("peno plastie", "Pénoplastie"),
    ("phalloplastie", "Phalloplastie"),
    ("allongement penien", "Allongement"),
    ("allongement pénien", "Allongement"),
    ("élargissement penien", "Élargissement"),
    ("élargissement pénien", "Élargissement"),
    ("augmentation penienne", "Augmentation"),
    ("augmentation pénienne", "Augmentation"),
    ("injections péniennes", "Injections"),
    ("injection penienne", "Injections"),
    ("stem cells", "Cellules souches"),
    ("cellules souches", "Cellules souches"),
    ("regenerative urology", "Régénérative"),
    ("urologie régénérative", "Régénérative"),
    ("incontinence urinaire", "Incontinence"),
    ("injection", "Injection"),
    ("la peyronie", "Peyronie"),
    ("maladie de la peyronie", "Peyronie"),
    ("lapeyronie", "Peyronie"),
    ("acide hyaluronique", "Acide hyaluronique"),
    ("botox", "Botox"),
    ("bocox", "Botox"),
    ("malformation verge", "Malformation"),
    ("implant penien", "Implant pénien"),
    ("implant pénien", "Implant pénien"),
    ("prothese penienne", "Prothèse"),
    ("prothèse pénienne", "Prothèse"),
    ("implant erectile", "Implant érectile"),
    ("curbure penienne", "Courbure"),
    ("courbure pénienne", "Courbure"),
    ("dysfonction erectile", "DE"),
    ("dysfonction érectile", "DE"),
    ("impuissance", "Impuissance"),
    ("troubles erection", "Troubles érection"),
    ("troubles érection", "Troubles érection"),
    ("ejaculation precoce", "EP"),
    ("éjaculation précoce", "EP"),
    ("infertilite masculine", "Infertilité"),
    ("infertilité masculine", "Infertilité"),
    ("vasectomie", "Vasectomie"),
    ("andrologie", "Andrologie"),
    ("andrologue", "Andrologue"),
    ("sexologie", "Sexologie"),
    ("medecine sexuelle", "Médecine sexuelle"),
    ("médecine sexuelle", "Médecine sexuelle"),
]

# Pages to check on each website
SUBPATHS = [
    "/", "",  # homepage
    "/services", "/services-urologie", "/services-urologiques",
    "/traitements", "/traitement",
    "/specialites", "/specialites-urologiques", "/specialite",
    "/urologie", "/urologue",
    "/andrologie", "/andrologue",
    "/chirurgie", "/chirurgies",
    "/pathologies", "/pathologie",
    "/penoplastie", "/penis", "/penien",
    "/implants", "/implant",
    "/erection", "/troubles-erectiles",
    "/peyronie", "/maladie-peyronie",
    "/incontinence",
    "/vasectomie",
    "/contact", "/mentions-legales",
]

def load_json(path: Path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def normalize_url(url: str) -> str:
    """Normalize URL for scraping"""
    if not url.startswith("http"):
        url = "https://" + url
    # Remove trailing slash for consistency
    return url.rstrip("/")

def extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML"""
    # Remove scripts and styles
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags but keep content
    html = re.sub(r'<[^>]+>', ' ', html)
    # Normalize whitespace
    html = re.sub(r'\s+', ' ', html)
    return html.strip()

def scrape_page(session: requests.Session, url: str) -> tuple[str, bool]:
    """Scrape a single page, return (text, success)"""
    try:
        r = session.get(url, timeout=(2, 8), allow_redirects=True)
        if r.status_code == 200:
            text = extract_text_from_html(r.text)
            return text, True
        return "", False
    except Exception:
        return "", False

def find_keywords_in_text(text: str) -> list[tuple[str, str]]:
    """Find all matching keywords in text, return list of (keyword, category)"""
    text_lower = text.lower()
    matches = []
    for keyword, category in TARGET_KEYWORDS:
        if keyword.lower() in text_lower:
            matches.append((keyword, category))
    return matches

def deep_scrape_website(session: requests.Session, base_url: str) -> tuple[list[tuple[str, str]], dict]:
    """
    Deep scrape a website looking for keywords.
    Returns (matches, info_dict)
    """
    all_matches = []
    pages_scraped = []
    
    base_url = normalize_url(base_url)
    parsed = urlparse(base_url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"
    
    for subpath in SUBPATHS[:6]:  # Limit to first 6 paths for speed
        url = urljoin(base_domain, subpath)
        text, success = scrape_page(session, url)
        if success and text:
            pages_scraped.append(subpath or "/")
            matches = find_keywords_in_text(text)
            all_matches.extend(matches)
        
        # Stop early if we found good matches
        if len(set(m[1] for m in all_matches)) >= 3:
            break
    
    # Remove duplicates while preserving order
    seen = set()
    unique_matches = []
    for m in all_matches:
        if m[0] not in seen:
            seen.add(m[0])
            unique_matches.append(m)
    
    return unique_matches, {"pages": pages_scraped}

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    adapter = requests.adapters.HTTPAdapter(max_retries=0)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    return s

def process_record(record: dict, session: requests.Session) -> dict | None:
    """Process a single record, return enriched result if it has matches"""
    website = record.get("website", "")
    if not website:
        # Check if record already matches by specialty alone
        specialty = record.get("specialty", "").lower()
        if "urolog" in specialty or "androlog" in specialty:
            return {
                "record": record,
                "matches": [("urologie", "Urologie")],
                "pages": [],
                "method": "specialty"
            }
        return None
    
    matches, info = deep_scrape_website(session, website)
    
    if matches:
        return {
            "record": record,
            "matches": matches,
            "pages": info["pages"],
            "method": "website"
        }
    
    return None

def main():
    # Load doctors data
    doctors = load_json(PUBLIC_DIR / "doctors.json")
    print(f"Loaded {len(doctors)} total doctors")
    
    # Filter to French candidates with websites
    candidates = [
        d for d in doctors 
        if d.get("country") == "FR" and (
            d.get("website") or 
            "urolog" in d.get("specialty", "").lower() or
            "androlog" in d.get("specialty", "").lower()
        )
    ]
    print(f"Found {len(candidates)} French urology candidates")
    
    # Process with thread pool
    session = make_session()
    matching_records = []
    processed_count = 0
    lock = Lock()
    
    print(f"\nDeep scraping {len(candidates)} websites with 15 workers...")
    
    def process_with_session(record):
        nonlocal processed_count
        try:
            result = process_record(record, session)
            with lock:
                processed_count += 1
                if processed_count % 100 == 0:
                    print(f"  Progress: {processed_count}/{len(candidates)}")
            return result
        except Exception as e:
            with lock:
                processed_count += 1
            return None
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_record = {executor.submit(process_with_session, c): c for c in candidates}
        
        for future in as_completed(future_to_record):
            result = future.result()
            if result:
                matching_records.append(result)
    
    # Prepare final output
    output = []
    for e in matching_records:
        rec = e["record"].copy()
        rec["matched_keywords"] = list(set(m[0] for m in e["matches"]))
        rec["keyword_categories"] = list(set(m[1] for m in e["matches"]))
        rec["scraped_pages"] = e.get("pages", [])
        rec["match_method"] = e.get("method", "unknown")
        output.append(rec)
    
    # Sort by number of unique categories (more specific = first)
    output.sort(key=lambda x: len(x.get("keyword_categories", [])), reverse=True)
    
    # Save results
    save_json(OUTPUT_FILE, output)
    
    print(f"\n{'='*60}")
    print(f"Found {len(output)} matching records")
    print(f"Saved to {OUTPUT_FILE}")
    
    # Print keyword distribution
    all_categories = []
    for e in matching_records:
        all_categories.extend([m[1] for m in e["matches"]])
    
    from collections import Counter
    cat_counts = Counter(all_categories)
    print(f"\nKeyword category distribution:")
    for cat, count in cat_counts.most_common(15):
        print(f"  {cat}: {count}")
    
    # Print top matches
    print(f"\n{'='*60}")
    print("Top matches (most keywords):")
    for e in matching_records[:10]:
        rec = e["record"]
        cats = set(m[1] for m in e["matches"])
        print(f"\n  {rec.get('name')} | {rec.get('specialty')}")
        print(f"    Categories: {list(cats)[:5]}")
        print(f"    Website: {rec.get('website', 'N/A')}")
        print(f"    Pages: {e.get('pages', [])}")

if __name__ == "__main__":
    main()
