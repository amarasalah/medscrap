"""Throwaway: verify the UI exposes the new countries, specialties, emails."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    page.goto("http://localhost:3000/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)

    print("Stats:", page.locator(".stat-number").all_inner_texts())
    print("Countries:", page.locator("#filter-country option").all_inner_texts())
    spec_options = page.locator("#filter-specialty option").all_inner_texts()
    print(f"Specialties ({len(spec_options)}):")
    for s in spec_options:
        print(" -", s)
    print("Result count:", page.locator(".filter-result-count").inner_text())
    print("Rows rendered:", page.locator("table.results-table tbody tr").count())
    browser.close()
