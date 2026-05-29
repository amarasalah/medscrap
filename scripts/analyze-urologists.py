#!/usr/bin/env python3
"""
Analyze French urologists using Gemini API to determine:
1. Has email (yes/no + email value)
2. Has advanced urology keywords (yes/no + which ones)
3. Works in: etatique / privee / both / unknown

Filters to only French urologists.
"""

import json
import re
import time
import os
from pathlib import Path
from threading import Lock

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    print("ERROR: Run: pip install google-generativeai")

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
PUBLIC_DIR = ROOT / "public"
OUTPUT_FILE = DATA_DIR / "fr-urologists-analyzed.json"
PROGRESS_FILE = DATA_DIR / ".analyze-progress.json"

# Advanced urology keywords
KEYWORDS = [
    "PRP urologie", "PRP erectile", "shockwave therapy", "onde de choc", "ondes de choc",
    "pénoplastie", "penoplastie", "peno plastie", "phalloplastie",
    "allongement penien", "allongement pénien", "élargissement penien", "élargissement pénien",
    "injections péniennes", "injection penienne", "injection",
    "stem cells", "cellules souches", "regenerative urology", "urologie régénérative",
    "incontinence urinaire", "incontinence",
    "la Peyronie", "peyronie", "lapeyronie", "maladie de la Peyronie",
    "acide hyaluronique", "botox", "bocox",
    "malformation de la verge", "malformation",
    "implant penien", "implant pénien", "prothese penienne", "prothèse pénienne",
    "implant erectile", "curbure penienne", "courbure pénienne",
    "dysfonction erectile", "dysfonction érectile", "impuissance",
    "éjaculation précoce", "ejaculation precoce",
    "infertilité masculine", "infertilite masculine",
    "vasectomie", "andrologie", "andrologue",
    "sexologie", "médecine sexuelle", "medecine sexuelle",
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

def get_api_key():
    env_path = ROOT / ".env.local"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("GEMINI_API_KEY="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("GEMINI_API_KEY", "")

def analyze_doctor(doctor: dict, model) -> dict:
    """Ask Gemini to analyze a doctor based on available data"""
    name = doctor.get("name", "")
    specialty = doctor.get("specialty", "")
    sub_specialty = doctor.get("subSpecialty", "")
    email = doctor.get("email", "")
    website = doctor.get("website", "")
    addresses = doctor.get("addresses", [])
    addr = addresses[0] if addresses else {}
    address_str = addr.get("address", "")
    city = addr.get("city", "")
    
    keywords_list = ", ".join(KEYWORDS[:20])  # First 20 keywords
    
    prompt = f"""Analyse ce médecin français et réponds UNIQUEMENT avec ce JSON exact:

Médecin: {name}
Spécialité: {specialty}
Sous-spécialité: {sub_specialty}
Adresse: {address_str}
Ville: {city}
Site web: {website}
Email connu: {email if email else "non fourni"}

Mots-clés à chercher: {keywords_list}...

Réponds avec ce JSON:
{{
  "has_email": true/false,
  "email_value": "l'email si trouvé ou connu, sinon vide",
  "sector": "etatique" ou "privee" ou "both" ou "unknown",
  "has_keywords": true/false,
  "matched_keywords": ["liste", "des", "mots", "trouvés"],
  "confidence": "high" ou "medium" ou "low"
}}

Règles:
- has_email: true si tu trouves un email valide dans les données ou sur le site web suggéré
- sector: "etatique" si CHU/hôpital public/clinique publique, "privee" si cabinet privé/clinique privée
- has_keywords: true si le nom, spécialité ou site suggèrent les traitements avancés listés
- confidence: "high" si certain, "medium" si probable, "low" si supposition"""

    try:
        response = model.generate_content(prompt)
        text = response.text
        
        # Extract JSON
        json_match = re.search(r'\{[^}]*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {}
        
        return {
            "has_email": result.get("has_email", bool(email)),
            "email_value": result.get("email_value", email or ""),
            "sector": result.get("sector", "unknown"),
            "has_keywords": result.get("has_keywords", False),
            "matched_keywords": result.get("matched_keywords", []),
            "confidence": result.get("confidence", "low")
        }
    except Exception as e:
        # Fallback to basic extraction
        return {
            "has_email": bool(email),
            "email_value": email or "",
            "sector": "unknown",
            "has_keywords": any(kw.lower() in f"{name} {specialty} {sub_specialty}".lower() for kw in KEYWORDS),
            "matched_keywords": [],
            "confidence": "low",
            "error": str(e)
        }

def main():
    api_key = get_api_key()
    if not api_key:
        print("ERROR: Add GEMINI_API_KEY to .env.local")
        return
    
    if not HAS_GENAI:
        print("ERROR: pip install google-generativeai")
        return
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Load doctors
    doctors = load_json(PUBLIC_DIR / "doctors.json")
    print(f"Loaded {len(doctors)} total doctors")
    
    # Filter French urologists
    candidates = [
        d for d in doctors
        if d.get("country") == "FR"
        and ("urolog" in d.get("specialty", "").lower() 
             or "androlog" in d.get("specialty", "").lower())
    ]
    print(f"Found {len(candidates)} French urologists")
    
    # Load progress
    progress = load_json(PROGRESS_FILE)
    processed_ids = set(progress.get("processed", []))
    to_process = [d for d in candidates if d.get("id") not in processed_ids]
    print(f"Remaining: {len(to_process)}")
    
    if not to_process:
        print("All done!")
        results = progress.get("results", [])
        save_json(OUTPUT_FILE, results)
        print(f"Saved {len(results)} analyzed records to {OUTPUT_FILE}")
        return
    
    # Process
    results = progress.get("results", [])
    processed = 0
    lock = Lock()
    
    print(f"\nAnalyzing {len(to_process)} doctors with Gemini...")
    print("(Rate limit: 15 requests/minute = ~4 sec between calls)")
    
    for doctor in to_process:
        analysis = analyze_doctor(doctor, model)
        
        # Enrich record
        enriched = doctor.copy()
        enriched["analysis"] = analysis
        enriched["has_email"] = analysis["has_email"]
        enriched["email_value"] = analysis["email_value"]
        enriched["sector"] = analysis["sector"]
        enriched["has_keywords"] = analysis["has_keywords"]
        enriched["matched_keywords"] = analysis["matched_keywords"]
        enriched["confidence"] = analysis["confidence"]
        
        with lock:
            processed += 1
            results.append(enriched)
            progress["results"] = results
            progress["processed"] = progress.get("processed", []) + [doctor.get("id")]
            
            if processed % 10 == 0:
                save_json(PROGRESS_FILE, progress)
                stats = {
                    "with_email": sum(1 for r in results if r.get("has_email")),
                    "with_keywords": sum(1 for r in results if r.get("has_keywords")),
                    "etatique": sum(1 for r in results if r.get("sector") == "etatique"),
                    "privee": sum(1 for r in results if r.get("sector") == "privee"),
                }
                print(f"  {processed}/{len(to_process)} | Stats: {stats}")
        
        time.sleep(4)  # Rate limit
    
    # Final save
    save_json(PROGRESS_FILE, progress)
    save_json(OUTPUT_FILE, results)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Complete! Analyzed {len(results)} French urologists")
    print(f"Saved to {OUTPUT_FILE}")
    
    stats = {
        "with_email": sum(1 for r in results if r.get("has_email")),
        "with_keywords": sum(1 for r in results if r.get("has_keywords")),
        "etatique": sum(1 for r in results if r.get("sector") == "etatique"),
        "privee": sum(1 for r in results if r.get("sector") == "privee"),
        "both": sum(1 for r in results if r.get("sector") == "both"),
        "unknown": sum(1 for r in results if r.get("sector") == "unknown"),
    }
    print(f"\nSummary:")
    print(f"  With email: {stats['with_email']}")
    print(f"  With keywords: {stats['with_keywords']}")
    print(f"  Sector - etatique: {stats['etatique']}, privee: {stats['privee']}, both: {stats['both']}, unknown: {stats['unknown']}")
    
    # Sample high-confidence matches
    print(f"\n{'='*60}")
    print("Sample matches with keywords:")
    matches = [r for r in results if r.get("has_keywords") and r.get("confidence") == "high"][:5]
    for r in matches:
        a = r.get("analysis", {})
        print(f"\n  {r['name']}")
        print(f"    Sector: {r.get('sector')} | Email: {r.get('email_value', 'N/A')[:30]}")
        print(f"    Keywords: {r.get('matched_keywords', [])[:3]}")

if __name__ == "__main__":
    main()
