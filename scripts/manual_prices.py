#!/usr/bin/env python3
"""
Record prices for a seller by hand, using config/targets.json for the SKU details.

For sellers that cannot be collected automatically -- e.g. Booker, which blocks
datacenter IPs at its CDN edge (HTTP 403 "Access Denied") so CI can never read it.
A human reads the prices in a normal browser and enters them here.

Usage:
    python3 scripts/manual_prices.py --seller Booker \\
        --price "soybean/bib=30.69" --price "soybean/drum=30.69" \\
        --price "rapeseed/bib=33.99" --price "rapeseed/drum=33.99"

    # or one flag, comma-separated:
    python3 scripts/manual_prices.py --seller Booker \\
        --prices "soybean/bib=30.69,soybean/drum=30.69,rapeseed/bib=33.99,rapeseed/drum=33.99"

Keys are "<oil>/<format>" exactly as they appear in config/targets.json.
Blank or zero values are skipped, so you can submit a partial update.
Rows are written with note "manual (browser-verified)" so provenance stays clear.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = os.path.join(ROOT, "config", "targets.json")
OBS = os.path.join(ROOT, "data", "observations.csv")
OILS = os.path.join(ROOT, "config", "oils.json")
FIELDS = ["date", "oil", "brand", "format", "channel", "source", "product", "url",
          "sku", "pack_value", "pack_unit", "price_gbp", "notes"]

def pack_for(oil):
    """The oil's pack, from config -- not every oil is a 20 L drum any more."""
    with open(OILS, encoding="utf-8") as fh:
        cfg = json.load(fh)["oils"]
    p = (cfg.get(oil) or {}).get("standard_pack") or {"value": 20, "unit": "L"}
    return p["value"], p["unit"]


def sku_from_url(url):
    """Booker and JJ put the seller's product code in the URL."""
    for pat in (r"[?&]Code=(\d+)", r"/product/[^/]+/([A-Z]{2,}\d+)/?"):
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return ""


# Brand rules are NOT duplicated here. Two copies drifted apart is exactly how a
# hand-entered row ends up classified differently from a fetched one, so this
# imports the collector's. adapters.py is stdlib-only at import time (Playwright
# is loaded lazily inside the fetch functions), so this costs nothing.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapters import brand_for as brand_of  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Manually record a seller's prices.")
    ap.add_argument("--seller", required=True, help="e.g. Booker")
    ap.add_argument("--price", action="append", default=[],
                    help='one "oil/format=price", repeatable')
    ap.add_argument("--prices", default="",
                    help='comma-separated "oil/format=price,..."')
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--note", default="manual (browser-verified)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    with open(TARGETS, encoding="utf-8") as fh:
        sellers = json.load(fh)["sellers"]
    match = [s for s in sellers if a.seller.lower() in s.lower()]
    if len(match) != 1:
        print(f"seller {a.seller!r} matched {match or 'nothing'}; "
              f"choose one of: {', '.join(sellers)}")
        return 1
    seller = match[0]
    skus = {f"{k['oil']}/{k['format']}": k for k in sellers[seller]["skus"]}

    raw = list(a.price)
    if a.prices:
        raw += [p for p in a.prices.split(",") if p.strip()]
    if not raw:
        print("no prices given. Available SKU keys for this seller:")
        for k in skus:
            print(f"   {k}")
        return 1

    rows, skipped = [], []
    for item in raw:
        if "=" not in item:
            print(f"  ! ignoring {item!r} (expected oil/format=price)")
            continue
        key, val = (x.strip() for x in item.split("=", 1))
        if key not in skus:
            print(f"  ! unknown SKU key {key!r} for {seller}; valid: {', '.join(skus)}")
            return 1
        val = val.replace("£", "").strip()
        if not val or val in ("0", "0.0", "0.00"):
            skipped.append(key)
            continue
        try:
            price = round(float(val), 2)
        except ValueError:
            print(f"  ! {key}: {val!r} is not a number")
            return 1
        if not (1 <= price < 1000):
            print(f"  ! {key}: £{price} is outside a sane range")
            return 1
        sku = skus[key]
        pack = pack_for(sku["oil"])
        rows.append({
            "date": a.date, "oil": sku["oil"], "brand": brand_of(sku["product"]),
            "format": sku["format"], "channel": "cash_carry", "source": seller,
            "product": sku["product"], "url": sku["url"],
            # Pack and SKU come from the same places the automatic collector uses,
            # so a hand-entered row is indistinguishable from a fetched one.
            "sku": sku_from_url(sku["url"]),
            "pack_value": pack[0], "pack_unit": pack[1],
            "price_gbp": f"{price:.2f}", "notes": a.note,
        })

    if skipped:
        print(f"skipped (blank/zero): {', '.join(skipped)}")
    if not rows:
        print("nothing to write.")
        return 0

    # replace any existing rows for this seller+date, so re-submitting corrects
    existing = []
    if os.path.exists(OBS):
        with open(OBS, encoding="utf-8") as fh:
            existing = list(csv.DictReader(fh))
    keep = [r for r in existing
            if not (r["source"] == seller and r["date"] == a.date)]
    replaced = len(existing) - len(keep)

    for r in rows:
        print(f"  + {r['source']} {r['oil']}/{r['format']}  £{r['price_gbp']}")
    if replaced:
        print(f"  (replacing {replaced} existing row(s) for {seller} on {a.date})")

    if a.dry_run:
        print("dry run -- nothing written.")
        return 0

    out = keep + rows
    out.sort(key=lambda r: (r["date"], r["oil"], r["source"], r["format"]))
    with open(OBS, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    print(f"\nwrote {len(rows)} row(s) to {OBS}")
    print("Now run: python3 scripts/process.py && python3 scripts/render_static.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
