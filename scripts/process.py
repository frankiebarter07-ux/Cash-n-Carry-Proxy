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

    # group[(oil, channel, date)] = [normalised point, ...]
    groups = defaultdict(list)
    for r in rows:
        oil = r["oil"]
        if oil not in oils_cfg:
            print(f"  ! skipping unknown oil {oil!r}")
            continue
        per_unit, per_tonne = normalise(r, oils_cfg[oil], tonne_kg)
        groups[(oil, r["channel"], r["date"])].append(
            {
                "source": r["source"],
                "product": r["product"],
                "price_per_unit": per_unit,
                "price_per_tonne": per_tonne,
            }
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

    print(f"Processing {len(rows)} observations into {len(groups)} oil/channel/date groups\n")
    for (oil, channel, day), points in sorted(groups.items()):
        kept, excluded = filter_anomalies(points)
        if not kept:  # everything excluded (shouldn't happen with the 2-SD rule) -> keep raw
            kept = points
        agg_unit = statistics.fmean(p["price_per_unit"] for p in kept)
        agg_tonne = statistics.fmean(p["price_per_tonne"] for p in kept)
        out["oils"][oil]["channels"][channel].append(
            {
                "date": day,
                "price_per_unit": round(agg_unit, 2),
                "price_per_tonne": round(agg_tonne, 2),
                "n_obs": len(points),
                "n_used": len(kept),
                "n_excluded": len(excluded),
                "sources": sorted({p["source"] for p in kept}),
                "excluded": [
                    {"source": p["source"], "price_per_tonne": round(p["price_per_tonne"], 2)}
                    for p in excluded
                ],
            }
        )
        flag = f"  [{len(excluded)} excluded]" if excluded else ""
        print(
            f"  {oil:10s} {channel:10s} {day}  "
            f"£{agg_unit:8.2f}/unit  £{agg_tonne:8.2f}/tonne  "
            f"(n={len(kept)}/{len(points)}){flag}"
        )

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
