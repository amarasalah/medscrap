#!/usr/bin/env python3
"""
Enrich doctor data by:
1. Scraping website content (homepage + key pages)
2. Using Gemini API to analyze scraped content
3. Categorizing as etatique / privée / both / neither
4. Checking for advanced urology keywords
5. Filtering to only doctors with emails

Targets: French urologists (urologue) with emails
"""

import json
import re
import time
import os
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
from threading import Lock

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
PUBLIC_DIR = ROOT / "public"
OUTPUT_FILE = DATA_DIR / "fr-urology-gemini-advanced.json"
PROGRESS_FILE = DATA_DIR / ".gemini-web-progress.json"

# Keywords to check for
UROLOGY_KEYWORDS = [
    "prp", "prp urologie", "prp erectile",
    "shockwave", "shockwave therapy", "onde de choc", "ondes de choc",
    "penoplastie", "pénoplastie", "peno plastie", "phalloplastie",
    "allongement penien", "allongement pénien", "élargissement penien", "élargissement pénien",
    "injections péniennes", "injection penienne", "injection",
    "stem cells", "cellules souches", "regenerative", "urologie régénérative",
    "incontinence urinaire", "incontinence",
    "la peyronie", "peyronie", "lapeyronie", "maladie de la peyronie",
    "acide hyaluronique",
    "botox", "bocox",
    "malformation de la verge", "malformation",
    "implant penien", "implant pénien", "prothese penienne", "prothèse pénienne",
    "implant erectile", "curbure penienne", "courbure pénienne",
    "dysfonction erectile", "dysfonction érectile", "impuissance",
    "ejaculation precoce", "éjaculation précoce",
    "infertilite masculine", "infertilité masculine",
    "vasectomie",
    "andrologie", "andrologue",
    "sexologie", "medecine sexuelle", "médecine sexuelle",
]

# Pages to scrape
SUBPATHS = ["/", "/services", "/traitements", "/specialites", "/urologie", "/contact"]

def load_json(path: Path):
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_gemini_api_key():
    env_path = ROOT / ".env.local"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("GEMINI_API_KEY="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("GEMINI_API_KEY", "")

def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    adapter = requests.adapters.HTTPAdapter(max_retries=0)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    return s

def scrape_website_fast(session, base_url):
    """Scrape website quickly, return combined text from accessible pages"""
    if not base_url or not base_url.startswith("http"):
        return ""
    
    all_text = []
    base_url = base_url.rstrip("/")
    parsed = urlparse(base_url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    
    for subpath in SUBPATHS[:3]:  # Only first 3 for speed
        try:
            url = urljoin(domain, subpath)
            r = session.get(url, timeout=(2, 6), allow_redirects=True)
            if r.status_code == 200:
                text = extract_text_from_html(r.text)
                if len(text) > 100:
                    all_text.append(f"--- Page {subpath or '/'} ---\n{text[:2000]}")
        except:
            pass
    
    return "\n".join(all_text)

def extract_text_from_html(html):
    """Extract readable text from HTML"""
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'\s+', ' ', html)
    return html.strip()

def analyze_with_gemini(text, doctor_info, model):
    """Use Gemini to analyze scraped website content"""
    name = doctor_info.get("name", "")
    specialty = doctor_info.get("specialty", "")
    
    prompt = f"""Analyse ce site web de médecin et réponds en JSON.

Médecin: {name}
Spécialité: {specialty}

CONTENU DU SITE WEB:
{text[:4000]}

Réponds avec ce format JSON:
{{
  "description": "Résumé des services offerts (max 150 caractères)",
  "categorie": "etatique" ou "privee" ou "both" ou "neither",
  "traitements_avances": ["liste des traitements spécifiques trouvés"],
  "has_advanced_keywords": true/false
}}

Règles pour catégorie:
- "etatique": hôpital public / CHU / clinique publique
- "privee": cabinet privé / clinique privée
- "both": mixte
- "neither": inconnu

Traitements avancés à chercher: PRP, shockwave/ondes de choc, pénoplastie, implants pénien, cellules souches, acide hyaluronique, botox, maladie de La Peyronie, incontinence, dysfonction érectile."""

    try:
        response = model.generate_content(prompt)
        text_resp = response.text
        
        # Extract JSON
        json_match = re.search(r'\{[^}]*\}', text_resp, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {}
        
        return {
            "description": result.get("description", ""),
            "category": result.get("categorie", "neither"),
            "treatments": result.get("traitements_avances", []),
            "has_advanced": result.get("has_advanced_keywords", False)
        }
    except Exception as e:
        return {"description": "", "category": "neither", "treatments": [], "has_advanced": False, "error": str(e)}

def process_doctor(doctor, session, model):
    """Process single doctor: scrape + analyze with Gemini"""
    website = doctor.get("website", "")
    
    # Scrape website
    scraped_text = ""
    if website:
        scraped_text = scrape_website_fast(session, website)
    
    # Analyze with Gemini (even if no website, to categorize)
    gemini_result = analyze_with_gemini(scraped_text, doctor, model)
    
    # Check for keywords in scraped text + gemini results
    check_text = f"{scraped_text} {' '.join(gemini_result.get('treatments', []))}".lower()
    matched_keywords = [kw for kw in UROLOGY_KEYWORDS if kw.lower() in check_text]
    
    has_match = gemini_result.get("has_advanced", False) or len(matched_keywords) > 0
    
    if has_match or gemini_result.get("category") in ["privee", "both"]:
        return {
            "doctor": doctor,
            "scraped_text": scraped_text[:500] if scraped_text else "",
            "gemini": gemini_result,
            "matched_keywords": matched_keywords,
            "has_match": has_match
        }
    return None

def main():
    api_key = get_gemini_api_key()
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found")
        return
    
    if not HAS_GENAI:
        print("ERROR: google-generativeai not installed")
        return
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Load data
    doctors = load_json(PUBLIC_DIR / "doctors.json")
    print(f"Loaded {len(doctors)} total doctors")
    
    # Filter French urologists with emails
    candidates = [
        d for d in doctors
        if d.get("country") == "FR" 
        and d.get("email")
        and ("urolog" in d.get("specialty", "").lower() or 
             "androlog" in d.get("specialty", "").lower())
    ]
    print(f"Found {len(candidates)} French urologists with emails")
    
    # Load progress
    progress = load_json(PROGRESS_FILE)
    processed_ids = set(progress.get("processed", []))
    to_process = [d for d in candidates if d.get("id") not in processed_ids]
    print(f"Remaining: {len(to_process)}")
    
    if not to_process:
        print("All done!")
        save_json(OUTPUT_FILE, progress.get("matching", []))
        return
    
    # Process
    session = make_session()
    matching = []
    processed = 0
    lock = Lock()
    
    print(f"\nProcessing {len(to_process)} doctors...")
    
    for doctor in to_process:
        result = process_doctor(doctor, session, model)
        
        with lock:
            processed += 1
            if result and result.get("has_match"):
                enriched = doctor.copy()
                enriched["gemini_description"] = result["gemini"].get("description", "")
                enriched["category"] = result["gemini"].get("category", "neither")
                enriched["treatments"] = result["gemini"].get("treatments", [])
                enriched["matched_keywords"] = result.get("matched_keywords", [])
                enriched["has_scraped_content"] = bool(result.get("scraped_text"))
                matching.append(enriched)
                progress["matching"] = progress.get("matching", []) + [enriched]
            
            progress["processed"] = progress.get("processed", []) + [doctor.get("id")]
            
            if processed % 10 == 0:
                save_json(PROGRESS_FILE, progress)
                print(f"  Progress: {processed}/{len(to_process)} | Advanced matches: {len(matching)}")
        
        time.sleep(4)  # Gemini rate limit
    
    save_json(PROGRESS_FILE, progress)
    save_json(OUTPUT_FILE, progress.get("matching", []))
    
    print(f"\n{'='*60}")
    print(f"Complete! Found {len(matching)} advanced urology matches")
    print(f"Saved to {OUTPUT_FILE}")
    
    # Summary
    cats = {}
    for d in matching:
        cat = d.get("category", "neither")
        cats[cat] = cats.get(cat, 0) + 1
    print(f"\nCategories: {cats}")
    
    # Sample
    print(f"\n{'='*60}")
    print("Sample matches:")
    for d in matching[:5]:
        print(f"\n  {d['name']} | {d.get('category')}")
        print(f"    Treatments: {d.get('treatments', [])[:3]}")
        print(f"    Keywords: {d.get('matched_keywords', [])[:3]}")
        print(f"    Email: {d.get('email', 'N/A')[:30]}...")

if __name__ == "__main__":
    main()
