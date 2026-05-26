"""For every record with a `profileUrl`, fetch the page and look for
`mailto:` links. Sets `record.email` to the first plausible match.

Run:
    python scripts/enrich-emails.py public/doctors.json
    python scripts/enrich-emails.py data/gb-places-aesthetic.json --workers 8

Concurrency: ThreadPoolExecutor over distinct domains. Per-page timeout
8 s. Records without a website are skipped. The script writes back to
the input file in place (after creating a .bak the first time).

Hit rate: usually 20-30%. Many sites use contact forms, some emails are
hidden by JS. We treat generic addresses (info@, contact@, hello@) as
fallbacks when no doctor-specific address can be found on the page.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import log, make_session

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MAILTO_RE = re.compile(r"mailto:([^\"'>\s?]+)", re.I)

GENERIC_PREFIXES = ("info@", "contact@", "hello@", "hi@", "team@",
                    "secretariat@", "receptionist@", "reception@", "admin@",
                    "enquiries@", "appointments@", "secretariado@",
                    "secretaria@", "cita@", "rdv@")

# Skip social / image / app domains we know don't hold mailto links
SKIP_HOSTS = {
    "www.facebook.com", "facebook.com", "instagram.com", "twitter.com",
    "x.com", "linkedin.com", "youtube.com", "tiktok.com", "pinterest.com",
    "maps.google.com", "g.co", "goo.gl",
}

# Directory aggregator domains. Emails on these domains are the directory
# operator (e.g. enquiries@cqc.org.uk), NOT the doctor — reject them.
DIRECTORY_EMAIL_DOMAINS = {
    "sante.fr", "esante.gouv.fr", "ars.sante.fr",
    "cqc.org.uk", "nhs.uk", "nhs.net",
    "doctolib.fr", "doctolib.com",
    "doctify.com", "doctify.co.uk",
    "doctoralia.es", "doctoralia.com",
    "topdoctors.co.uk", "topdoctors.es", "topdoctors.fr",
    "google.com", "googlemail.com", "gmail.com",  # gmail itself is often a contact form noreply
}


def is_directory_email(addr: str) -> bool:
    if "@" not in addr:
        return False
    domain = addr.rsplit("@", 1)[1].lower()
    return any(domain == d or domain.endswith("." + d)
               for d in DIRECTORY_EMAIL_DOMAINS)


PLACEHOLDER_EMAILS = {
    "email@site.com", "you@example.com", "name@example.com",
    "user@example.com", "test@test.com", "test@test.fr", "test@gmail.com",
    "name@domain.com", "your-email@example.com", "info@example.com",
    "email@example.com", "your@email.com",
}

# Domains used by JS error-tracking / dev infra. Their "emails" are bug-report
# ingest tokens, not real addresses.
TRACKING_EMAIL_DOMAINS = {
    "sentry.io", "ingest.sentry.io", "ingest.us.sentry.io",
    "sentry-next.wixpress.com", "wixpress.com",
    "bugsnag.com", "rollbar.com", "raygun.io", "datadoghq.com",
    "newrelic.com",
}


def looks_like_email(s: str) -> bool:
    if not EMAIL_RE.fullmatch(s):
        return False
    low = s.lower()
    if "example." in low or low.endswith(".png") or low.endswith(".jpg"):
        return False
    if low in PLACEHOLDER_EMAILS:
        return False
    # Reject obvious placeholders / dev artifacts
    if "@site.com" in low or "@yoursite." in low or "@domain." in low:
        return False
    if is_directory_email(low):
        return False
    # Reject error-tracking sentinel addresses (32-char hex local-part is the
    # tell-tale Sentry/Wix pattern).
    domain = low.rsplit("@", 1)[1]
    if any(domain == d or domain.endswith("." + d)
           for d in TRACKING_EMAIL_DOMAINS):
        return False
    return True


def pick_best_email(emails: list[str]) -> str | None:
    if not emails:
        return None
    # Prefer doctor-y, then non-generic, then generic
    non_generic = [e for e in emails
                   if not any(e.lower().startswith(p) for p in GENERIC_PREFIXES)]
    return (non_generic[0] if non_generic else emails[0]).strip()


def extract_emails(html: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for m in MAILTO_RE.finditer(html):
        addr = m.group(1).split("?")[0].strip().lower()
        if looks_like_email(addr) and addr not in seen:
            seen.add(addr)
            found.append(addr)
    if not found:
        # Fallback: bare email patterns in text (skip if too many — likely a list)
        text_addrs = EMAIL_RE.findall(html)
        if 1 <= len(set(text_addrs)) <= 5:
            for a in text_addrs:
                low = a.lower()
                if low not in seen and looks_like_email(low):
                    seen.add(low)
                    found.append(low)
    return found


def fetch_email(session: requests.Session, url: str) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return None
    if host in SKIP_HOSTS:
        return None
    # If the URL itself is a directory aggregator, the page only contains the
    # directory operator's email — don't waste an HTTP call.
    h_low = host.lower().lstrip("www.")
    if any(h_low == d or h_low.endswith("." + d) for d in DIRECTORY_EMAIL_DOMAINS):
        return None

    try:
        r = session.get(url, timeout=4, allow_redirects=True)
    except requests.RequestException:
        return None
    if r.status_code != 200 or "text/html" not in (r.headers.get("Content-Type") or ""):
        return None
    emails = extract_emails(r.text)
    pick = pick_best_email(emails)
    if pick:
        return pick

    # Try /contact subpage
    base = f"{urlparse(url).scheme}://{host}"
    for path in ("/contact", "/contacto"):
        try:
            r2 = session.get(urljoin(base, path), timeout=3, allow_redirects=True)
        except requests.RequestException:
            continue
        if r2.status_code != 200:
            continue
        emails = extract_emails(r2.text)
        if emails:
            return pick_best_email(emails)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, help="only process first N records")
    args = ap.parse_args()

    raw_text = args.input.read_text(encoding="utf-8")
    records = json.loads(raw_text)
    # Back up the ORIGINAL bytes before we modify anything in memory.
    bak = args.input.with_suffix(args.input.suffix + ".bak")
    if not bak.exists():
        bak.write_text(raw_text, encoding="utf-8")

    def has_real_url(r) -> bool:
        """True if any URL on the record points outside known directory hosts."""
        for u in (r.get("website"), r.get("profileUrl")):
            if not u:
                continue
            try:
                host = (urlparse(u).hostname or "").lower().lstrip("www.")
            except Exception:
                continue
            if host in SKIP_HOSTS:
                continue
            if any(host == d or host.endswith("." + d)
                   for d in DIRECTORY_EMAIL_DOMAINS):
                continue
            return True
        return False

    todo = [(i, r) for i, r in enumerate(records)
            if has_real_url(r) and not r.get("email")]
    if args.limit:
        todo = todo[:args.limit]
    log(f"records to try: {len(todo)} (of {len(records)} total)")

    session = make_session()
    found = 0
    processed = 0
    lock = threading.Lock()

    def worker(item):
        idx, rec = item
        # Prefer the clinic website (set by places.py enrich); fall back to
        # profileUrl. fetch_email already skips directory hosts.
        for url in (rec.get("website"), rec.get("profileUrl")):
            if not url:
                continue
            email = fetch_email(session, url)
            if email:
                return idx, email
        return idx, None

    def flush() -> None:
        args.input.write_text(json.dumps(records, ensure_ascii=False),
                              encoding="utf-8")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(worker, item) for item in todo]
        for fut in as_completed(futures):
            idx, email = fut.result()
            with lock:
                processed += 1
                if email:
                    records[idx]["email"] = email
                    found += 1
                if processed % 100 == 0:
                    log(f"  processed {processed}/{len(todo)}, found {found}")
                    flush()  # incremental safety against crashes

    log(f"done; emails found: {found}/{len(todo)}")
    flush()
    log(f"wrote -> {args.input}")


if __name__ == "__main__":
    main()
