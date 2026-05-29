#!/usr/bin/env python3
"""
Enrich doctor records with descriptions from:
1. Google Places API editorial_summary
2. Website meta descriptions

Then filter by urology-related keywords.
"""

import json
import re
import sys
import time
import requests
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from typing import Optional

# Paths
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
PUBLIC_DIR = ROOT / "public"
CACHE_FILE = DATA_DIR / ".desc-cache.json"
OUTPUT_FILE = DATA_DIR / "fr-urology-filtered.json"

# Google Places API
SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# Keywords to filter by (French urology focus)
KEYWORDS = [
    # French urology terms
    "urologue", "urologie", "urologiste",
    "andrologie", "andrologue",
    "dysfonction érectile", "erectile dysfunction",
    "impuissance", "troubles de l'érection",
    "ejaculation precoce", "premature ejaculation",
    "infertilite masculine", "male infertility",
    "vasectomie", "vasectomy",
    "adénome de la prostate", "prostate adenoma",
    "hypertrophie bénigne de la prostate", "HBP", "BPH",
    "cancer de la prostate", "prostate cancer",
    "lithiase rénale", "kidney stones",
    "infection urinaire", "urinary tract infection",
    "cystite", "cystitis",
    "prostatite", "prostatitis",
    "énurésie", "bedwetting",
    "incontinence urinaire", "urinary incontinence",
    "fuite urinaire", "urinary leakage",
    "dysurie", "dysuria",
    "pollakiurie", "frequent urination",
    "nicturie", "nocturia",
    "hématurie", "hematuria",
    "rétention urinaire", "urinary retention",
    "stricture urétrale", "urethral stricture",
    "sténose du col vésical",
    "reflux vésico-rénal", "vesicoureteral reflux",
    "micropénis", "micropenis",
    "phimosis", "phimosis",
    "paraphimosis", "paraphimosis",
    "balanite", "balanitis",
    "cancer du testicule", "testicular cancer",
    "cancer du rein", "kidney cancer",
    "tumeur de la vessie", "bladder tumor",
    "vessie hyperactive", "overactive bladder",
    "neuro-vessie", "neurogenic bladder",
    "sonde urinaire", "urinary catheter",
    "cystoscopie", "cystoscopy",
    "résection endoscopique de la prostate", "TURP",
    "laser prostate", "greenlight", "holmium",
    "prostatectomie", "prostatectomy",
    "nephrectomie", "nephrectomy",
    "cystectomie", "cystectomy",
    "ureteroscopie", "ureteroscopy",
    "lithotritie", "lithotripsy",
    "percutanée", "PCNL",
    "biopsie de la prostate", "prostate biopsy",
    "prise en charge globale", "comprehensive care",
    "chirurgie urologique", "urological surgery",
    "chirurgie mini-invasive", "minimally invasive surgery",
    "robotique", "robotic surgery",
    "laparoscopie", "laparoscopy",
    "endourologie", "endourology",
    "urologie fonctionnelle", "functional urology",
    "urologie oncologique", "oncological urology",
    "urologie reconstructrice", "reconstructive urology",
    "urologie pédiatrique", "pediatric urology",
    "urologie féminine", "female urology",
    "sexologie", "sexology",
    "médecine sexuelle", "sexual medicine",
    "traitement hormonal", "hormone therapy",
    "testosterone", "testosterone",
    "substitution hormonale", "hormone replacement",
    "prise en charge du cancer", "cancer care",
    "suivi post-cancer", "post-cancer follow-up",
    "rééducation périnéale", "perineal rehabilitation",
    "rééducation vésicale", "bladder rehabilitation",
    "électrostimulation", "electrical stimulation",
    "biofeedback", "biofeedback",
    "PFPT", "pelvic floor physical therapy",
    "santé masculine", "men's health",
    "dépistage prostate", "prostate screening",
    "PSA", "prostate specific antigen",
    "touché rectal", "digital rectal exam",
    "IRM prostate", "prostate MRI",
    "fusion biopsy", "fusion biopsy",
    "curiethérapie", "brachytherapy",
    "radiothérapie", "radiotherapy",
    "chimiothérapie", "chemotherapy",
    "immunothérapie", "immunotherapy",
    "hormonothérapie", "hormone therapy",
    "chirurgie conservatrice", "conservative surgery",
    "prostatectomie radicale", "radical prostatectomy",
    "nerve-sparing", "nerve-sparing",
    "réhabilitation sexuelle", "sexual rehabilitation",
    "prothèse pénienne", "penile prosthesis",
    "implant pénien", "penile implant",
    "pénoplastie", "penoplasty",
    "phalloplastie", "phalloplasty",
    "allongement", "lengthening",
    "élargissement", "enlargement",
    "curvature", "curvature",
    "maladie de laverne", "laverne disease",
    "la Peyronie", "peyronie",
    "priapisme", "priapism",
    "érection prolongée", "prolonged erection",
    "dysplasie", "dysplasia",
    "malformation", "malformation",
    "hypogonadisme", "hypogonadism",
    "gynécomastie", "gynecomastia",
    "varicocèle", "varicocele",
    "hydrocèle", "hydrocele",
    "spermatocele", "spermatocele",
    "cryptorchidie", "cryptorchidism",
    "anorchidie", "anorchidism",
    "ectopie testiculaire", "testicular ectopia",
    "torsion testiculaire", "testicular torsion",
    "traumatisme testiculaire", "testicular trauma",
    "epididymite", "epididymitis",
    "orchite", "orchitis",
    "stenose", "stenosis",
    "hypospadias", "hypospadias",
    "epispadias", "epispadias",
    "fistule", "fistula",
    "uréthroplastie", "urethroplasty",
    "meatotomie", "meatotomy",
    "meatoplastie", "meatoplasty",
    "circoncision", "circumcision",
    "posthectomie", "posthectomy",
    "frenectomie", "frenectomy",
    "plastie", "plasty",
    "reconstruction", "reconstruction",
    "réparation", "repair",
    # New keywords from user
    "PRP urologie", "PRP urology",
    "PRP erectile dysfunction",
    "shockwave therapy", "onde de choc",
    "pénoplastie", "penoplastie", "peno plastie",
    "injections péniennes", "penile injections",
    "stem cells urology", "cellules souches urologie",
    "regenerative urology", "urologie régénérative",
    "incontinance urinaire", "incontinence urinaire",
    "injection",
    "lapeyronie", "la peyronie",
    "l'acide hyaluronique", "acide hyaluronique",
    "BOTOX", "BOCOX",
    "MALFORMATION DE LA VERGE",
    "implant penien", "implant pénien",
]

# Compile regex for fast matching
KEYWORD_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k.lower()) for k in KEYWORDS) + r')\b',
    re.IGNORECASE
)

class MLStripper(HTMLParser):
    """Strip HTML tags"""
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    try:
        s.feed(html)
        return s.get_data()
    except:
        return html

def load_json(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_cid_from_url(url: str) -> Optional[str]:
    """Extract CID from Google Maps URL"""
    if not url or "cid=" not in url:
        return None
    match = re.search(r'cid=(\d+)', url)
    return match.group(1) if match else None

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"
    })
    return s

def fetch_place_details_by_cid(session: requests.Session, api_key: str, cid: str) -> Optional[dict]:
    """Fetch place details using CID via text search then details"""
    try:
        # First, find place_id using the CID
        search_url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {
            "input": f"place_id:{cid}",  # CID can sometimes work as input
            "inputtype": "textquery",
            "fields": "place_id",
            "key": api_key
        }
        r = session.get(search_url, params=params, timeout=10)
        data = r.json()
        
        if data.get("status") != "OK" or not data.get("candidates"):
            return None
            
        place_id = data["candidates"][0]["place_id"]
        
        # Now get details with editorial_summary
        details_params = {
            "place_id": place_id,
            "fields": "editorial_summary,types,formatted_address,name",
            "key": api_key
        }
        r2 = session.get(DETAILS_URL, params=details_params, timeout=10)
        data2 = r2.json()
        
        if data2.get("status") == "OK":
            return data2.get("result", {})
        return None
    except Exception as e:
        return None

def fetch_place_details_by_name_address(session: requests.Session, api_key: str, name: str, address: str) -> Optional[dict]:
    """Find place by name and address, then get details"""
    try:
        query = f"{name} {address}"
        params = {
            "query": query,
            "key": api_key
        }
        r = session.get(SEARCH_URL, params=params, timeout=10)
        data = r.json()
        
        if data.get("status") != "OK" or not data.get("results"):
            return None
            
        # Take first result
        place_id = data["results"][0]["place_id"]
        
        # Get details
        details_params = {
            "place_id": place_id,
            "fields": "editorial_summary,types,formatted_address,name",
            "key": api_key
        }
        r2 = session.get(DETAILS_URL, params=details_params, timeout=10)
        data2 = r2.json()
        
        if data2.get("status") == "OK":
            return data2.get("result", {})
        return None
    except Exception as e:
        return None

def scrape_website_description(session: requests.Session, url: str) -> Optional[str]:
    """Scrape meta description from website"""
    if not url or not url.startswith("http"):
        return None
    
    try:
        r = session.get(url, timeout=(3, 8), allow_redirects=True)
        if r.status_code != 200:
            return None
        
        html = r.text
        
        # Look for meta description
        patterns = [
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                desc = match.group(1).strip()
                if len(desc) > 20:
                    return strip_tags(desc)
        
        # Fallback: try to get first paragraph
        para_match = re.search(r'<p[^>]*>([^<]{50,500})</p>', html, re.IGNORECASE)
        if para_match:
            return strip_tags(para_match.group(1))
            
        return None
    except Exception as e:
        return None

def matches_keywords(text: str) -> tuple[bool, list]:
    """Check if text matches any keywords, return matches found"""
    if not text:
        return False, []
    
    text_lower = text.lower()
    matches = []
    
    for keyword in KEYWORDS:
        if keyword.lower() in text_lower:
            matches.append(keyword)
    
    return len(matches) > 0, list(set(matches))

def enrich_record(session: requests.Session, api_key: str, record: dict, cache: dict) -> dict:
    """Enrich a single record with descriptions"""
    record_id = record.get("id", "unknown")
    
    # Check cache
    if record_id in cache:
        return cache[record_id]
    
    descriptions = []
    sources = []
    
    # Method 1: Places API editorial_summary
    profile_url = record.get("profileUrl", "")
    cid = extract_cid_from_url(profile_url)
    
    if cid and api_key:
        place_data = fetch_place_details_by_cid(session, api_key, cid)
        if place_data:
            editorial = place_data.get("editorial_summary", {})
            if editorial:
                desc = editorial.get("overview", "")
                if desc:
                    descriptions.append(desc)
                    sources.append("places_editorial")
    
    # Method 2: Website scraping
    website = record.get("website", "")
    if website:
        web_desc = scrape_website_description(session, website)
        if web_desc:
            descriptions.append(web_desc)
            sources.append("website_meta")
    
    # Combine descriptions
    combined_desc = " | ".join(descriptions) if descriptions else ""
    
    # Check keyword matches
    text_to_check = f"{record.get('name', '')} {record.get('specialty', '')} {record.get('subSpecialty', '')} {combined_desc}"
    has_match, matched_keywords = matches_keywords(text_to_check)
    
    result = {
        "record": record,
        "description": combined_desc,
        "sources": sources,
        "keyword_matches": matched_keywords,
        "matches": has_match
    }
    
    cache[record_id] = result
    return result

def main():
    # Load API key
    env_path = ROOT / ".env.local"
    api_key = None
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("GOOGLE_PLACES_API_KEY="):
                    api_key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                    break
    
    if not api_key:
        print("ERROR: GOOGLE_PLACES_API_KEY not found in .env.local")
        sys.exit(1)
    
    # Load doctors data
    doctors = load_json(PUBLIC_DIR / "doctors.json")
    print(f"Loaded {len(doctors)} doctors")
    
    # Load cache
    cache = load_json(CACHE_FILE) if CACHE_FILE.exists() else {}
    print(f"Cache has {len(cache)} entries")
    
    # Filter to French urologists first (optimization)
    fr_urologists = [
        d for d in doctors 
        if d.get("country") == "FR" and 
        ("urolog" in d.get("specialty", "").lower() or 
         "urolog" in d.get("subSpecialty", "").lower() or
         "androlog" in d.get("specialty", "").lower())
    ]
    print(f"Found {len(fr_urologists)} French urologists/andrologists")
    
    # Also include records with websites that might be urology-related
    # but weren't classified as urology
    candidates = fr_urologists
    
    # Enrich records
    session = make_session()
    enriched = []
    
    print("\nEnriching records...")
    for i, record in enumerate(candidates):
        if i % 50 == 0:
            print(f"  Progress: {i}/{len(candidates)}")
        
        result = enrich_record(session, api_key, record, cache)
        enriched.append(result)
        
        # Rate limiting
        time.sleep(0.1)
    
    # Save cache
    save_json(CACHE_FILE, cache)
    
    # Filter by keywords
    matching_records = [e for e in enriched if e["matches"]]
    print(f"\nFound {len(matching_records)} records matching keywords")
    
    # Prepare output
    output = []
    for e in matching_records:
        rec = e["record"].copy()
        rec["enriched_description"] = e["description"]
        rec["description_sources"] = e["sources"]
        rec["matched_keywords"] = e["keyword_matches"]
        output.append(rec)
    
    # Save results
    save_json(OUTPUT_FILE, output)
    print(f"\nSaved {len(output)} matching records to {OUTPUT_FILE}")
    
    # Print sample matches
    print("\n=== Sample Matches ===")
    for e in matching_records[:5]:
        rec = e["record"]
        print(f"\n{rec.get('name')}")
        print(f"  Specialty: {rec.get('specialty')}")
        print(f"  Keywords: {e['keyword_matches']}")
        print(f"  Desc sources: {e['sources']}")
        desc = e['description'][:150] + "..." if len(e['description']) > 150 else e['description']
        print(f"  Description: {desc}")

if __name__ == "__main__":
    main()
