"""Shared scraper utilities. See scripts/schema.md for the output shape."""
from __future__ import annotations

import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Callable, Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PUBLIC_DIR = ROOT / "public"
DATA_DIR.mkdir(exist_ok=True)


def _load_env_local() -> None:
    """Tiny .env.local loader so scripts pick up secrets without a deps."""
    env_path = ROOT / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_local()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504))
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return s


def polite_sleep(min_s: float = 0.8, max_s: float = 2.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


# ----- Phone formatting -----

def format_phone_fr(raw: str) -> str | None:
    if not raw:
        return None
    d = re.sub(r"\D", "", raw)
    if d.startswith("33") and len(d) == 11:
        d = "0" + d[2:]
    if len(d) == 10:
        return " ".join(d[i:i + 2] for i in range(0, 10, 2))
    return raw.strip() or None


def format_phone_uk(raw: str) -> str | None:
    if not raw:
        return None
    d = re.sub(r"\D", "", raw)
    if d.startswith("44") and len(d) >= 12:
        d = "0" + d[2:]
    if len(d) == 11 and d.startswith("0"):
        return f"{d[:5]} {d[5:8]} {d[8:]}"
    return raw.strip() or None


def format_phone_es(raw: str) -> str | None:
    if not raw:
        return None
    d = re.sub(r"\D", "", raw)
    if d.startswith("34") and len(d) == 11:
        d = d[2:]
    if len(d) == 9:
        return f"{d[:3]} {d[3:5]} {d[5:7]} {d[7:]}"
    return raw.strip() or None


PHONE_FORMATTERS = {"FR": format_phone_fr, "GB": format_phone_uk, "ES": format_phone_es}


def make_phone(country: str, raw: str) -> dict | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    return {"raw": digits, "formatted": PHONE_FORMATTERS.get(country, lambda x: x)(raw) or raw}


def make_address(
    *,
    address: str = "",
    city: str = "",
    postal_code: str = "",
    department: str = "",
    region: str = "",
    lat: float | None = None,
    lng: float | None = None,
    maps_url: str = "",
) -> dict:
    return {
        "address": (address or "").strip(),
        "city": (city or "").strip(),
        "postalCode": (postal_code or "").strip(),
        "department": (department or "").strip(),
        "region": (region or "").strip(),
        "lat": lat,
        "lng": lng,
        "mapsUrl": (maps_url or "").strip(),
    }


def make_record(
    *,
    country: str,
    type_: str = "professionnel_de_sante",
    name: str,
    specialty: str = "",
    sub_specialty: str = "",
    profile_url: str = "",
    website: str = "",
    email: str | None = None,
    phones: Iterable[dict] = (),
    addresses: Iterable[dict] = (),
    convention: str | None = None,
) -> dict:
    return {
        "id": None,  # assigned at merge time
        "country": country,
        "type": type_,
        "name": (name or "").strip(),
        "specialty": (specialty or "").strip(),
        "subSpecialty": (sub_specialty or "").strip(),
        "profileUrl": (profile_url or "").strip(),
        "website": (website or "").strip(),
        "email": email,
        "phones": [p for p in phones if p],
        "addresses": [a for a in addresses if a],
        "convention": convention,
    }


# ----- Geography maps -----

FR_DEPT = {
    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes", "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes",
    "09": "Ariège", "10": "Aube", "11": "Aude", "12": "Aveyron", "13": "Bouches-du-Rhône",
    "14": "Calvados", "15": "Cantal", "16": "Charente", "17": "Charente-Maritime",
    "18": "Cher", "19": "Corrèze", "21": "Côte-d'Or", "22": "Côtes-d'Armor",
    "23": "Creuse", "24": "Dordogne", "25": "Doubs", "26": "Drôme", "27": "Eure",
    "28": "Eure-et-Loir", "29": "Finistère", "2A": "Corse-du-Sud", "2B": "Haute-Corse",
    "30": "Gard", "31": "Haute-Garonne", "32": "Gers", "33": "Gironde", "34": "Hérault",
    "35": "Ille-et-Vilaine", "36": "Indre", "37": "Indre-et-Loire", "38": "Isère",
    "39": "Jura", "40": "Landes", "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire",
    "44": "Loire-Atlantique", "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne",
    "48": "Lozère", "49": "Maine-et-Loire", "50": "Manche", "51": "Marne",
    "52": "Haute-Marne", "53": "Mayenne", "54": "Meurthe-et-Moselle", "55": "Meuse",
    "56": "Morbihan", "57": "Moselle", "58": "Nièvre", "59": "Nord", "60": "Oise",
    "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dôme",
    "64": "Pyrénées-Atlantiques", "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales",
    "67": "Bas-Rhin", "68": "Haut-Rhin", "69": "Rhône", "70": "Haute-Saône",
    "71": "Saône-et-Loire", "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie",
    "75": "Paris", "76": "Seine-Maritime", "77": "Seine-et-Marne", "78": "Yvelines",
    "79": "Deux-Sèvres", "80": "Somme", "81": "Tarn", "82": "Tarn-et-Garonne",
    "83": "Var", "84": "Vaucluse", "85": "Vendée", "86": "Vienne", "87": "Haute-Vienne",
    "88": "Vosges", "89": "Yonne", "90": "Territoire de Belfort", "91": "Essonne",
    "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis", "94": "Val-de-Marne",
    "95": "Val-d'Oise", "971": "Guadeloupe", "972": "Martinique", "973": "Guyane",
    "974": "La Réunion", "976": "Mayotte",
}

FR_REGION = {
    "Ain": "Auvergne-Rhône-Alpes", "Aisne": "Hauts-de-France", "Allier": "Auvergne-Rhône-Alpes",
    "Alpes-de-Haute-Provence": "Provence-Alpes-Côte d'Azur",
    "Hautes-Alpes": "Provence-Alpes-Côte d'Azur",
    "Alpes-Maritimes": "Provence-Alpes-Côte d'Azur", "Ardèche": "Auvergne-Rhône-Alpes",
    "Ardennes": "Grand Est", "Ariège": "Occitanie", "Aube": "Grand Est",
    "Aude": "Occitanie", "Aveyron": "Occitanie",
    "Bouches-du-Rhône": "Provence-Alpes-Côte d'Azur", "Calvados": "Normandie",
    "Cantal": "Auvergne-Rhône-Alpes", "Charente": "Nouvelle-Aquitaine",
    "Charente-Maritime": "Nouvelle-Aquitaine", "Cher": "Centre-Val de Loire",
    "Corrèze": "Nouvelle-Aquitaine", "Corse-du-Sud": "Corse", "Haute-Corse": "Corse",
    "Côte-d'Or": "Bourgogne-Franche-Comté", "Côtes-d'Armor": "Bretagne",
    "Creuse": "Nouvelle-Aquitaine", "Dordogne": "Nouvelle-Aquitaine",
    "Doubs": "Bourgogne-Franche-Comté", "Drôme": "Auvergne-Rhône-Alpes",
    "Eure": "Normandie", "Eure-et-Loir": "Centre-Val de Loire", "Finistère": "Bretagne",
    "Gard": "Occitanie", "Haute-Garonne": "Occitanie", "Gers": "Occitanie",
    "Gironde": "Nouvelle-Aquitaine", "Hérault": "Occitanie", "Ille-et-Vilaine": "Bretagne",
    "Indre": "Centre-Val de Loire", "Indre-et-Loire": "Centre-Val de Loire",
    "Isère": "Auvergne-Rhône-Alpes", "Jura": "Bourgogne-Franche-Comté",
    "Landes": "Nouvelle-Aquitaine", "Loir-et-Cher": "Centre-Val de Loire",
    "Loire": "Auvergne-Rhône-Alpes", "Haute-Loire": "Auvergne-Rhône-Alpes",
    "Loire-Atlantique": "Pays de la Loire", "Loiret": "Centre-Val de Loire",
    "Lot": "Occitanie", "Lot-et-Garonne": "Nouvelle-Aquitaine", "Lozère": "Occitanie",
    "Maine-et-Loire": "Pays de la Loire", "Manche": "Normandie", "Marne": "Grand Est",
    "Haute-Marne": "Grand Est", "Mayenne": "Pays de la Loire",
    "Meurthe-et-Moselle": "Grand Est", "Meuse": "Grand Est", "Morbihan": "Bretagne",
    "Moselle": "Grand Est", "Nièvre": "Bourgogne-Franche-Comté", "Nord": "Hauts-de-France",
    "Oise": "Hauts-de-France", "Orne": "Normandie", "Pas-de-Calais": "Hauts-de-France",
    "Puy-de-Dôme": "Auvergne-Rhône-Alpes",
    "Pyrénées-Atlantiques": "Nouvelle-Aquitaine", "Hautes-Pyrénées": "Occitanie",
    "Pyrénées-Orientales": "Occitanie", "Bas-Rhin": "Grand Est", "Haut-Rhin": "Grand Est",
    "Rhône": "Auvergne-Rhône-Alpes", "Haute-Saône": "Bourgogne-Franche-Comté",
    "Saône-et-Loire": "Bourgogne-Franche-Comté", "Sarthe": "Pays de la Loire",
    "Savoie": "Auvergne-Rhône-Alpes", "Haute-Savoie": "Auvergne-Rhône-Alpes",
    "Paris": "Île-de-France", "Seine-Maritime": "Normandie",
    "Seine-et-Marne": "Île-de-France", "Yvelines": "Île-de-France",
    "Deux-Sèvres": "Nouvelle-Aquitaine", "Somme": "Hauts-de-France", "Tarn": "Occitanie",
    "Tarn-et-Garonne": "Occitanie", "Var": "Provence-Alpes-Côte d'Azur",
    "Vaucluse": "Provence-Alpes-Côte d'Azur", "Vendée": "Pays de la Loire",
    "Vienne": "Nouvelle-Aquitaine", "Haute-Vienne": "Nouvelle-Aquitaine",
    "Vosges": "Grand Est", "Yonne": "Bourgogne-Franche-Comté",
    "Territoire de Belfort": "Bourgogne-Franche-Comté", "Essonne": "Île-de-France",
    "Hauts-de-Seine": "Île-de-France", "Seine-Saint-Denis": "Île-de-France",
    "Val-de-Marne": "Île-de-France", "Val-d'Oise": "Île-de-France",
    "Guadeloupe": "Outre-mer", "Martinique": "Outre-mer", "Guyane": "Outre-mer",
    "La Réunion": "Outre-mer", "Mayotte": "Outre-mer",
}


def fr_geo_from_postal(postal: str) -> tuple[str, str]:
    """Return (department, region) from a French postal code."""
    if not postal or len(postal) < 2:
        return "", ""
    code = postal[:2]
    if code == "20":
        code = "2A"
    elif postal.startswith("97") and len(postal) >= 3:
        code = postal[:3]
    dept = FR_DEPT.get(code, "")
    region = FR_REGION.get(dept, "")
    return dept, region


# UK: NHS England regions cover counties. Simplified mapping below.
UK_COUNTY_REGION = {
    # London
    "Greater London": "London", "London": "London",
    # South East
    "Kent": "South East", "Surrey": "South East", "Sussex": "South East",
    "East Sussex": "South East", "West Sussex": "South East", "Hampshire": "South East",
    "Berkshire": "South East", "Buckinghamshire": "South East",
    "Oxfordshire": "South East", "Isle of Wight": "South East",
    # South West
    "Dorset": "South West", "Devon": "South West", "Cornwall": "South West",
    "Somerset": "South West", "Wiltshire": "South West", "Gloucestershire": "South West",
    "Bristol": "South West",
    # East of England
    "Essex": "East of England", "Hertfordshire": "East of England",
    "Bedfordshire": "East of England", "Cambridgeshire": "East of England",
    "Norfolk": "East of England", "Suffolk": "East of England",
    # East Midlands
    "Lincolnshire": "East Midlands", "Nottinghamshire": "East Midlands",
    "Derbyshire": "East Midlands", "Leicestershire": "East Midlands",
    "Rutland": "East Midlands", "Northamptonshire": "East Midlands",
    # West Midlands
    "Warwickshire": "West Midlands", "Staffordshire": "West Midlands",
    "Shropshire": "West Midlands", "Worcestershire": "West Midlands",
    "Herefordshire": "West Midlands", "West Midlands": "West Midlands",
    # Yorkshire and the Humber
    "North Yorkshire": "Yorkshire and the Humber",
    "West Yorkshire": "Yorkshire and the Humber",
    "South Yorkshire": "Yorkshire and the Humber",
    "East Riding of Yorkshire": "Yorkshire and the Humber",
    # North West
    "Lancashire": "North West", "Cheshire": "North West",
    "Greater Manchester": "North West", "Merseyside": "North West",
    "Cumbria": "North West",
    # North East
    "Northumberland": "North East", "Tyne and Wear": "North East",
    "County Durham": "North East",
    # Devolved
    "Scotland": "Scotland", "Wales": "Wales", "Northern Ireland": "Northern Ireland",
}

# ES: provincia → comunidad autónoma
ES_COMUNIDAD = {
    "Álava": "País Vasco", "Albacete": "Castilla-La Mancha", "Alicante": "Comunidad Valenciana",
    "Almería": "Andalucía", "Asturias": "Asturias", "Ávila": "Castilla y León",
    "Badajoz": "Extremadura", "Barcelona": "Cataluña", "Bizkaia": "País Vasco",
    "Burgos": "Castilla y León", "Cáceres": "Extremadura", "Cádiz": "Andalucía",
    "Cantabria": "Cantabria", "Castellón": "Comunidad Valenciana", "Ceuta": "Ceuta",
    "Ciudad Real": "Castilla-La Mancha", "Córdoba": "Andalucía", "Cuenca": "Castilla-La Mancha",
    "Gipuzkoa": "País Vasco", "Girona": "Cataluña", "Granada": "Andalucía",
    "Guadalajara": "Castilla-La Mancha", "Huelva": "Andalucía", "Huesca": "Aragón",
    "Illes Balears": "Islas Baleares", "Jaén": "Andalucía", "La Coruña": "Galicia",
    "La Rioja": "La Rioja", "Las Palmas": "Canarias", "León": "Castilla y León",
    "Lleida": "Cataluña", "Lugo": "Galicia", "Madrid": "Comunidad de Madrid",
    "Málaga": "Andalucía", "Melilla": "Melilla", "Murcia": "Región de Murcia",
    "Navarra": "Navarra", "Orense": "Galicia", "Palencia": "Castilla y León",
    "Pontevedra": "Galicia", "Salamanca": "Castilla y León",
    "Santa Cruz de Tenerife": "Canarias", "Segovia": "Castilla y León",
    "Sevilla": "Andalucía", "Soria": "Castilla y León", "Tarragona": "Cataluña",
    "Teruel": "Aragón", "Toledo": "Castilla-La Mancha", "Valencia": "Comunidad Valenciana",
    "Valladolid": "Castilla y León", "Zamora": "Castilla y León", "Zaragoza": "Aragón",
}


# ----- I/O helpers -----

def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=None)


def read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def log(msg: str) -> None:
    safe = msg.encode("ascii", "replace").decode("ascii")
    print(f"[scrape] {safe}", flush=True)


def fetch(session: requests.Session, url: str, **kwargs) -> requests.Response | None:
    try:
        r = session.get(url, timeout=30, **kwargs)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        log(f"fetch failed {url}: {e}")
        return None
