#!/usr/bin/env python3
"""
Build the cooking-oil price series from raw observations.

Pipeline
--------
1. Read every price observation (one row = one product seen on one site on one day).
   Each row carries only the price for the single standalone pack it is sold in.
2. Standardise every observation to the oil's standard pack (20L drum for most,
   12.5kg block for palm, 5L tin for olive) -> "price per unit".
3. Convert every observation to "price per metric tonne" using the oil's density
   (palm is sold by weight, so per-kg scales straight to per-tonne).
4. For each (oil, channel, date) group, drop cross-site anomalies: any observation
   more than 2 standard deviations from the group mean (measured in £/tonne, the
   common comparable unit). Only applied when a group has >= 3 points.
5. Aggregate the survivors (mean) into one point per oil/channel/date and write
   data/series.js (for the dashboard) and data/series.json.

Pure standard library -- no third-party dependencies.
"""

import csv
import json
import os
import statistics
from collections import defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "oils.json")
OBS_PATH = os.path.join(ROOT, "data", "observations.csv")
JSON_OUT = os.path.join(ROOT, "data", "series.json")
JS_OUT = os.path.join(ROOT, "data", "series.js")

STD_DEV_THRESHOLD = 2.0  # exclude observations beyond this many SDs from the mean


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_observations():
    with open(OBS_PATH, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["pack_value"] = float(r["pack_value"])
        r["price_gbp"] = float(r["price_gbp"])
    return rows


def normalise(row, oil_cfg, tonne_kg):
    """Return (price_per_unit, price_per_tonne) for a single observation."""
    basis = oil_cfg["basis"]
    pack = oil_cfg["standard_pack"]
    price = row["price_gbp"]

    if basis == "volume":
        # price per litre of the product as sold
        per_litre = price / row["pack_value"]
        per_unit = per_litre * pack["value"]            # £ for the standard drum/tin
        density = oil_cfg["density_kg_per_l"]
        per_tonne = per_litre / density * tonne_kg       # £/L -> £/kg -> £/tonne
    elif basis == "mass":
        per_kg = price / row["pack_value"]
        per_unit = per_kg * pack["value"]                # £ for the standard block
        per_tonne = per_kg * tonne_kg
    else:
        raise ValueError(f"unknown basis {basis!r}")
    return per_unit, per_tonne


def collapse_by_source(points):
    """Average a seller's products into one seller-level price (equal weight per
    seller), so a shop listing 4 rapeseed SKUs counts as one seller, not four."""
    by = defaultdict(list)
    for p in points:
        by[p["source"]].append(p)
    sellers = []
    for src, ps in by.items():
        sellers.append({
            "source": src,
            "price_per_unit": statistics.fmean(x["price_per_unit"] for x in ps),
            "price_per_tonne": statistics.fmean(x["price_per_tonne"] for x in ps),
            "n_products": len(ps),
        })
    return sellers


def filter_anomalies(points):
    """Split points into (kept, excluded) using the 2-SD rule on £/tonne."""
    if len(points) < 3:
        return points, []
    tonnes = [p["price_per_tonne"] for p in points]
    mean = statistics.fmean(tonnes)
    sd = statistics.stdev(tonnes)  # sample standard deviation
    if sd == 0:
        return points, []
    kept, excluded = [], []
    for p in points:
        if abs(p["price_per_tonne"] - mean) > STD_DEV_THRESHOLD * sd:
            excluded.append(p)
        else:
            kept.append(p)
    return kept, excluded


def build():
    config = load_config()
    tonne_kg = config["metric_tonne_kg"]
    oils_cfg = config["oils"]
    rows = load_observations()

    # panel[(oil, channel)][source][date] = [normalised product point, ...]
    panel = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        oil = r["oil"]
        if oil not in oils_cfg:
            print(f"  ! skipping unknown oil {oil!r}")
            continue
        # Enforce one pack size per oil: every observation for an oil must be at that
        # oil's standard pack (e.g. sunflower is 20L only, never 5L + 20L mixed).
        pack = oils_cfg[oil]["standard_pack"]
        if r["pack_value"] != pack["value"] or r["pack_unit"] != pack["unit"]:
            print(f"  ! {oil} {r['source']}: pack {r['pack_value']}{r['pack_unit']} "
                  f"!= standard {pack['value']}{pack['unit']} -- skipped (size mismatch)")
            continue
        per_unit, per_tonne = normalise(r, oils_cfg[oil], tonne_kg)
        panel[(oil, r["channel"])][r["source"]][r["date"]].append(
            {"price_per_unit": per_unit, "price_per_tonne": per_tonne}
        )

    out = {
        "generated": date.today().isoformat(),
        "metric_tonne_kg": tonne_kg,
        "std_dev_threshold": STD_DEV_THRESHOLD,
        "raw_count": len(rows),
        "oils": {},
    }

    for oil, cfg in oils_cfg.items():
        out["oils"][oil] = {
            "label": cfg["label"],
            "color": cfg["color"],
            "basis": cfg["basis"],
            "standard_pack": cfg["standard_pack"],
            "notes": cfg.get("notes", ""),
            "channels": defaultdict(list),
        }

    print(f"Processing {len(rows)} observations (last price carried forward per seller)\n")
    for (oil, channel), sources in sorted(panel.items()):
        # stage 1: one price per seller per date (average that seller's products)
        seller_series, all_dates = {}, set()
        for source, datemap in sources.items():
            series = []
            for d, pts in datemap.items():
                series.append((d,
                               statistics.fmean(p["price_per_unit"] for p in pts),
                               statistics.fmean(p["price_per_tonne"] for p in pts)))
                all_dates.add(d)
            seller_series[source] = sorted(series)

        for day in sorted(all_dates):
            # LOCF: each seller's most recent price on or before `day` (keeps the
            # seller set comparable when only some sellers report on a given day)
            sellers = []
            for source, series in seller_series.items():
                latest = None
                for entry in series:
                    if entry[0] <= day:
                        latest = entry
                    else:
                        break
                if latest is not None:
                    sellers.append({"source": source,
                                    "price_per_unit": latest[1],
                                    "price_per_tonne": latest[2],
                                    "stale": latest[0] != day})
            kept, excluded = filter_anomalies(sellers)   # stage 2: drop cross-seller outliers
            if not kept:
                kept = sellers
            agg_unit = statistics.fmean(s["price_per_unit"] for s in kept)
            agg_tonne = statistics.fmean(s["price_per_tonne"] for s in kept)
            n_fresh = sum(1 for s in kept if not s["stale"])
            out["oils"][oil]["channels"][channel].append(
                {
                    "date": day,
                    "price_per_unit": round(agg_unit, 2),
                    "price_per_tonne": round(agg_tonne, 2),
                    "n_obs": len(sellers),
                    "n_used": len(kept),
                    "n_excluded": len(excluded),
                    "n_fresh": n_fresh,          # sellers that actually reported this day
                    "sources": sorted(s["source"] for s in kept),
                    "excluded": [
                        {"source": s["source"], "price_per_tonne": round(s["price_per_tonne"], 2)}
                        for s in excluded
                    ],
                }
            )
            flag = f"  [{len(excluded)} excl]" if excluded else ""
            cf = f", {len(kept) - n_fresh} carried" if n_fresh < len(kept) else ""
            print(f"  {oil:12s} {channel:10s} {day}  £{agg_unit:8.2f}/unit  "
                  f"£{agg_tonne:8.2f}/tonne  (sellers={len(kept)}{cf}){flag}")

    # sort each channel by date and drop empty channels
    for oil in out["oils"].values():
        oil["channels"] = {
            ch: sorted(pts, key=lambda p: p["date"])
            for ch, pts in oil["channels"].items()
            if pts
        }

    with open(JSON_OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(JS_OUT, "w", encoding="utf-8") as fh:
        fh.write("// Auto-generated by scripts/process.py -- do not edit by hand.\n")
        fh.write("window.OIL_SERIES = ")
        json.dump(out, fh, indent=2)
        fh.write(";\n")

    print(f"\nWrote {JSON_OUT}")
    print(f"Wrote {JS_OUT}")


if __name__ == "__main__":
    build()
