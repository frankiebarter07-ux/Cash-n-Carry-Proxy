#!/usr/bin/env python3
"""
Per-seller price adapters.

Each adapter knows exactly where its seller keeps the price, and returns a Quote
carrying provenance (which method read it) -- or raises AdapterError. See
ARCHITECTURE.md sections 2, 5 and 6.

The two rules, enforced here:
  1. A price is only accepted from a LABELLED source (JSON-LD offers.price, an
     internal JSON API field, or a known price selector). Never a bare-£ regex.
  2. No labelled price -> raise. Never guess, never return a stray number.

Usage:
    python3 scripts/adapters.py --list          # show adapters and their SKUs
    python3 scripts/adapters.py --selftest      # offline tests, no network
    python3 scripts/adapters.py --run           # live fetch (needs network/Playwright)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = os.path.join(ROOT, "config", "targets.json")

PRICE_MIN, PRICE_MAX = 15.0, 60.0      # plausible band for a 20L pack (ARCHITECTURE §6)
MAX_MOVE_PCT = 20.0                    # beyond this vs last price -> hold for review


class AdapterError(Exception):
    """No labelled price could be read. Never swallow this into a default."""


@dataclass
class Quote:
    price_gbp: float
    method: str                 # "json-ld" | "json-api" | "selector:<sel>"
    source_url: str
    fetched_at: str

    def dict(self):
        return asdict(self)


# --------------------------------------------------------------------------- #
# parsing helpers (shared, deliberately strict)
# --------------------------------------------------------------------------- #
def money(value) -> float | None:
    """Parse a GBP amount from a labelled field. Returns None if not sane."""
    if value is None:
        return None
    s = str(value).replace(",", "").replace("£", "").strip()
    m = re.search(r"\d+(?:\.\d{1,2})?", s)
    if not m:
        return None
    try:
        return round(float(m.group(0)), 2)
    except ValueError:
        return None


def price_from_jsonld(html: str) -> float | None:
    """First offers.price in any JSON-LD Product block. A labelled source."""
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE)
    for raw in blocks:
        try:
            data = json.loads(raw.strip())
        except Exception:
            continue

        def walk(node):
            if isinstance(node, list):
                for n in node:
                    r = walk(n)
                    if r is not None:
                        return r
                return None
            if not isinstance(node, dict):
                return None
            offers = node.get("offers")
            if offers:
                for off in (offers if isinstance(offers, list) else [offers]):
                    if isinstance(off, dict):
                        p = money(off.get("price"))
                        if p is not None:
                            return p
            for v in node.values():
                if isinstance(v, (dict, list)):
                    r = walk(v)
                    if r is not None:
                        return r
            return None

        found = walk(data)
        if found is not None:
            return found
    return None


def price_from_meta(html: str) -> float | None:
    """<meta itemprop="price" content="..."> / property="product:price:amount"."""
    for pat in (r'<meta[^>]+itemprop=["\']price["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+itemprop=["\']price["\']',
                r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([^"\']+)'):
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            p = money(m.group(1))
            if p is not None:
                return p
    return None


def validate(price: float, last: float | None = None) -> str:
    """Return '' if publishable, else the reason to hold it for review."""
    if not (PRICE_MIN <= price <= PRICE_MAX):
        return f"outside plausible band £{PRICE_MIN:.0f}-£{PRICE_MAX:.0f}"
    if last:
        move = abs(price - last) / last * 100
        if move > MAX_MOVE_PCT:
            return f"moved {move:.1f}% vs last (£{last:.2f}) -- over {MAX_MOVE_PCT}% threshold"
    return ""


# --------------------------------------------------------------------------- #
# adapters
# --------------------------------------------------------------------------- #
class BaseAdapter:
    name = "base"
    # ordered, seller-specific price selectors (used only by the browser tier)
    selectors: list[str] = []

    def __init__(self, fetch_html=None, fetch_rendered=None):
        # injectable so tests can run with no network
        self._fetch_html = fetch_html
        self._fetch_rendered = fetch_rendered

    # -- tier 2: static HTML (JSON-LD / meta) --------------------------------
    def from_static(self, url: str) -> Quote | None:
        if not self._fetch_html:
            return None
        html = self._fetch_html(url)
        if not html:
            return None
        p = price_from_jsonld(html)
        if p is not None:
            return Quote(p, "json-ld", url, datetime.now(timezone.utc).isoformat())
        p = price_from_meta(html)
        if p is not None:
            return Quote(p, "meta-itemprop", url, datetime.now(timezone.utc).isoformat())
        return None

    # -- tier 3: rendered page + known selector ------------------------------
    def from_rendered(self, url: str) -> Quote | None:
        if not self._fetch_rendered or not self.selectors:
            return None
        for sel in self.selectors:
            text = self._fetch_rendered(url, sel)
            p = money(text)
            if p is not None:
                return Quote(p, f"selector:{sel}", url,
                             datetime.now(timezone.utc).isoformat())
        return None

    def fetch(self, sku: dict) -> Quote:
        url = sku["url"]
        for step in (self.from_static, self.from_rendered):
            q = step(url)
            if q:
                return q
        raise AdapterError(f"{self.name}: no labelled price at {url}")


class MagnaAdapter(BaseAdapter):
    """WooCommerce -- JSON-LD expected. Easiest; build/verify first."""
    name = "Magna Foodservice"
    selectors = ["p.price .woocommerce-Price-amount", ".summary .woocommerce-Price-amount",
                 "[itemprop='price']"]


class MarfastAdapter(BaseAdapter):
    """Magento-style, likely server-rendered."""
    name = "Marfast"
    selectors = ["[data-price-type='finalPrice'] .price", ".price-wrapper .price",
                 "[itemprop='price']"]


class BookerAdapter(BaseAdapter):
    """Direct per-product URLs (Code=...). JS-rendered -> browser tier.

    NOTE: replaces an earlier category-listing keyword match that silently
    returned no price on every run.
    """
    name = "Booker"
    selectors = ["[class*='product-price']", "[class*='price-value']",
                 "[data-testid*='price']", "[itemprop='price']"]


class BrakesAdapter(BaseAdapter):
    """Sysco UK. Check for Akamai on first live run."""
    name = "Brakes (Sysco)"
    selectors = ["[data-testid*='price']", "[class*='ProductPrice']",
                 "[class*='product-price']", "[itemprop='price']"]


class JJAdapter(BaseAdapter):
    """React SPA; 403s plain fetchers.

    Highest-value work is finding the internal JSON API (DevTools > Network >
    Fetch/XHR on a product page) and filling in `api_url_for`. Until then the
    browser tier carries it.
    """
    name = "JJ Foodservice"
    selectors = ["[class*='collection'] [class*='price']", "[class*='product-price']",
                 "[itemprop='price']"]

    # Fill this in once the endpoint is known, e.g.
    #   return f"https://www.jjfoodservice.com/api/product/{code}?branch=London-Enfield"
    def api_url_for(self, url: str) -> str | None:
        return None

    def from_api(self, url: str) -> Quote | None:
        api = self.api_url_for(url)
        if not api or not self._fetch_html:
            return None
        raw = self._fetch_html(api)
        try:
            data = json.loads(raw)
        except Exception:
            return None
        for key in ("collectionPrice", "price", "unitPrice", "sellPrice"):
            p = money(data.get(key) if isinstance(data, dict) else None)
            if p is not None:
                return Quote(p, f"json-api:{key}", api,
                             datetime.now(timezone.utc).isoformat())
        return None

    def fetch(self, sku: dict) -> Quote:
        for step in (self.from_api, self.from_static, self.from_rendered):
            q = step(sku["url"])
            if q:
                return q
        raise AdapterError(f"{self.name}: no labelled price at {sku['url']}")


ADAPTERS = {
    "Magna Foodservice": MagnaAdapter,
    "Marfast": MarfastAdapter,
    "Booker": BookerAdapter,
    "Brakes (Sysco)": BrakesAdapter,
    "JJ Foodservice": JJAdapter,
}


def load_targets():
    with open(TARGETS, encoding="utf-8") as fh:
        return json.load(fh)["sellers"]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_list():
    sellers = load_targets()
    for name, v in sellers.items():
        cls = ADAPTERS.get(name)
        print(f"{name}  ->  {cls.__name__ if cls else 'NO ADAPTER'}  ({len(v['skus'])} SKUs, route: {v['route']})")
    missing = [n for n in sellers if n not in ADAPTERS]
    print("\nAll sellers have an adapter." if not missing else f"\nMissing adapters: {missing}")
    return 0


def cmd_selftest():
    """Offline tests -- no network. Proves the parse rules and the validation gate."""
    ok = True

    def check(label, cond):
        nonlocal ok
        print(("  PASS  " if cond else "  FAIL  ") + label)
        ok = ok and cond

    print("JSON-LD extraction")
    html = '<script type="application/ld+json">{"@type":"Product","name":"KTC 20L","offers":{"@type":"Offer","price":"27.99","priceCurrency":"GBP"}}</script>'
    check("reads offers.price", price_from_jsonld(html) == 27.99)
    nested = '<script type="application/ld+json">{"@graph":[{"@type":"Product","offers":[{"price":31.49}]}]}</script>'
    check("reads nested @graph offers", price_from_jsonld(nested) == 31.49)
    check("returns None when absent", price_from_jsonld("<p>£29.99</p>") is None)

    print("Rule 1 -- a bare £ on the page is NOT a price")
    a = MagnaAdapter(fetch_html=lambda u: "<p>Spend £25.00 for free delivery</p>")
    try:
        a.fetch({"url": "https://example.test/p"})
        check("raises AdapterError instead of taking £25.00", False)
    except AdapterError:
        check("raises AdapterError instead of taking £25.00", True)

    print("meta itemprop fallback")
    a = MarfastAdapter(fetch_html=lambda u: '<meta itemprop="price" content="30.49">')
    q = a.fetch({"url": "https://example.test/p"})
    check("reads meta content", q.price_gbp == 30.49 and q.method == "meta-itemprop")

    print("selector tier + provenance")
    a = BookerAdapter(fetch_html=lambda u: "<html>no labelled price</html>",
                      fetch_rendered=lambda u, sel: "£33.99" if "price" in sel else None)
    q = a.fetch({"url": "https://example.test/p"})
    check("reads via selector", q.price_gbp == 33.99)
    check("records provenance", q.method.startswith("selector:"))

    print("validation gate")
    check("accepts a normal price", validate(30.49) == "")
    check("rejects out-of-band", validate(199.0) != "")
    check("holds a >20% jump", validate(45.0, last=30.0) != "")
    check("allows a small move", validate(31.0, last=30.0) == "")

    print("\nSELFTEST PASSED" if ok else "\nSELFTEST FAILED")
    return 0 if ok else 1


def cmd_run():
    """Live fetch. Needs network; uses Playwright for the rendered tier if present."""
    try:
        import urllib.request
    except ImportError:
        print("stdlib urllib unavailable"); return 1

    UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

    def fetch_html(url):
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept-Language": "en-GB,en;q=0.9"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode(r.headers.get_content_charset() or "utf-8",
                                       errors="replace")
        except Exception as e:
            print(f"    (static fetch failed: {type(e).__name__})")
            return None

    page_holder = {}

    def fetch_rendered(url, selector):
        pw = page_holder.get("page")
        if not pw:
            return None
        try:
            pw.goto(url, wait_until="domcontentloaded", timeout=45000)
            pw.wait_for_timeout(1500)
            loc = pw.locator(selector).first
            if loc.count() == 0:
                return None
            return loc.inner_text(timeout=2500)
        except Exception:
            return None

    browser = ctx = None
    try:
        from playwright.sync_api import sync_playwright
        pwctx = sync_playwright().start()
        browser = pwctx.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-GB")
        page_holder["page"] = ctx.new_page()
        print("Playwright available -- rendered tier enabled\n")
    except Exception:
        print("Playwright unavailable -- static tier only\n")

    results, failures = [], []
    for seller, v in load_targets().items():
        cls = ADAPTERS.get(seller)
        if not cls:
            print(f"{seller}: no adapter"); continue
        ad = cls(fetch_html=fetch_html, fetch_rendered=fetch_rendered)
        print(seller)
        for sku in v["skus"]:
            try:
                q = ad.fetch(sku)
            except AdapterError as e:
                failures.append(str(e))
                print(f"  ✗ {sku['oil']}/{sku['format']}: {e}")
                continue
            why = validate(q.price_gbp)
            flag = "" if not why else f"  [HELD: {why}]"
            results.append({"seller": seller, **sku, **q.dict(), "held": why})
            print(f"  ✓ {sku['oil']}/{sku['format']}: £{q.price_gbp:.2f}  via {q.method}{flag}")
        print()

    print(f"{len(results)} quote(s), {len(failures)} failure(s)")
    if ctx:
        ctx.close()
    if browser:
        browser.close()
    out = os.path.join(ROOT, "data", "adapter_run.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(),
                   "results": results, "failures": failures}, fh, indent=2)
    print(f"wrote {out}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Per-seller price adapters.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.list:
        return cmd_list()
    if a.selftest:
        return cmd_selftest()
    return cmd_run()


if __name__ == "__main__":
    sys.exit(main())
