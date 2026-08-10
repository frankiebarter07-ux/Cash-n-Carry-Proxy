#!/usr/bin/env python3
"""
Append a new price observation and rebuild the series.

Usage:
  python3 scripts/add_observation.py \
      --oil sunflower --channel cash_carry \
      --source "Bestway" --product "White Pearl Sunflower 20L" \
      --url "https://www.bestwaywholesale.co.uk/..." \
      --pack 20 --unit L --price 41.50 \
      [--date 2026-08-01] [--note "collection price"]

Valid oils come from config/oils.json. Channel is cash_carry or retail.
Enter the price for the single standalone pack exactly as the site lists it
(e.g. the price of one 20L drum). The £/tonne maths is done for you by process.py.
After appending, this script runs process.py so data/series.js is refreshed.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBS_PATH = os.path.join(ROOT, "data", "observations.csv")
CONFIG_PATH = os.path.join(ROOT, "config", "oils.json")
FIELDS = ["date", "oil", "format", "channel", "source", "product", "url",
          "pack_value", "pack_unit", "price_gbp", "notes"]


def main():
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        oils = set(json.load(fh)["oils"])

    ap = argparse.ArgumentParser(description="Add a cooking-oil price observation.")
    ap.add_argument("--oil", required=True, choices=sorted(oils))
    ap.add_argument("--channel", required=True, choices=["cash_carry", "retail"])
    ap.add_argument("--format", default="", choices=["", "bib", "drum"],
                    help="pack format: bag-in-box or drum")
    ap.add_argument("--source", required=True, help="Website / retailer name")
    ap.add_argument("--product", required=True, help="Product name as listed")
    ap.add_argument("--url", required=True)
    ap.add_argument("--pack", required=True, type=float, help="Pack size value, e.g. 20")
    ap.add_argument("--unit", required=True, choices=["L", "kg"], help="Pack size unit")
    ap.add_argument("--price", required=True, type=float, help="Price of ONE pack in GBP")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    row = {
        "date": args.date, "oil": args.oil, "format": args.format,
        "channel": args.channel,
        "source": args.source, "product": args.product, "url": args.url,
        "pack_value": args.pack, "pack_unit": args.unit,
        "price_gbp": args.price, "notes": args.note,
    }

    write_header = not os.path.exists(OBS_PATH) or os.path.getsize(OBS_PATH) == 0
    with open(OBS_PATH, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        w.writerow(row)
    print(f"Appended: {args.oil} / {args.channel} / {args.source} "
          f"@ £{args.price} per {args.pack}{args.unit} ({args.date})")

    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "process.py")], check=True)


if __name__ == "__main__":
    main()
