#!/usr/bin/env python3
"""
Probe Booker from wherever this runs, to find ANY endpoint that serves price data.

Booker's product pages return HTTP 403 ("Access Denied", 307 bytes) to GitHub
runners. Before accepting that, this checks the obvious question: is the whole
domain blocked, or only certain paths? And is there an internal JSON API or a
product feed that is served normally?

This only requests public, ordinary endpoints (the site root, robots.txt, the
sitemap, and the API paths a storefront of this type typically calls). It does not
attempt to defeat or evade any protection -- if Booker declines, that is the answer.

    python3 scripts/booker_probe.py

Reads nothing, writes nothing; it just reports what each endpoint returns.
"""

import re
import sys
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
BASE = "https://www.booker.co.uk"
CODE = "181801"          # KTC Vegetable Cooking Oil 20L (bib)

ENDPOINTS = [
    ("site root",            f"{BASE}/"),
    ("robots.txt",           f"{BASE}/robots.txt"),
    ("sitemap",              f"{BASE}/sitemap.xml"),
    ("product page",         f"{BASE}/products/product?Code={CODE}"),
    ("product search",       f"{BASE}/products/product-search?keywords=KTC+Vegetable+Cooking+Oil"),
    ("api products",         f"{BASE}/api/products/{CODE}"),
    ("api product q",        f"{BASE}/api/product?code={CODE}"),
    ("api catalogue",        f"{BASE}/api/catalogue/product/{CODE}"),
    ("bff product",          f"{BASE}/bff/product/{CODE}"),
    ("occ (SAP Commerce)",   f"{BASE}/occ/v2/booker/products/{CODE}?fields=FULL"),
    ("rest product",         f"{BASE}/rest/v2/products/{CODE}"),
]

HEADERS_HTML = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
HEADERS_JSON = dict(HEADERS_HTML, Accept="application/json,*/*;q=0.8")


def probe(label, url):
    hdrs = HEADERS_JSON if ("api" in url or "occ" in url or "rest" in url or "bff" in url) \
        else HEADERS_HTML
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(200000).decode("utf-8", errors="replace")
            status, ctype = r.status, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(2000).decode("utf-8", errors="replace")
        except Exception:
            pass
        status, ctype = e.code, e.headers.get("Content-Type", "") if e.headers else ""
    except Exception as e:
        print(f"  {label:<22} ERROR   {type(e).__name__}")
        return None

    n = len(body)
    prices = sorted(set(re.findall(r"£\s?\d{1,4}\.\d{2}", body)))[:6]
    jsonish = "json" in (ctype or "").lower() or body.strip()[:1] in "{["
    note = ""
    if status == 403 or "access denied" in body.lower():
        note = "BLOCKED"
    elif prices:
        note = f"PRICES FOUND: {' '.join(prices)}"
    elif jsonish:
        note = "JSON returned (no £ strings -- inspect keys)"
    elif n > 5000:
        note = "page served, no £ found"
    print(f"  {label:<22} {status:<5} {n:>7}b  {ctype[:28]:<28} {note}")
    return {"label": label, "url": url, "status": status, "bytes": n,
            "prices": prices, "json": jsonish}


def main():
    print(f"Probing Booker for any endpoint that serves price data\n{'-'*88}")
    print(f"  {'endpoint':<22} {'code':<5} {'size':>7}   {'content-type':<28} result")
    print(f"{'-'*88}")
    results = [r for r in (probe(l, u) for l, u in ENDPOINTS) if r]

    blocked = [r for r in results if r["status"] == 403]
    served = [r for r in results if r["status"] == 200]
    winners = [r for r in results if r["prices"] or (r["json"] and r["status"] == 200)]

    print(f"\n{'-'*88}")
    print(f"  {len(served)} served, {len(blocked)} blocked, {len(results)} probed")
    if winners:
        print("\n  PROMISING -- these returned usable data:")
        for w in winners:
            print(f"    {w['label']}: {w['url']}")
            if w["prices"]:
                print(f"      prices seen: {' '.join(w['prices'])}")
        print("\n  Next: point the Booker adapter at the best one.")
    elif served:
        print("\n  Some endpoints are served but none expose a price.")
        print("  => the block is targeted at product/pricing data, not the whole domain.")
    else:
        print("\n  Every endpoint blocked => the filtering is by IP, not by path.")
        print("  No code change can read Booker from here; it needs a normal")
        print("  (residential/business) connection, or manual entry.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
