#!/usr/bin/env python3
"""
Daily best-effort re-scrape of the configured product prices (UK sellers only).

For every product in config/products.json marked "scrapable": true, this fetches
the page and tries to read the current single-pack price (JSON-LD offer price first,
then a £-price regex). Any price found is appended to data/observations.csv as a
fresh observation for today; process.py then re-aggregates.

Reality check (why this is best-effort, not real-time):
  * Most UK cash & carry / wholesale sites (JJ Foodservice, Brakes/Sysco, Magna,
    Bestway) sit behind Cloudflare/Akamai bot-protection and return HTTP 403 to any
    automated fetch, or hide prices behind a trade login. Those are marked
    "scrapable": false and are kept fresh via scripts/add_observation.py instead.
  * There is no public price API and no push feed for these sellers, so "instant"
    monitoring is not achievable. Wholesale oil prices move over days/weeks, so a
    once-a-day pass captures all real movement.

Standard library only (urllib) so it runs in CI with no pip install.
"""

import csv
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS_PATH = os.path.join(ROOT, "config", "products.json")
OBS_PATH = os.path.join(ROOT, "data", "observations.csv")
FIELDS = ["date", "oil", "channel", "source", "product", "url",
          "pack_value", "pack_unit", "price_gbp", "notes"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
TIMEOUT = 25


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def price_from_jsonld(html):
    """Return the first offers.price found in any JSON-LD block, or None."""
    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(block.strip())
        except Exception:
            continue
        for node in data if isinstance(data, list) else [data]:
            if not isinstance(node, dict):
                continue
            offers = node.get("offers")
            for off in (offers if isinstance(offers, list) else [offers] if offers else []):
                if isinstance(off, dict) and off.get("price"):
                    try:
                        return float(str(off["price"]).replace(",", ""))
                    except ValueError:
                        pass
    return None


def price_from_regex(html):
    """Fallback: the first plausible £ amount on the page (>= £1)."""
    for m in re.findall(r'£\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)', html):
        try:
            v = float(m.replace(",", ""))
            if v >= 1:
                return v
        except ValueError:
            continue
    return None


def existing_keys():
    if not os.path.exists(OBS_PATH):
        return set()
    with open(OBS_PATH, encoding="utf-8") as fh:
        return {(r["date"], r["source"], r["product"]) for r in csv.DictReader(fh)}


def main():
    with open(PRODUCTS_PATH, encoding="utf-8") as fh:
        products = json.load(fh)["products"]

    today = date.today().isoformat()
    seen = existing_keys()
    new_rows, ok, blocked, skipped = [], 0, 0, 0

    print(f"Daily scrape {today} -- {len(products)} products\n")
    for p in products:
        tag = f"{p['oil']:9s} {p['source']}"
        if not p.get("scrapable"):
            skipped += 1
            print(f"  ·  {tag:34s} manual (gated) -- skip")
            continue
        key = (today, p["source"], p["product"])
        if key in seen:
            print(f"  =  {tag:34s} already recorded today")
            continue
        try:
            html = fetch(p["url"])
        except (urllib.error.HTTPError, urllib.error.URLError, Exception) as e:  # noqa
            blocked += 1
            print(f"  ✗  {tag:34s} fetch failed ({type(e).__name__})")
            continue
        price = price_from_jsonld(html) or price_from_regex(html)
        if not price:
            blocked += 1
            print(f"  ?  {tag:34s} no price found on page")
            continue
        new_rows.append({
            "date": today, "oil": p["oil"], "channel": p["channel"],
            "source": p["source"], "product": p["product"], "url": p["url"],
            "pack_value": p["pack_value"], "pack_unit": p["pack_unit"],
            "price_gbp": round(price, 2), "notes": "auto-scraped",
        })
        ok += 1
        print(f"  ✓  {tag:34s} £{price:.2f} / {p['pack_value']}{p['pack_unit']}")

    if new_rows:
        write_header = not os.path.exists(OBS_PATH) or os.path.getsize(OBS_PATH) == 0
        with open(OBS_PATH, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if write_header:
                w.writeheader()
            w.writerows(new_rows)

    print(f"\nScraped {ok} new price(s); {blocked} blocked/empty; {skipped} manual-only.")
    print("Now run: python3 scripts/process.py")
    # Non-zero exit only if literally nothing scrapable succeeded AND there were targets.
    if ok == 0 and any(p.get("scrapable") for p in products):
        print("(No automated prices captured this run -- manual sources unaffected.)")


if __name__ == "__main__":
    sys.exit(main())
