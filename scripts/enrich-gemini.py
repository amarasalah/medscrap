#!/usr/bin/env python3
"""
Enrich doctor data using Gemini API to:
1. Generate descriptions for doctors
2. Categorize as etattique / privée / both / neither
3. Check for advanced urology keywords
4. Filter to only doctors with emails

Targets: French urologists (urologue)
"""

import json
import re
import time
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Try to import google.generativeai
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    print("Warning: google-generativeai not installed. Run: pip install google-generativeai")

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
PUBLIC_DIR = ROOT / "public"
OUTPUT_FILE = DATA_DIR / "fr-urology-gemini-enriched.json"
PROGRESS_FILE = DATA_DIR / ".gemini-progress.json"

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
    """Get Gemini API key from .env.local or environment"""
    env_path = ROOT / ".env.local"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("GEMINI_API_KEY="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("GEMINI_API_KEY", "")

def analyze_doctor_with_gemini(doctor: dict, model) -> dict:
    """
    Use Gemini to analyze a doctor and return:
    - generated_description
    - category: "etatique" | "privée" | "both" | "neither"
    - has_keywords: bool
    - matched_keywords: list
    """
    name = doctor.get("name", "")
    specialty = doctor.get("specialty", "")
    sub_specialty = doctor.get("subSpecialty", "")
    website = doctor.get("website", "")
    addresses = doctor.get("addresses", [])
    address = addresses[0].get("address", "") if addresses else ""
    city = addresses[0].get("city", "") if addresses else ""
    
    prompt = f"""Analyse ce médecin français et réponds UNIQUEMENT en format JSON:

Nom: {name}
Spécialité: {specialty}
Sous-spécialité: {sub_specialty}
Adresse: {address}
Ville: {city}
Site web: {website}

Réponds avec ce format JSON exact:
{{
  "description": "Une phrase décrivant ce que fait ce médecin (max 150 caractères)",
  "categorie": "etatique" ou "privée" ou "both" ou "neither",
  "services": ["liste", "des", "services", "clés"]
}}

Règles pour la catégorie:
- "etatique": Si Un médecin du secteur public est un professionnel de la santé salarié par l'État exerçant en hôpital public.
- "privée": Si c'est un cabinet privé / clinique privée (pas hôpital public)
- "both": Si les deux
- "neither": Si ni l'un ni l'autre (ex: hôpital public généraliste)

N'invente rien. Si tu ne sais pas, mets "neither"."""

    try:
        response = model.generate_content(prompt)
        text = response.text
        
        # Extract JSON from response
        json_match = re.search(r'\{[^}]*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {}
        
        # Check for keywords in the generated content
        check_text = f"{result.get('description', '')} {' '.join(result.get('services', []))} {specialty} {sub_specialty}".lower()
        matched = [kw for kw in UROLOGY_KEYWORDS if kw.lower() in check_text]
        
        return {
            "description": result.get("description", ""),
            "category": result.get("categorie", "neither"),
            "services": result.get("services", []),
            "has_keywords": len(matched) > 0,
            "matched_keywords": matched
        }
    except Exception as e:
        return {
            "description": "",
            "category": "neither",
            "services": [],
            "has_keywords": False,
            "matched_keywords": [],
            "error": str(e)
        }

def main():
    api_key = get_gemini_api_key()
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env.local or environment")
        print("Add GEMINI_API_KEY=your_key to .env.local")
        return
    
    if not HAS_GENAI:
        print("ERROR: google-generativeai package not installed")
        print("Run: pip install google-generativeai")
        return
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')  # Fast model
    
    # Load doctors data
    doctors = load_json(PUBLIC_DIR / "doctors.json")
    print(f"Loaded {len(doctors)} total doctors")
    
    # Filter to French urologists WITH emails
    candidates = []
    for d in doctors:
        if d.get("country") != "FR":
            continue
        if not d.get("email"):  # Must have email
            continue
        specialty = d.get("specialty", "").lower()
        if "urolog" not in specialty and "androlog" not in specialty:
            continue
        candidates.append(d)
    
    print(f"Found {len(candidates)} French urologists with emails")
    
    # Load progress
    progress = load_json(PROGRESS_FILE)
    processed_ids = set(progress.get("processed", []))
    print(f"Already processed: {len(processed_ids)}")
    
    # Filter out already processed
    to_process = [d for d in candidates if d.get("id") not in processed_ids]
    print(f"Remaining to process: {len(to_process)}")
    
    if not to_process:
        print("All done! Loading results...")
        all_matching = progress.get("matching", [])
        save_json(OUTPUT_FILE, all_matching)
        print(f"Saved {len(all_matching)} records to {OUTPUT_FILE}")
        return
    
    # Process with Gemini
    matching_records = []
    processed_count = 0
    lock = Lock()
    
    print(f"\nAnalyzing {len(to_process)} doctors with Gemini...")
    print("(Rate limit: ~15 requests/minute for free tier)")
    
    for doctor in to_process:
        result = analyze_doctor_with_gemini(doctor, model)
        
        # Add Gemini data to record
        enriched = doctor.copy()
        enriched["gemini_description"] = result.get("description", "")
        enriched["category"] = result.get("category", "neither")
        enriched["gemini_services"] = result.get("services", [])
        enriched["has_keywords"] = result.get("has_keywords", False)
        enriched["matched_keywords"] = result.get("matched_keywords", [])
        
        # Count categories
        with lock:
            processed_count += 1
            if result.get("has_keywords"):
                matching_records.append(enriched)
                progress["matching"] = progress.get("matching", []) + [enriched]
            progress["processed"] = progress.get("processed", []) + [doctor.get("id")]
            
            if processed_count % 10 == 0:
                save_json(PROGRESS_FILE, progress)
                print(f"  Progress: {processed_count}/{len(to_process)} | Matches: {len(matching_records)}")
        
        # Rate limiting (Gemini free tier: 15 RPM)
        time.sleep(4)
    
    # Final save
    save_json(PROGRESS_FILE, progress)
    save_json(OUTPUT_FILE, progress.get("matching", []))
    
    # Summary
    all_matching = progress.get("matching", [])
    print(f"\n{'='*60}")
    print(f"Complete! Found {len(all_matching)} matching records")
    print(f"Saved to {OUTPUT_FILE}")
    
    # Category breakdown
    cats = {}
    for d in all_matching:
        cat = d.get("category", "neither")
        cats[cat] = cats.get(cat, 0) + 1
    print(f"\nCategory breakdown:")
    for cat, count in cats.items():
        print(f"  {cat}: {count}")
    
    # Sample outputs
    print(f"\n{'='*60}")
    print("Sample enriched records:")
    for d in all_matching[:5]:
        print(f"\n  {d.get('name')}")
        print(f"    Category: {d.get('category')}")
        print(f"    Keywords: {d.get('matched_keywords')[:3]}")
        print(f"    Desc: {d.get('gemini_description', '')[:80]}...")
        print(f"    Email: {d.get('email', 'N/A')[:30]}...")

if __name__ == "__main__":
    main()
