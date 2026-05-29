#!/usr/bin/env python3
"""
Fast parallel enrichment of doctor descriptions from:
1. Google Places API editorial_summary
2. Website meta descriptions

Then filter by urology-related keywords.
"""

import json
import re
import sys
import time
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from typing import Optional
from threading import Lock

# Paths
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
PUBLIC_DIR = ROOT / "public"
CACHE_FILE = DATA_DIR / ".desc-cache-v2.json"
OUTPUT_FILE = DATA_DIR / "fr-urology-filtered-fast.json"
PROGRESS_FILE = DATA_DIR / ".desc-progress.json"

# Google Places API
SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# Keywords to filter by (French urology focus) - expanded list
KEYWORDS = [
    # User-specified keywords
    "PRP urologie", "PRP urology", "PRP erectile dysfunction",
    "shockwave therapy", "onde de choc", "ondes de choc",
    "pénoplastie", "penoplastie", "peno plastie", "penoplasty",
    "péniplastie", "peniplastie",
    "phalloplastie", "phalloplasty",
    "allongement penien", "allongement pénien",
    "élargissement penien", "élargissement pénien",
    "augmentation penienne", "augmentation pénienne",
    "injections péniennes", "penile injections", "injection penienne",
    "stem cells urology", "cellules souches urologie", "cellules souches",
    "regenerative urology", "urologie régénérative",
    "incontinance urinaire", "incontinence urinaire", "incontinence",
    "injection",
    "lapeyronie", "la peyronie", "maladie de la peyronie", "peyronie",
    "l'acide hyaluronique", "acide hyaluronique", "hyaluronique",
    "BOTOX", "BOCOX", "botox urologie",
    "MALFORMATION DE LA VERGE", "malformation de la verge", "malformation penienne",
    "implant penien", "implant pénien", "prothese penienne", "prothèse pénienne",
    "implant erectile", "implant erection", "prothese erection",
    # Urology terms
    "urologue", "urologie", "urologiste", "urolog",
    "andrologie", "andrologue", "androlog",
    "dysfonction erectile", "dysfonction érectile", "erectile dysfunction",
    "impuissance", "troubles de l'erection", "troubles de l'érection",
    "ejaculation precoce", "éjaculation précoce", "premature ejaculation",
    "infertilite masculine", "infertilité masculine", "male infertility",
    "vasectomie", "vasectomy",
    "adenome prostate", "adénome prostate", "prostate adenoma",
    "hypertrophie benigne prostate", "hypertrophie bénigne prostate", "HBP", "BPH",
    "cancer prostate", "cancer de la prostate", "prostate cancer",
    "lithiase renale", "lithiase rénale", "kidney stones",
    "infection urinaire", "urinary tract infection",
    "cystite", "cystitis",
    "prostatite", "prostatitis",
    "enuresie", "énurésie", "bedwetting",
    "incontinence urinaire", "urinary incontinence",
    "fuite urinaire", "urinary leakage",
    "dysurie", "dysuria",
    "pollakiurie", "frequent urination",
    "nicturie", "nocturia",
    "hematurie", "hématurie", "hematuria",
    "retention urinaire", "rétention urinaire", "urinary retention",
    "stricture uretrale", "stricture urétrale", "urethral stricture",
    "stenose col vesical", "sténose col vésical",
    "reflux vesico-renal", "reflux vésico-rénal", "vesicoureteral reflux",
    "micropenis", "micropénis", "micropenis",
    "phimosis", "phimosis",
    "paraphimosis", "paraphimosis",
    "balanite", "balanitis",
    "cancer testicule", "cancer du testicule", "testicular cancer",
    "cancer rein", "cancer du rein", "kidney cancer",
    "tumeur vessie", "tumeur de la vessie", "bladder tumor",
    "vessie hyperactive", "overactive bladder",
    "neuro-vessie", "neurogenic bladder",
    "sonde urinaire", "urinary catheter",
    "cystoscopie", "cystoscopy",
    "résection endoscopique prostate", "resection endoscopique prostate", "TURP",
    "laser prostate", "greenlight", "holmium", "thulium", "laser vert",
    "prostatectomie", "prostatectomy",
    "nephrectomie", "néphrectomie", "nephrectomy",
    "cystectomie", "cystectomy",
    "ureteroscopie", "urétéroscopie", "ureteroscopy",
    "lithotritie", "lithotripsy", "lithotripsie",
    "percutanee", "percutanée", "PCNL",
    "biopsie prostate", "biopsie de la prostate", "prostate biopsy",
    "prise en charge globale", "comprehensive care",
    "chirurgie urologique", "urological surgery",
    "chirurgie mini-invasive", "minimally invasive surgery",
    "robotique", "robotic surgery", "da vinci",
    "laparoscopie", "laparoscopy",
    "endourologie", "endourology",
    "urologie fonctionnelle", "functional urology",
    "urologie oncologique", "oncological urology",
    "urologie reconstructrice", "reconstructive urology",
    "urologie pediatrique", "urologie pédiatrique", "pediatric urology",
    "urologie feminine", "urologie féminine", "female urology",
    "sexologie", "sexology",
    "medecine sexuelle", "médecine sexuelle", "sexual medicine",
    "traitement hormonal", "hormone therapy",
    "testosterone", "testostérone", "testosterone",
    "substitution hormonale", "hormone replacement",
    "prise en charge cancer", "cancer care",
    "suivi post-cancer", "post-cancer follow-up",
    "reeducation perineale", "rééducation périnéale", "perineal rehabilitation",
    "reeducation vesicale", "rééducation vésicale", "bladder rehabilitation",
    "electrostimulation", "électrostimulation", "electrical stimulation",
    "biofeedback", "biofeedback",
    "PFPT", "pelvic floor physical therapy", "perineometrie",
    "sante masculine", "santé masculine", "men's health",
    "depistage prostate", "dépistage prostate", "prostate screening",
    "PSA", "prostate specific antigen",
    "touche rectal", "digital rectal exam", "touché rectal",
    "IRM prostate", "prostate MRI", "echo prostate",
    "fusion biopsy", "fusion biopsy",
    "curietherapie", "curiethérapie", "brachytherapy",
    "radiotherapie", "radiothérapie", "radiotherapy",
    "chimiotherapie", "chimiothérapie", "chemotherapy",
    "immunotherapie", "immunothérapie", "immunotherapy",
    "hormonotherapie", "hormonothérapie", "hormone therapy",
    "chirurgie conservatrice", "conservative surgery",
    "prostatectomie radicale", "radical prostatectomy",
    "nerve-sparing", "nerve sparing",
    "rehabilitation sexuelle", "réhabilitation sexuelle", "sexual rehabilitation",
    "prothese penienne", "prothèse pénienne", "penile prosthesis",
    "implant penien", "implant pénien", "penile implant",
    "plastie", "plasty",
    "reconstruction", "reconstruction",
    "reparation", "réparation", "repair",
    # Peyronie/La Peyronie variations
    "peyronie", "induratio penis plastica",
    "courbure penienne", "courbure pénienne", "penile curvature",
    "priapisme", "priapism",
    "erection prolongee", "érection prolongée", "prolonged erection",
    "dysplasie", "dysplasia",
    "malformation", "malformation",
    "hypogonadisme", "hypogonadism",
    "gynecomastie", "gynécomastie", "gynecomastia",
    "varicocele", "varicocèle", "varicocele",
    "hydrocele", "hydrocèle", "hydrocele",
    "spermatocele", "spermatocele",
    "cryptorchidie", "cryptorchidism",
    "anorchidie", "anorchidism",
    "ectopie testiculaire", "testicular ectopia",
    "torsion testiculaire", "testicular torsion",
    "traumatisme testiculaire", "testicular trauma",
    "epididymite", "épididymite", "epididymitis",
    "orchite", "orchite", "orchitis",
    "stenose", "sténose", "stenosis",
    "hypospadias", "hypospadias",
    "epispadias", "épispadias", "epispadias",
    "fistule", "fistula",
    "uretroplastie", "urétroplastie", "urethroplasty",
    "meatotomie", "meatotomy",
    "meatoplastie", "méatoplastie", "meatoplasty",
    "circoncision", "circumcision",
    "posthectomie", "posthectomy",
    "frenectomie", "frénectomie", "frenectomy",
]

# Compile regex for fast matching
KEYWORDS_LOWER = [k.lower() for k in KEYWORDS]

def load_json(path: Path) -> list | dict:
    if not path.exists():
        return {} if "cache" in path.name or "progress" in path.name else []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data):
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    # No retries, fast timeouts
    adapter = requests.adapters.HTTPAdapter(max_retries=0)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    return s

def fetch_place_details_by_name_address(session: requests.Session, api_key: str, name: str, address: str) -> Optional[str]:
    """Find place by name and address, get editorial_summary"""
    try:
        query = f"{name} {address}"
        params = {
            "query": query,
            "key": api_key,
            "region": "fr"
        }
        r = session.get(SEARCH_URL, params=params, timeout=(3, 5))
        data = r.json()
        
        if data.get("status") != "OK" or not data.get("results"):
            return None
            
        place_id = data["results"][0]["place_id"]
        
        # Get details with editorial_summary
        details_params = {
            "place_id": place_id,
            "fields": "editorial_summary",
            "key": api_key
        }
        r2 = session.get(DETAILS_URL, params=details_params, timeout=(3, 5))
        data2 = r2.json()
        
        if data2.get("status") == "OK":
            result = data2.get("result", {})
            editorial = result.get("editorial_summary", {})
            if editorial:
                return editorial.get("overview", "")
        return None
    except Exception:
        return None

def scrape_website_description(session: requests.Session, url: str) -> Optional[str]:
    """Scrape meta description from website"""
    if not url or not url.startswith("http"):
        return None
    
    try:
        r = session.get(url, timeout=(2, 5), allow_redirects=True)
        if r.status_code != 200:
            return None
        
        html = r.text.lower()
        
        # Look for meta description (case insensitive search in already lowercased html)
        patterns = [
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        ]
        
        html_orig = r.text
        for pattern in patterns:
            match = re.search(pattern, html_orig, re.IGNORECASE)
            if match:
                desc = match.group(1).strip()
                if len(desc) > 20:
                    return desc
        
        return None
    except Exception:
        return None

def matches_keywords(text: str) -> tuple[bool, list]:
    """Check if text matches any keywords, return matches found"""
    if not text:
        return False, []
    
    text_lower = text.lower()
    matches = []
    
    for keyword in KEYWORDS_LOWER:
        if keyword in text_lower:
            matches.append(keyword)
    
    return len(matches) > 0, list(set(matches))

def process_record(record: dict, api_key: str, session: requests.Session) -> Optional[dict]:
    """Process a single record, return enriched result if matches"""
    record_id = record.get("id", "")
    
    descriptions = []
    sources = []
    
    # Method 1: Places API editorial_summary
    addr = record.get("addresses", [{}])[0]
    address_str = addr.get("address", "")
    name = record.get("name", "")
    
    if name and address_str and api_key:
        place_desc = fetch_place_details_by_name_address(session, api_key, name, address_str)
        if place_desc:
            descriptions.append(place_desc)
            sources.append("places")
    
    # Method 2: Website scraping
    website = record.get("website", "")
    if website:
        web_desc = scrape_website_description(session, website)
        if web_desc:
            descriptions.append(web_desc)
            sources.append("website")
    
    # Combine descriptions
    combined_desc = " | ".join(descriptions) if descriptions else ""
    
    # Check keyword matches in all relevant text
    text_to_check = f"{name} {record.get('specialty', '')} {record.get('subSpecialty', '')} {combined_desc}"
    has_match, matched_keywords = matches_keywords(text_to_check)
    
    if has_match:
        return {
            "record": record,
            "description": combined_desc,
            "sources": sources,
            "keyword_matches": matched_keywords,
        }
    return None

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
    
    # Load cache and progress
    cache = load_json(CACHE_FILE)
    progress = load_json(PROGRESS_FILE)
    processed_ids = set(progress.get("processed", []))
    print(f"Cache: {len(cache)} entries, Progress: {len(processed_ids)} already processed")
    
    # Filter to candidates:
    # 1. French urologists/andrologists
    # 2. Any French doctor with keywords in existing fields
    candidates = []
    for d in doctors:
        if d.get("country") != "FR":
            continue
        if d.get("id") in processed_ids:
            continue
            
        specialty = d.get("specialty", "").lower()
        sub_specialty = d.get("subSpecialty", "").lower()
        name = d.get("name", "").lower()
        
        # Include urologists/andrologists
        is_urologist = "urolog" in specialty or "urolog" in sub_specialty or "androlog" in specialty
        
        # Also include if keywords already match (fast pre-filter)
        text = f"{name} {specialty} {sub_specialty}"
        has_keyword = any(k in text for k in KEYWORDS_LOWER)
        
        if is_urologist or has_keyword:
            candidates.append(d)
    
    print(f"Found {len(candidates)} candidates to process")
    
    if not candidates:
        print("No new candidates to process")
        # Just output existing results
        all_matching = progress.get("matching", [])
        print(f"Already found {len(all_matching)} matching records")
        save_json(OUTPUT_FILE, all_matching)
        return
    
    # Process with thread pool
    matching_records = []
    session = make_session()
    processed_count = 0
    lock = Lock()
    
    print(f"\nProcessing {len(candidates)} candidates with 10 workers...")
    
    def process_with_session(record):
        nonlocal processed_count
        try:
            result = process_record(record, api_key, session)
            with lock:
                processed_count += 1
                if processed_count % 100 == 0:
                    print(f"  Progress: {processed_count}/{len(candidates)}")
            return result
        except Exception as e:
            with lock:
                processed_count += 1
            return None
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_record = {executor.submit(process_with_session, c): c for c in candidates}
        
        for future in as_completed(future_to_record):
            result = future.result()
            if result:
                matching_records.append(result)
                # Update progress incrementally
                if "matching" not in progress:
                    progress["matching"] = []
                if "processed" not in progress:
                    progress["processed"] = []
                progress["matching"].append(result)
                progress["processed"].append(result["record"]["id"])
                # Save every 10 matches
                if len(matching_records) % 10 == 0:
                    save_json(PROGRESS_FILE, progress)
    
    # Final save
    save_json(PROGRESS_FILE, progress)
    
    # Prepare final output
    all_matching = progress.get("matching", [])
    output = []
    for rec_data in all_matching:
        if isinstance(rec_data, dict) and "record" in rec_data:
            rec = rec_data["record"].copy()
            rec["enriched_description"] = rec_data.get("description", "")
            rec["description_sources"] = rec_data.get("sources", [])
            rec["matched_keywords"] = rec_data.get("keyword_matches", [])
        else:
            rec = rec_data
        output.append(rec)
    
    # Save results
    save_json(OUTPUT_FILE, output)
    print(f"\n{'='*50}")
    print(f"Found {len(output)} total matching records")
    print(f"Saved to {OUTPUT_FILE}")
    
    # Print sample matches
    print(f"\n{'='*50}")
    print("Sample Matches:")
    for e in matching_records[:5]:
        rec = e["record"]
        print(f"\n  {rec.get('name')}")
        print(f"    Specialty: {rec.get('specialty')}")
        print(f"    Keywords: {e['keyword_matches'][:5]}")
        print(f"    Sources: {e['sources']}")
        if e['description']:
            desc = e['description'][:120] + "..." if len(e['description']) > 120 else e['description']
            print(f"    Desc: {desc}")

if __name__ == "__main__":
    main()
