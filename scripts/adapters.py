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
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = os.path.join(ROOT, "config", "targets.json")
OILS = os.path.join(ROOT, "config", "oils.json")

PRICE_MIN, PRICE_MAX = 15.0, 60.0      # default plausible band, a 20L pack (ARCHITECTURE §6)
MAX_MOVE_PCT = 20.0                    # beyond this vs last price -> hold for review


class AdapterError(Exception):
    """No labelled price could be read. Never swallow this into a default."""


@dataclass
class Quote:
    price_gbp: float
    method: str                 # "json-ld" | "json-api" | "selector:<sel>"
    source_url: str
    fetched_at: str
    sku_code: str = ""          # the seller's own product code, "" if not published

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


def sku_from_jsonld(html: str) -> str:
    """The seller's own product code from a JSON-LD Product block, or "".

    Metadata, not a price -- so unlike price parsing this is allowed to come back
    empty and must never raise. A missing code costs a lookup later; a wrong price
    corrupts the index, which is why the two are held to different standards.
    """
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
                    if (r := walk(n)):
                        return r
                return None
            if not isinstance(node, dict):
                return None
            # schema.org order of preference: sku is the seller's code, mpn the
            # manufacturer's, productID a catch-all.
            for key in ("sku", "mpn", "productID"):
                v = node.get(key)
                if isinstance(v, (str, int)) and str(v).strip():
                    return str(v).strip()[:40]
            for v in node.values():
                if isinstance(v, (dict, list)) and (r := walk(v)):
                    return r
            return None

        if (found := walk(data)):
            return found
    return ""


# Sellers that put the code in the URL. Cheapest possible source: no extra fetch,
# and it keeps working even when the page markup changes.
_SKU_URL_PATTERNS = [
    r"[?&]Code=(\d+)",                              # Booker
    r"/product/[^/]+/([A-Z]{2,}\d+)/?",             # JJ Foodservice: /product/<branch>/OIL011/
]


def sku_from_url(url: str) -> str:
    for pat in _SKU_URL_PATTERNS:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return ""


# Magento and most storefronts render the code beside the word "SKU".
_SKU_TEXT_RE = re.compile(r"\bSKU[:\s#]*([A-Za-z0-9][A-Za-z0-9._/-]{1,24})", re.I)


def sku_from_text(html: str) -> str:
    """Last resort: a 'SKU 84' style label in the page text."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    m = _SKU_TEXT_RE.search(text)
    return m.group(1) if m else ""


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


def validate(price: float, last: float | None = None, band=None) -> str:
    """Return '' if publishable, else the reason to hold it for review.

    'band' lets an oil sold in a different pack carry its own plausible range --
    a £25 box of palm is normal, but would be a red flag for a 20L drum. Oils
    that set no band in oils.json get the 20L default.
    """
    lo, hi = band or (PRICE_MIN, PRICE_MAX)
    if not (lo <= price <= hi):
        return f"outside plausible band £{lo:.0f}-£{hi:.0f}"
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

    def __init__(self, fetch_html=None, fetch_rendered=None, fetch_labelled=None,
                 fetch_page_html=None):
        # injectable so tests can run with no network
        self._fetch_html = fetch_html
        self._fetch_rendered = fetch_rendered
        self._fetch_labelled = fetch_labelled
        self._fetch_page_html = fetch_page_html

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

    # -- tier 2b: label-anchored price ---------------------------------------
    # Sellers commonly show "Delivery £X  Collection £Y" together. Anchoring on the
    # word is far more durable than a CSS position: utility classes (ms-2/ms-3)
    # change on any restyle, the word "Collection" does not.
    price_label = None          # set to "Collection" to enable

    # Containers to search within, tried in order. A product page also shows
    # *other* products (related, recently viewed, basket) and each of those
    # carries its own "Collection £x" -- searching the whole page can therefore
    # return a labelled price belonging to a different SKU. Anything listed here
    # is only a hint: if none match, the search falls back to the block around the
    # page's <h1>, which is the main product on any ordinary product page.
    label_scope: list[str] = []

    def capture_sku(self, url: str) -> str:
        """The seller's product code, best effort. Never raises, never blocks a price.

        Tried cheapest first: the URL often carries it (JJ, Booker) and costs no
        request at all; only if that fails is the page fetched for JSON-LD or a
        'SKU 1234' label. Kept separate from the price path on purpose -- this is
        provenance metadata, and no failure here should be able to lose a price
        that was read correctly.
        """
        try:
            if code := sku_from_url(url):
                return code
            if not self._fetch_html:
                return ""
            html = self._fetch_html(url)
            return sku_from_jsonld(html) or sku_from_text(html)
        except Exception:
            return ""

    def from_label(self, url) -> Quote | None:
        if not self.price_label or not self._fetch_labelled:
            return None
        res = self._fetch_labelled(url, self.price_label, self.label_scope)
        scope = ""
        if isinstance(res, dict):
            scope, res = res.get("scope", ""), res.get("value")
        p = money(res)
        if p is not None:
            method = f"label:{self.price_label}" + (f"@{scope}" if scope else "")
            return Quote(p, method, url, datetime.now(timezone.utc).isoformat())
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

    # When True, read the displayed (rendered) price first. Needed where the
    # static/JSON-LD figure is not the collection price we track.
    prefer_rendered = False

    def fetch(self, sku: dict) -> Quote:
        url = sku["url"]
        order = ((self.from_label, self.from_rendered, self.from_static)
                 if self.prefer_rendered
                 else (self.from_label, self.from_static, self.from_rendered))
        for step in order:
            q = step(url)
            if q:
                return q
        raise AdapterError(f"{self.name}: no labelled price at {url}")


class MagnaAdapter(BaseAdapter):
    """WooCommerce.

    Diagnostics showed JSON-LD carries £28.99 while the page displays £27.99 --
    the structured data is stale/list price. Read the displayed price instead.
    """
    name = "Magna Foodservice"
    prefer_rendered = True
    price_label = "Collection"      # page shows "Delivery £28.99 Collection £27.99"
    # Whole-page label search returned £12.49 (a "Delivery £0.00 Collection £12.49"
    # row belonging to another product) and, on the drum page, the bib's £27.99.
    # Confine the search to the WooCommerce product summary.
    label_scope = ["div.summary.entry-summary", "div.mfs-product-detail-meta",
                   "div.product-detail", "div.product.type-product"]
    # mfs-fs-18 = the main product block (related products use mfs-fs-16);
    # ms-3 = collection, ms-2 = delivery. Backup only -- the label tier is primary,
    # because these are Bootstrap spacing classes and will not survive a restyle.
    selectors = ["div.mfs-fs-18.fw-semibold.ms-3 span.woocommerce-Price-amount",
                 "li:has-text('Collection') div.ms-3 span.woocommerce-Price-amount"]


class MarfastAdapter(BaseAdapter):
    """Magento.

    Diagnostics showed the page renders TWO prices with an identical class path
    (£34.29 and £32.79). meta[itemprop=price] returns the higher one; the
    collection price we track is the lower. Selectors below target the
    collection block; the next diagnose run confirms the distinguishing label.
    """
    name = "Marfast"
    prefer_rendered = True
    price_label = "Collection"      # page renders delivery and collection together
    label_scope = ["div.product-info-main", "div.product-info-price"]  # Magento
    selectors = ["[class*='collection'] .price-wrapper .price",
                 "[data-price-type='finalPrice'] .price",
                 ".price-container.price-final_price .price-wrap"]


def price_from_booker_embedded(html: str) -> tuple:
    """Read Booker's pricing from the JSON embedded in the product page.

    Booker server-renders its pricing into the document (confirmed 2026-08-10 via
    DevTools: all matches for the price were inside the main document, never a
    separate API call). The page carries clearly named fields:

        "collectOE":{"wsp":30.69            <- collection at depot
        "clickAndCollect":{"wsp":30.69      <- click & collect
        "delivered":{"wsp":30.69            <- delivery
        "standardPricing":{"price":"£30.69"
        "formattedPrice":"£30.69"

    We track the COLLECTION price, so collection fields are tried first and the
    delivered field is never used. Returns (price, field_name) or (None, None).
    """
    patterns = [
        ("collectOE",       r'"collectOE"\s*:\s*\{[^}]*?"wsp"\s*:\s*([0-9]+(?:\.[0-9]{1,2})?)'),
        ("clickAndCollect", r'"clickAndCollect"\s*:\s*\{[^}]*?"wsp"\s*:\s*([0-9]+(?:\.[0-9]{1,2})?)'),
        ("standardPricing", r'"standardPricing"\s*:\s*\{[^}]*?"price"\s*:\s*"?£?\s*([0-9]+(?:\.[0-9]{1,2})?)'),
        ("formattedPrice",  r'"formattedPrice"\s*:\s*"£?\s*([0-9]+(?:\.[0-9]{1,2})?)'),
    ]
    for field, pat in patterns:
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            p = money(m.group(1))
            if p is not None:
                return p, field
    return None, None


class BookerAdapter(BaseAdapter):
    """Booker.

    Pricing is embedded as JSON in the product document -- no separate API exists
    (verified in DevTools). Parsing is therefore easy and precise; the only
    obstacle is that Booker returns HTTP 403 to datacenter IPs, so this adapter
    only succeeds when run from a residential/business connection (self-hosted
    runner). See HANDOVER.md section 3.
    """
    name = "Booker"
    selectors = ["[class*='product-price']", "[class*='price-value']",
                 "[data-testid*='price']", "[itemprop='price']"]

    def from_embedded(self, url) -> Quote | None:
        for getter in (self._fetch_html, self._fetch_page_html):
            if not getter:
                continue
            html = getter(url)
            if not html:
                continue
            if "access denied" in html[:2000].lower():
                continue
            price, field = price_from_booker_embedded(html)
            if price is not None:
                return Quote(price, f"embedded-json:{field}", url,
                             datetime.now(timezone.utc).isoformat())
        return None

    def fetch(self, sku: dict) -> Quote:
        url = sku["url"]
        for step in (self.from_embedded, self.from_rendered, self.from_static):
            q = step(url)
            if q:
                return q
        raise AdapterError(
            f"{self.name}: no labelled price at {url}. If this says 403/Access "
            f"Denied, the request came from a datacenter IP -- run the collector "
            f"from a self-hosted runner on a normal connection.")


class BrakesAdapter(BaseAdapter):
    """Sysco UK. Check for Akamai on first live run."""
    name = "Brakes (Sysco)"
    selectors = ["[data-testid*='price']", "[class*='ProductPrice']",
                 "[class*='product-price']", "[itemprop='price']"]


class JJAdapter(BaseAdapter):
    """React SPA that 403s plain fetchers, yet serves JSON-LD to a browser -- so
    the static tier reads it and no API hunt was ever needed. See ARCHITECTURE 4."""
    name = "JJ Foodservice"
    price_label = "Collection"
    selectors = ["[class*='collection'] [class*='price']", "[class*='product-price']",
                 "[itemprop='price']"]

    def fetch(self, sku: dict) -> Quote:
        for step in (self.from_static, self.from_rendered):
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


OBS = os.path.join(ROOT, "data", "observations.csv")
OBS_FIELDS = ["date", "oil", "brand", "format", "channel", "source", "product",
              "url", "sku", "pack_value", "pack_unit", "price_gbp", "notes"]
_BRAND_RULES = [(r"chef'?s larder", "Chef's Larder"), (r"sysco classic", "Sysco Classic"),
                (r"chef'?s choice", "KTC Chef's Choice"),
                (r"extended life rapeseed|ktc extended life", "KTC Extended Life"),
                (r"\bktc\b", "KTC")]


def _brand(product):
    low = product.lower()
    for pat, b in _BRAND_RULES:
        if re.search(pat, low):
            return b
    return "Other"


def _write_observations(results):
    """Append today's publishable quotes, replacing same-day rows for those SKUs."""
    import csv
    from datetime import date as _date
    today = _date.today().isoformat()
    oils_cfg = load_oils()
    rows = []
    for r in results:
        if r.get("held"):
            print(f"  (held, not written: {r['seller']} {r['oil']}/{r['format']} -- {r['held']})")
            continue
        pack_value, pack_unit = _pack_for(oils_cfg, r["oil"])
        rows.append({
            "date": today, "oil": r["oil"], "brand": _brand(r["product"]),
            "format": r["format"], "channel": "cash_carry", "source": r["seller"],
            "product": r["product"], "url": r["url"],
            "sku": r.get("sku_code", ""), "pack_value": pack_value,
            "pack_unit": pack_unit, "price_gbp": f"{r['price_gbp']:.2f}",
            "notes": f"auto ({r['method']})",
        })
    if not rows:
        print("nothing publishable to write"); return
    existing = []
    if os.path.exists(OBS):
        with open(OBS, encoding="utf-8") as fh:
            existing = list(csv.DictReader(fh))
    new_keys = {(r["date"], r["source"], r["product"]) for r in rows}
    keep = [e for e in existing
            if (e["date"], e["source"], e["product"]) not in new_keys]
    out = keep + rows
    out.sort(key=lambda r: (r["date"], r["oil"], r["source"], r["format"]))
    with open(OBS, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OBS_FIELDS)
        w.writeheader(); w.writerows(out)
    print(f"wrote {len(rows)} observation(s) to {OBS}")


def load_targets():
    with open(TARGETS, encoding="utf-8") as fh:
        return json.load(fh)["sellers"]


def load_oils():
    with open(OILS, encoding="utf-8") as fh:
        return json.load(fh)["oils"]


def _band_for(oils_cfg, oil):
    """The oil's own plausible price band, or the 20L default."""
    b = (oils_cfg.get(oil) or {}).get("price_band")
    return (b[0], b[1]) if b else (PRICE_MIN, PRICE_MAX)


def _pack_for(oils_cfg, oil):
    """The pack an observation is recorded in -- (value, unit)."""
    p = (oils_cfg.get(oil) or {}).get("standard_pack") or {"value": 20, "unit": "L"}
    return p["value"], p["unit"]


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

    print("label anchoring (Delivery vs Collection)")
    import re as _re
    def _lbl(text, label="Collection"):
        m = _re.search(label + r"\s*:?\s*£\s?([0-9]{1,4}(?:\.[0-9]{2})?)", text, _re.I)
        return float(m.group(1)) if m else None
    check("picks Collection, not Delivery (Magna layout)",
          _lbl("Delivery £28.99 Collection £27.99") == 27.99)
    check("works when Collection comes first (Marfast layout)",
          _lbl("Collection: £32.79 Delivery: £34.29") == 32.79)
    a = MagnaAdapter(fetch_labelled=lambda u, l, s: "27.99",
                     fetch_html=lambda u: '<meta itemprop="price" content="28.99">')
    q = a.fetch({"url": "https://example.test/p"})
    check("label tier beats the stale meta/JSON-LD value",
          q.price_gbp == 27.99 and q.method == "label:Collection")

    print("label scoping (a page shows other products' Collection prices too)")
    seen = {}
    def _spy(u, l, s):
        seen["scopes"] = list(s)
        return {"value": "31.49", "scope": "product-block"}
    a = MagnaAdapter(fetch_labelled=_spy)
    q = a.fetch({"url": "https://example.test/p"})
    check("adapter's label_scope reaches the fetcher",
          "div.summary.entry-summary" in seen.get("scopes", []))
    check("the scope used is recorded as provenance",
          q.method == "label:Collection@product-block" and q.price_gbp == 31.49)
    check("Marfast scopes to the Magento product block",
          "div.product-info-main" in MarfastAdapter.label_scope)

    print("Booker embedded JSON (real page text)")
    booker_html = (
        'const args = { ...{ "sucode": 181801, "standardPricing": { "price": "£30.69", '
        '"priceInclVat":30.69,"collectOE":{"wsp":30.69,"x":1},'
        '"clickAndCollect":{"wsp":30.69},"delivered":{"wsp":31.99},'
        '"formattedPrice":"£30.69" } }')
    pr, fld = price_from_booker_embedded(booker_html)
    check("reads the collection price from embedded JSON", pr == 30.69)
    check("uses a collection field, never 'delivered'", fld in ("collectOE", "clickAndCollect"))
    a = BookerAdapter(fetch_html=lambda u: booker_html)
    q = a.fetch({"url": "https://www.booker.co.uk/products/product?Code=181801"})
    check("adapter returns it with provenance", q.price_gbp == 30.69
          and q.method.startswith("embedded-json:"))
    blocked = BookerAdapter(fetch_html=lambda u: "<HTML><HEAD>Access Denied</HEAD></HTML>")
    try:
        blocked.fetch({"url": "https://www.booker.co.uk/x"})
        check("refuses an Access Denied stub", False)
    except AdapterError:
        check("refuses an Access Denied stub", True)

    print("validation gate")
    check("accepts a normal price", validate(30.49) == "")
    check("rejects out-of-band", validate(199.0) != "")
    check("holds a >20% jump", validate(45.0, last=30.0) != "")
    check("allows a small move", validate(31.0, last=30.0) == "")
    # An oil in its own pack carries its own band, or a cheap box reads as an error.
    _oils = {"palm": {"price_band": [12.0, 55.0],
                      "standard_pack": {"value": 12.5, "unit": "kg"}}}
    check("per-oil band accepts a £13 box", validate(13.0, band=_band_for(_oils, "palm")) == "")
    check("default band would have rejected it", validate(13.0) != "")
    check("per-oil pack is read from config", _pack_for(_oils, "palm") == (12.5, "kg"))
    check("unknown oil falls back to the 20L pack", _pack_for(_oils, "nope") == (20, "L"))

    print("seller SKU codes (metadata: may be empty, must never raise)")
    check("JJ's code comes free from the URL",
          sku_from_url("https://www.jjfoodservice.com/product/London-Enfield/OIL011/") == "OIL011")
    check("Booker's comes from the query string",
          sku_from_url("https://www.booker.co.uk/products/product?Code=141775&x=y") == "141775")
    check("a slug URL yields nothing rather than guessing",
          sku_from_url("https://marfast.co.uk/prep-palm-oil-12-5kg-box.html") == "")
    check("JSON-LD sku is preferred over mpn",
          sku_from_jsonld('<script type="application/ld+json">'
                          '{"@type":"Product","mpn":"M-9","sku":"ABC123"}</script>') == "ABC123")
    check("falls back to mpn when there is no sku",
          sku_from_jsonld('<script type="application/ld+json">'
                          '{"@type":"Product","mpn":"M-9"}</script>') == "M-9")
    check("malformed JSON-LD returns empty, does not raise",
          sku_from_jsonld('<script type="application/ld+json">{not json</script>') == "")
    check("reads a Magento-style 'SKU 84' label",
          sku_from_text("<div>Availability: In stock <b>SKU</b> 84</div>") == "84")
    check("no SKU label anywhere returns empty",
          sku_from_text("<div>Delivered: £34.29</div>") == "")

    print("\nSELFTEST PASSED" if ok else "\nSELFTEST FAILED")
    return 0 if ok else 1


def cmd_run(only=None, exclude=None, write=False):
    """Live fetch. Needs network; uses Playwright for the rendered tier if present.

    only/exclude filter sellers (used to split cloud vs self-hosted collection).
    write=True appends validated quotes to data/observations.csv.
    """
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
    SKU_BUDGET = 75          # seconds one SKU may consume across all its tiers

    def _out_of_time():
        """True once this SKU has had its share. A slow seller costs us that
        seller's price for a day; it must never cost us the whole run."""
        started = page_holder.get("started")
        return started is not None and (time.monotonic() - started) > SKU_BUDGET

    def _prepare(pw, url):
        """Navigate, dismiss consent banners, wait for the price to actually load."""
        if page_holder.get("at") == url:
            return True
        pw.goto(url, wait_until="domcontentloaded", timeout=30000)
        for sel in ("button:has-text('Accept')", "button:has-text('Allow all')",
                    "#onetrust-accept-btn-handler", "button:has-text('I accept')"):
            try:
                b = pw.locator(sel).first
                if b.count() > 0 and b.is_visible():
                    b.click(timeout=3000)
                    break
            except Exception:
                pass
        try:
            pw.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        pw.wait_for_timeout(2000)
        page_holder["at"] = url
        return True

    def fetch_page_html(url):
        """Full HTML after rendering -- lets embedded-JSON parsing use the browser."""
        pw = page_holder.get("page")
        if not pw or _out_of_time():
            return None
        try:
            _prepare(pw, url)
            return pw.content()
        except Exception:
            return None

    def fetch_labelled(url, label, scopes=()):
        """Return the £ value that follows `label` in the tightest element
        containing both, searched *within the main product block only*.

        Handles "Delivery £28.99 Collection £27.79". The scoping matters as much
        as the label: a product page also lists related/recently-viewed products,
        each with its own "Collection £x", and the tightest of those can easily be
        a different SKU's price. Returns {"value", "scope"} so the chosen root is
        recorded as provenance alongside the price.
        """
        pw = page_holder.get("page")
        if not pw or _out_of_time():
            return None
        try:
            _prepare(pw, url)
            # NOTE: use ONLY regex literals here. A previous version built the
            # pattern with new RegExp('...\\s...') -- in a JS *string* literal
            # \\s collapses to "s", so the pattern silently never matched and the
            # adapter fell through to the delivery price.
            return pw.evaluate(r"""(args) => {
              const label  = args.label;
              const scopes = args.scopes || [];
              const money  = /£\s?([0-9]{1,4}(?:\.[0-9]{2})?)/;
              const lower  = label.toLowerCase();
              const has = (el) =>
                !!el && (el.textContent || '').toLowerCase().includes(lower);

              // 1. an explicit per-seller container, if one matches and carries
              //    the label
              let root = null, how = '';
              for (const s of scopes) {
                let el = null;
                try { el = document.querySelector(s); } catch (e) { el = null; }
                if (has(el)) { root = el; how = 'scope'; break; }
              }
              // 2. otherwise the smallest ancestor of the page's <h1> that also
              //    contains the label -- i.e. the main product block. Semantic,
              //    so it survives restyles and works on sites we haven't tuned.
              if (!root) {
                const h = document.querySelector('h1, [itemprop="name"]');
                let el = h ? h.parentElement : null;
                for (let i = 0; el && i < 10; i++, el = el.parentElement) {
                  if (has(el)) { root = el; how = 'product-block'; break; }
                }
              }
              // 3. last resort: the whole page (what we used to always do)
              if (!root) { root = document.body; how = 'page'; }

              let best = null, bestLen = Infinity;
              const els = [root].concat(Array.from(root.querySelectorAll('*')));
              for (const el of els) {
                const t = (el.textContent || '').replace(/\s+/g, ' ');
                if (!t || t.length > 400) continue;
                const i = t.toLowerCase().indexOf(lower);
                if (i < 0) continue;
                const after = t.slice(i + label.length, i + label.length + 24);
                const m = money.exec(after);
                if (m && t.length < bestLen) { bestLen = t.length; best = m[1]; }
              }
              return best === null ? null : { value: best, scope: how };
            }""", {"label": label, "scopes": list(scopes)})
        except Exception:
            return None

    def fetch_rendered(url, selector):
        pw = page_holder.get("page")
        if not pw or _out_of_time():
            return None
        try:
            _prepare(pw, url)
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
        ctx.set_default_timeout(20000)     # no browser call waits indefinitely
        page_holder["page"] = ctx.new_page()
        print("Playwright available -- rendered tier enabled\n")
    except Exception:
        print("Playwright unavailable -- static tier only\n")

    targets = load_targets()
    oils_cfg = load_oils()
    if only:
        targets = {k: v for k, v in targets.items() if k.lower() in
                   [o.strip().lower() for o in only.split(",")]}
    if exclude:
        skip = [e.strip().lower() for e in exclude.split(",")]
        targets = {k: v for k, v in targets.items() if k.lower() not in skip}
    if not targets:
        print("no sellers selected"); return 1

    results, failures = [], []
    for seller, v in targets.items():
        cls = ADAPTERS.get(seller)
        if not cls:
            print(f"{seller}: no adapter"); continue
        ad = cls(fetch_html=fetch_html, fetch_rendered=fetch_rendered,
                 fetch_labelled=fetch_labelled, fetch_page_html=fetch_page_html)
        print(seller)
        for sku in v["skus"]:
            page_holder.pop("at", None)   # force navigation for each SKU
            page_holder["started"] = time.monotonic()
            try:
                q = ad.fetch(sku)
            except AdapterError as e:
                failures.append(str(e))
                took = time.monotonic() - page_holder["started"]
                note = "  (SKU time budget spent)" if took > SKU_BUDGET else ""
                print(f"  ✗ {sku['oil']}/{sku['format']}: {e}{note}")
                continue
            if not q.sku_code:
                q.sku_code = ad.capture_sku(sku["url"])
            why = validate(q.price_gbp, band=_band_for(oils_cfg, sku["oil"]))
            flag = "" if not why else f"  [HELD: {why}]"
            results.append({"seller": seller, **sku, **q.dict(), "held": why})
            code = f"  sku={q.sku_code}" if q.sku_code else ""
            print(f"  ✓ {sku['oil']}/{sku['format']}: £{q.price_gbp:.2f}  via {q.method}{code}{flag}")
        print()

    print(f"{len(results)} quote(s), {len(failures)} failure(s)")
    if ctx:
        ctx.close()
    if browser:
        browser.close()
    if write and results:
        _write_observations(results)
    out = os.path.join(ROOT, "data", "adapter_run.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(),
                   "results": results, "failures": failures}, fh, indent=2)
    print(f"wrote {out}")
    return 0


def cmd_diagnose(seller_filter=None, limit=1):
    """Print what a page ACTUALLY contains, so selectors are written from evidence.

    For each SKU: loads the page in a real browser, dismisses cookie banners, waits
    for network idle, then lists every element whose text looks like a GBP price
    along with its tag/class and nearby label. Also reports title, challenge/login
    hints and JSON-LD presence.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright required for --diagnose"); return 1

    UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
    sellers = load_targets()
    if seller_filter:
        sellers = {k: v for k, v in sellers.items()
                   if seller_filter.lower() in k.lower()}
        if not sellers:
            print(f"no seller matching {seller_filter!r}"); return 1

    JS = """() => {
      const out = [];
      const re = /£\\s?\\d{1,4}(?:\\.\\d{2})?/;
      const seen = new Set();
      document.querySelectorAll('body *').forEach(el => {
        // allow small composite nodes (WooCommerce wraps the £ in its own span)
        if (el.children.length > 2) return;
        const t = (el.textContent || '').trim().replace(/\\s+/g, ' ');
        if (!t || t.length > 60 || !re.test(t)) return;
        const path = [];
        let n = el;
        for (let i = 0; i < 3 && n && n.tagName; i++) {
          path.unshift(n.tagName.toLowerCase() +
            (n.className && typeof n.className === 'string'
              ? '.' + n.className.trim().split(/\\s+/).slice(0,3).join('.') : ''));
          n = n.parentElement;
        }
        const key = t + '|' + path.join('>');
        if (seen.has(key)) return;
        seen.add(key);
        // climb for a labelling ancestor -- this is what distinguishes
        // "Collection" from "Delivery" on catering sites
        let label = '';
        let p = el.parentElement;
        for (let i = 0; i < 5 && p; i++) {
          const pt = (p.textContent || '').trim().replace(/\\s+/g, ' ');
          if (pt.length > t.length + 3 && pt.length < 160) { label = pt; break; }
          p = p.parentElement;
        }
        out.push({ text: t, path: path.join(' > '), label });
      });
      return out.slice(0, 40);
    }"""

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-GB",
                                  viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        for seller, v in sellers.items():
            print("=" * 70)
            print(f"  {seller}")
            print("=" * 70)
            for sku in v["skus"][:limit]:
                url = sku["url"]
                print(f"\n--- {sku['oil']}/{sku['format']}\n    {url}")
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    print(f"    http status : {resp.status if resp else '?'}")
                except Exception as e:
                    print(f"    NAVIGATION FAILED: {type(e).__name__}: {e}")
                    continue

                # dismiss cookie / consent banners -- a very common price blocker
                for sel in ["button:has-text('Accept')", "button:has-text('Allow all')",
                            "button:has-text('I accept')", "#onetrust-accept-btn-handler",
                            "[id*='accept']", "[class*='accept']"]:
                    try:
                        b = page.locator(sel).first
                        if b.count() > 0 and b.is_visible():
                            b.click(timeout=3000)
                            print(f"    dismissed banner via {sel}")
                            break
                    except Exception:
                        pass
                try:
                    page.wait_for_load_state("networkidle", timeout=20000)
                except Exception:
                    pass
                page.wait_for_timeout(2500)

                html = page.content()
                print(f"    title       : {page.title()[:70]}")
                print(f"    html length : {len(html)}")
                low = html.lower()
                for hint, msg in [
                    ("just a moment", "CLOUDFLARE CHALLENGE"),
                    ("checking your browser", "BOT CHALLENGE"),
                    ("access denied", "ACCESS DENIED"),
                    ("log in to see", "LOGIN REQUIRED for price"),
                    ("sign in to view", "LOGIN REQUIRED for price"),
                    ("select a branch", "BRANCH SELECTION REQUIRED"),
                    ("choose your store", "STORE SELECTION REQUIRED"),
                ]:
                    if hint in low:
                        print(f"    !! {msg}")
                print(f"    json-ld     : {'yes' if 'application/ld+json' in low else 'no'}")

                try:
                    hits = page.evaluate(JS)
                except Exception as e:
                    hits = []
                    print(f"    (scan failed: {type(e).__name__})")
                if not hits:
                    print("    NO £ VALUES FOUND ON PAGE")
                else:
                    print(f"    {len(hits)} price-like element(s):")
                    for h in hits:
                        print(f"      {h['text']:<12} | {h['path'][:60]}")
                        if h["label"] and h["label"] != h["text"]:
                            print(f"          context: {h['label'][:66]}")
        ctx.close(); browser.close()
    print("\nUse the paths above to write exact per-seller selectors.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Per-seller price adapters.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--run", action="store_true")
    g.add_argument("--diagnose", metavar="SELLER", nargs="?", const="",
                   help="dump what a seller's page actually contains")
    ap.add_argument("--limit", type=int, default=1,
                    help="SKUs per seller to diagnose (default 1)")
    ap.add_argument("--only", default=None, help="comma-separated sellers to include")
    ap.add_argument("--exclude", default=None, help="comma-separated sellers to skip")
    ap.add_argument("--write", action="store_true",
                    help="append validated quotes to data/observations.csv")
    a = ap.parse_args()
    if a.list:
        return cmd_list()
    if a.selftest:
        return cmd_selftest()
    if a.diagnose is not None:
        return cmd_diagnose(a.diagnose or None, a.limit)
    return cmd_run(a.only, a.exclude, a.write)


if __name__ == "__main__":
    sys.exit(main())
