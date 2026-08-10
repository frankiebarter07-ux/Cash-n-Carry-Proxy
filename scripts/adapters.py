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

    # When True, read the displayed (rendered) price first. Needed where the
    # static/JSON-LD figure is not the collection price we track.
    prefer_rendered = False

    def fetch(self, sku: dict) -> Quote:
        url = sku["url"]
        order = ((self.from_rendered, self.from_static) if self.prefer_rendered
                 else (self.from_static, self.from_rendered))
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
    selectors = ["p.price ins .woocommerce-Price-amount",
                 "p.price .woocommerce-Price-amount",
                 ".summary .woocommerce-Price-amount",
                 "[class*='woocommerce-Price-amount']"]


class MarfastAdapter(BaseAdapter):
    """Magento.

    Diagnostics showed the page renders TWO prices with an identical class path
    (£34.29 and £32.79). meta[itemprop=price] returns the higher one; the
    collection price we track is the lower. Selectors below target the
    collection block; the next diagnose run confirms the distinguishing label.
    """
    name = "Marfast"
    prefer_rendered = True
    selectors = ["[class*='collection'] .price-wrapper .price",
                 "[data-price-type='finalPrice'] .price",
                 ".price-container.price-final_price .price-wrap"]


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

    def _prepare(pw, url):
        """Navigate, dismiss consent banners, wait for the price to actually load."""
        if page_holder.get("at") == url:
            return True
        pw.goto(url, wait_until="domcontentloaded", timeout=45000)
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

    def fetch_rendered(url, selector):
        pw = page_holder.get("page")
        if not pw:
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
            page_holder.pop("at", None)   # force navigation for each SKU
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
    a = ap.parse_args()
    if a.list:
        return cmd_list()
    if a.selftest:
        return cmd_selftest()
    if a.diagnose is not None:
        return cmd_diagnose(a.diagnose or None, a.limit)
    return cmd_run()


if __name__ == "__main__":
    sys.exit(main())
