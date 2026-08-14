#!/usr/bin/env python3
"""
Search each seller's catalogue for a term and report candidate products.

Why this exists: adding an oil to the index means finding its product page on
every seller, and those URLs cannot be guessed -- they carry site-specific
codes (JJ's OIL068, Brakes' /p/85753). This runs the search that a person would
run, on a machine that the sellers will actually serve, and prints what it finds
with the URL beside it.

It is a *discovery* tool, not an adapter. It deliberately over-reports: it casts
a wide net and flags the doubtful ones rather than deciding for you. Nothing it
prints reaches the index until a human puts it in config/targets.json. So the
Rule 1 discipline that governs adapters (a price only from a labelled source)
does not apply here -- prices shown are a rough sanity signal, nothing more.

Usage:
    python3 scripts/discover.py --term palm
    python3 scripts/discover.py --term palm --only Marfast,"Magna Foodservice"

Needs Playwright. Booker will return nothing from a datacenter IP -- see
docs/03-booker-collection.md; that is expected, not a bug.
"""
import argparse
import json
import os
import re
import sys
import urllib.parse as up

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = os.path.join(ROOT, "config", "targets.json")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Each seller runs a different shop platform, and each platform has its own
# search URL. We do not know these for certain from here, so every seller gets
# several candidates and the first that returns hits wins -- the report says
# which one worked, so it can be pinned later.
SEARCH_PATTERNS = {
    "Marfast": [                                   # Magento
        "https://marfast.co.uk/catalogsearch/result/?q={q}",
    ],
    "Magna Foodservice": [                         # WooCommerce
        "https://www.magnafoodservice.co.uk/?s={q}&post_type=product",
        "https://www.magnafoodservice.co.uk/?s={q}",
    ],
    "Brakes (Sysco)": [                            # SAP Hybris
        "https://www.brake.co.uk/search?text={q}",
        "https://www.brake.co.uk/search?q={q}",
    ],
    "JJ Foodservice": [                            # React SPA
        "https://www.jjfoodservice.com/search/{q}",
        "https://www.jjfoodservice.com/search?q={q}",
    ],
    "Booker": [                                    # blocked from datacenter IPs
        "https://www.booker.co.uk/products/search?searchTerm={q}",
    ],
}

# A product link is one that looks like a product, not a category or a filter.
PRODUCT_HINTS = ("/product", "/products/", "/p/", ".html")

# Things that are palm-adjacent but would break the "no blends, single source"
# rule, or are the wrong physical product. Flagged, never auto-dropped.
SUSPECT = [
    (r"\bblend|blended\b",                 "BLEND?"),
    (r"rapeseed\s*(&|and|/)\s*palm",       "BLEND?"),
    (r"\bshortening|frying fat|hard fat\b", "SOLID FAT?"),
    (r"\bkernel\b",                        "PALM KERNEL (different oil)"),
    (r"\bsoap|candle|cosmetic\b",          "NOT FOOD"),
]

PRICE_RE = re.compile(r"£\s?\d[\d,]*\.?\d{0,2}")
PACK_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(L|LTR|LITRE|LITRES|KG|G)\b", re.I)


def flags_for(text):
    """Reasons a human should look twice at this result."""
    low = text.lower()
    hits = []
    for pat, label in SUSPECT:
        if re.search(pat, low) and label not in hits:   # two rules can name the same doubt
            hits.append(label)
    return hits


def harvest(page, term):
    """Pull every plausible product link off a rendered search page.

    Deliberately generic: matching on link text and href rather than on each
    site's result-card markup means this keeps working when they redesign, and
    means it needs no per-site selectors to be maintained.
    """
    js = """
    (term) => {
      const t = term.toLowerCase();
      const out = [];
      for (const a of document.querySelectorAll('a[href]')) {
        const text = (a.innerText || '').trim().replace(/\\s+/g, ' ');
        const href = a.href;
        if (!text && !href.toLowerCase().includes(t)) continue;
        if (!text.toLowerCase().includes(t) && !href.toLowerCase().includes(t)) continue;
        // Walk up a little to catch a price that sits beside the title.
        let near = '';
        let node = a;
        for (let i = 0; i < 3 && node; i++) {
          node = node.parentElement;
          if (node) near = (node.innerText || '').replace(/\\s+/g, ' ');
          if (/£/.test(near)) break;
        }
        out.push({ text: text.slice(0, 120), href, near: near.slice(0, 300) });
      }
      return out;
    }
    """
    try:
        rows = page.evaluate(js, term)
    except Exception as exc:
        print(f"      (page script failed: {type(exc).__name__})")
        return []

    seen, results = set(), []
    for r in rows:
        href = r["href"].split("#")[0]
        if href in seen:
            continue
        if not any(h in href for h in PRODUCT_HINTS):
            continue
        seen.add(href)
        price = PRICE_RE.search(r["near"])
        pack = PACK_RE.search(r["text"]) or PACK_RE.search(r["near"])
        results.append({
            "product": r["text"] or "(no link text)",
            "url": href,
            "price_seen": price.group(0) if price else "",
            "pack_seen": f"{pack.group(1)}{pack.group(2).upper()}" if pack else "",
            "flags": flags_for(r["text"] + " " + r["near"]),
        })
    return results


def search_seller(page, seller, term):
    """Try each candidate search URL until one yields product links."""
    for pattern in SEARCH_PATTERNS.get(seller, []):
        url = pattern.format(q=up.quote(term))
        print(f"    {url}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            # SPAs paint results after load; a short settle beats a fixed sleep.
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
        except Exception as exc:
            print(f"      unreachable: {type(exc).__name__}")
            continue

        body = ""
        try:
            body = page.inner_text("body", timeout=3000)[:400].lower()
        except Exception:
            pass
        if "access denied" in body or "403 forbidden" in body:
            print("      blocked (Access Denied) -- expected for Booker")
            continue

        found = harvest(page, term)
        if found:
            return url, found
        print("      no matching products on this page")
    return None, []


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--term", default="palm", help="what to search for (default: palm)")
    ap.add_argument("--only", default="", help="comma-separated sellers to search")
    ap.add_argument("--json", default="", help="also write the results to this path")
    args = ap.parse_args()

    sellers = list(json.load(open(TARGETS))["sellers"])
    if args.only:
        want = [s.strip().lower() for s in args.only.split(",")]
        sellers = [s for s in sellers if s.lower() in want]
    if not sellers:
        print("no sellers selected")
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed -- pip install -r requirements.txt")
        return 1

    print(f'Searching {len(sellers)} seller(s) for "{args.term}"\n')
    everything = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-GB")
        ctx.set_default_timeout(20000)
        page = ctx.new_page()

        for seller in sellers:
            print(f"[{seller}]")
            used, found = search_seller(page, seller, args.term)
            everything[seller] = {"search_url": used, "results": found}
            print(f"      -> {len(found)} candidate(s)\n")

        browser.close()

    print("=" * 78)
    print(f'CANDIDATES FOR "{args.term.upper()}"')
    print("=" * 78)
    total = 0
    for seller, data in everything.items():
        results = data["results"]
        print(f"\n{seller} -- {len(results)} candidate(s)")
        if not results:
            print("  (nothing found -- see the log above for why)")
            continue
        for r in results:
            total += 1
            bits = [b for b in (r["pack_seen"], r["price_seen"]) if b]
            tail = ("  [" + ", ".join(bits) + "]") if bits else ""
            print(f"  - {r['product']}{tail}")
            print(f"    {r['url']}")
            if r["flags"]:
                print(f"    ⚠  {'; '.join(r['flags'])}")

    print("\n" + "=" * 78)
    print(f"{total} candidate(s) across {len(sellers)} seller(s).")
    print("Nothing above is in the index. To add one, put it in")
    print("config/targets.json and run the adapter tests -- see HANDOVER.md §7.")
    print("Check each is a PURE single-source oil in a comparable pack before adding.")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"term": args.term, "sellers": everything}, fh, indent=2)
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
