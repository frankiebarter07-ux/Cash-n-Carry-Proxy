#!/usr/bin/env python3
"""
Authenticated (login-gated) price scraper using Playwright.

Reads per-site login flow + product list from config/auth_sites.json and
credentials ONLY from environment variables (GitHub Actions Secrets). For each
enabled site it logs in, opens each product page, reads the pack price, and
appends a fresh observation to data/observations.csv (deduped per day). Then run
process.py + render_static.py to rebuild.

Usage:
  python3 scripts/scrape_auth.py            # run the scrape (needs Playwright + creds)
  python3 scripts/scrape_auth.py --check    # validate config only (no Playwright, no network)

Honest caveats (see README):
  * Sites behind Cloudflare/Akamai may still challenge a headless browser even
    with a valid login; 2FA breaks automated login; scraping a trade account may
    be against that seller's terms. Verify selectors/URLs against the live site.
  * Credentials must be provided as env vars; nothing is stored in the repo.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "auth_sites.json")
OBS = os.path.join(ROOT, "data", "observations.csv")
FIELDS = ["date", "oil", "channel", "source", "product", "url",
          "pack_value", "pack_unit", "price_gbp", "notes"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
NAV_TIMEOUT = 45000


def load_cfg():
    with open(CFG, encoding="utf-8") as fh:
        return json.load(fh)


def parse_price(text):
    """Pull a plausible GBP amount out of a string; return float or None."""
    if not text:
        return None
    m = re.search(r"([0-9]{1,4}(?:,[0-9]{3})*\.[0-9]{2})", text.replace("£", ""))
    if not m:
        m = re.search(r"£\s*([0-9]{1,4}(?:,[0-9]{3})*)", text)
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return v if 1 <= v < 1000 else None


def existing_keys():
    if not os.path.exists(OBS):
        return set()
    with open(OBS, encoding="utf-8") as fh:
        return {(r["date"], r["source"], r["product"]) for r in csv.DictReader(fh)}


def append_rows(rows):
    if not rows:
        return
    header = not os.path.exists(OBS) or os.path.getsize(OBS) == 0
    with open(OBS, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if header:
            w.writeheader()
        w.writerows(rows)


# ----- config validation (no Playwright needed) --------------------------------
def check(cfg):
    problems = 0
    for name, site in cfg["sites"].items():
        state = "enabled" if site.get("enabled", True) else "disabled"
        creds = site.get("cred_env", {})
        prods = site.get("products", [])
        bad = [p for p in prods if str(p.get("url", "")).startswith("FILL_")]
        print(f"  {name}: {state}, {len(prods)} product(s), "
              f"creds env {creds.get('user')}/{creds.get('pass')}"
              + (f"  [{len(bad)} URL(s) still need filling]" if bad else ""))
        if site.get("enabled", True) and bad:
            problems += 1
            print(f"    ! enabled but has placeholder URLs -- will skip those products")
    print("config OK" if not problems else f"config has {problems} warning(s)")
    return 0


# ----- Playwright helpers ------------------------------------------------------
def _first(page, selectors):
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if loc.count() > 0:
                return loc
        except Exception:
            continue
    return None


def login(page, site, user, pw):
    page.goto(site["login_url"], wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
    u = _first(page, site["username_selectors"])
    p = _first(page, site["password_selectors"])
    if not u or not p:
        raise RuntimeError("login fields not found (check username/password selectors)")
    u.fill(user, timeout=8000)
    p.fill(pw, timeout=8000)
    btn = _first(page, site["submit_selectors"])
    if btn:
        btn.click(timeout=8000)
    else:
        p.press("Enter")
    page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT)


def read_price(page, site, prod):
    """Read a price from a single product page (prod['url'])."""
    page.goto(prod["url"], wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
    page.wait_for_timeout(1500)
    for sel in site.get("price_selectors", []):
        loc = page.locator(sel).first
        try:
            if loc.count() == 0:
                continue
            val = loc.get_attribute("content")  # meta[itemprop=price] etc.
            price = parse_price(val) if val else None
            if not price:
                price = parse_price(loc.inner_text(timeout=2500))
            if price:
                return price
        except Exception:
            continue
    return parse_price(page.content())  # last resort: whole-page scan


def read_price_from_listing(page, site, prod):
    """Find a product on a category/listing page by keyword and read its price.

    Used for sellers (e.g. Booker) that show prices publicly on a listing rather
    than on per-product URLs. 'match'/'exclude' are lowercase keyword lists.
    """
    page.goto(site["list_url"], wait_until="networkidle", timeout=NAV_TIMEOUT)
    page.wait_for_timeout(2500)
    kws = [k.lower() for k in prod.get("match", [])]
    exc = [k.lower() for k in prod.get("exclude", [])]
    selectors = site.get("tile_selectors",
                         ["[class*='product']", "[class*='tile']", "[class*='card']", "li"])
    for sel in selectors:
        try:
            tiles = page.locator(sel)
            n = tiles.count()
        except Exception:
            continue
        for i in range(min(n, 250)):
            try:
                txt = tiles.nth(i).inner_text(timeout=1200)
            except Exception:
                continue
            low = txt.lower()
            if kws and all(k in low for k in kws) and not any(e in low for e in exc):
                price = parse_price(txt)
                if price:
                    return price
    return None


def run():
    cfg = load_cfg()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. `pip install -r requirements.txt` and "
              "`python -m playwright install chromium`. Skipping auth scrape.")
        return 0

    today = date.today().isoformat()
    seen = existing_keys()
    new, ok, fail = [], 0, 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for name, site in cfg["sites"].items():
            if not site.get("enabled", True):
                print(f"·  {name}: disabled -- skip")
                continue
            no_login = site.get("no_login", False)
            user = passwd = None
            if not no_login:
                cu, cp = site["cred_env"]["user"], site["cred_env"]["pass"]
                user, passwd = os.environ.get(cu), os.environ.get(cp)
                if not user or not passwd:
                    print(f"·  {name}: no credentials in env ({cu}/{cp}) -- skip")
                    continue
            ctx = browser.new_context(user_agent=UA, locale="en-GB",
                                      viewport={"width": 1366, "height": 900})
            page = ctx.new_page()
            if not no_login:
                try:
                    login(page, site, user, passwd)
                    print(f"✓  {name}: logged in")
                except Exception as e:
                    fail += 1
                    print(f"✗  {name}: login failed ({type(e).__name__}: {e})")
                    ctx.close()
                    continue
            for prod in site.get("products", []):
                url = str(prod.get("url", ""))
                use_listing = (not url or url.startswith("FILL_")) and site.get("list_url") and prod.get("match")
                if (not url or url.startswith("FILL_")) and not use_listing:
                    print(f"   {name}: {prod['product']} -- URL not filled, skip")
                    continue
                if (today, name, prod["product"]) in seen:
                    print(f"=  {name}: {prod['product']} already recorded today")
                    continue
                try:
                    price = read_price_from_listing(page, site, prod) if use_listing \
                        else read_price(page, site, prod)
                except Exception as e:
                    fail += 1
                    print(f"?  {name}: {prod['product']} error ({type(e).__name__})")
                    continue
                if not price:
                    fail += 1
                    print(f"?  {name}: {prod['product']} no price found")
                    continue
                new.append({
                    "date": today, "oil": prod["oil"], "channel": "cash_carry",
                    "source": name, "product": prod["product"],
                    "url": prod.get("url") or site.get("list_url", ""),
                    "pack_value": prod["pack_value"], "pack_unit": prod["pack_unit"],
                    "price_gbp": round(price, 2), "notes": "auth-scraped",
                })
                ok += 1
                print(f"✓  {name}: {prod['product']} £{price:.2f}")
            ctx.close()
        browser.close()

    append_rows(new)
    print(f"\nAuth scrape: {ok} new price(s), {fail} failed/empty.")
    print("Now run: python3 scripts/process.py && python3 scripts/render_static.py")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Authenticated price scraper.")
    ap.add_argument("--check", action="store_true", help="validate config only")
    args = ap.parse_args()
    cfg = load_cfg()
    return check(cfg) if args.check else run()


if __name__ == "__main__":
    sys.exit(main())
