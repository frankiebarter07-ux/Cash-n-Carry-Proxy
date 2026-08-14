#!/usr/bin/env python3
"""
Build the cooking-oil price series from raw observations.

Pipeline
--------
1. Read every price observation (one row = one product seen on one site on one day).
   Each row carries only the price for the single standalone pack it is sold in.
2. Standardise every observation to the oil's standard pack (20L for both oils
   currently tracked) -> "price per unit".
3. Convert every observation to "price per metric tonne" using the oil's density.
   An oil whose config sets "basis": "mass" is sold by weight instead, so its per-kg
   price scales straight to per-tonne with no density involved.
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
# Warn (never exclude) when a seller sits this far from the median, in %. The 2-SD
# filter goes blind to a single gross outlier at small n -- see flag_suspect().
MEDIAN_WARN_PCT = 40.0

# How long a seller's last known price may be carried forward before that seller
# stops counting towards the index.
#
# Carry-forward exists so the index moves only on real price changes, not on a
# seller being briefly unreadable. But carried indefinitely it becomes a lie: a
# permanently blocked seller would sit frozen at its final price and still pull the
# average, making "we have no data" look identical to "the price did not move".
# After this many days a seller lapses -- it still appears in the SKU breakdown,
# marked as no longer reporting, but it no longer counts towards the aggregate.
MAX_CARRY_DAYS = 7


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


def flag_suspect(points):
    """Mark sellers sitting absurdly far from the median. Returns the flagged ones.

    This does NOT change the aggregate -- it only raises a hand. The 2-SD filter
    above cannot be relied on to catch a badly mismatched product at the three-to-
    five sellers this index has: one extreme value inflates the standard deviation
    faster than it inflates its own deviation from the mean, so it masks itself and
    passes. Measured on the palm series, a seller £20 clear of the other three
    survived the filter and would have moved the index ~20% while reporting nothing
    excluded (ARCHITECTURE.md section 3).

    The median is used precisely because it does not move when one value is wild,
    so the comparison stays stable however bad the outlier is. A price this far out
    almost always means the SKU is not like-for-like -- a case rather than a single
    unit, or a different pack -- which is a config question, not a maths one.
    """
    if len(points) < 3:
        return []
    med = statistics.median(p["price_per_tonne"] for p in points)
    if med <= 0:
        return []
    flagged = []
    for p in points:
        dev = abs(p["price_per_tonne"] - med) / med * 100
        if dev > MEDIAN_WARN_PCT:
            p["suspect_pct"] = round(dev, 1)
            flagged.append(p)
    return flagged


def compute_changes(rows):
    """Per-SKU price movements: what changed on the latest date, and a 7-day summary.

    Works off the raw observations (one row per SKU per date), so a change is only
    reported when that exact SKU's listed price actually differs from its previous
    observation -- never from a seller simply not reporting.
    """
    from datetime import datetime, timedelta

    by_sku = defaultdict(list)                       # (source, product) -> [(date, price)]
    for r in rows:
        by_sku[(r["source"], r["product"])].append(
            (r["date"], float(r["price_gbp"]), r.get("oil", ""), r.get("brand", ""),
             r.get("format", "")))
    all_dates = sorted({r["date"] for r in rows})
    if not all_dates:
        return {"latest_date": None, "today": [], "week": [], "week_from": None}
    latest = all_dates[-1]
    week_from = (datetime.fromisoformat(latest) - timedelta(days=7)).date().isoformat()

    today_moves, week_moves = [], []
    for (source, product), series in by_sku.items():
        series.sort(key=lambda e: e[0])
        oil, brand, fmt = series[-1][2], series[-1][3], series[-1][4]
        # movement on the latest date vs the SKU's previous observation
        if len(series) >= 2 and series[-1][0] == latest:
            prev_d, prev_p = series[-2][0], series[-2][1]
            cur_p = series[-1][1]
            if abs(cur_p - prev_p) >= 0.01:
                today_moves.append({
                    "source": source, "product": product, "oil": oil,
                    "brand": brand, "format": fmt,
                    "from": round(prev_p, 2), "to": round(cur_p, 2),
                    "delta": round(cur_p - prev_p, 2),
                    "pct": round((cur_p - prev_p) / prev_p * 100, 2),
                    "since": prev_d,
                })
        # movement across the trailing 7 days
        window = [e for e in series if e[0] >= week_from]
        if len(window) >= 2 and abs(window[-1][1] - window[0][1]) >= 0.01:
            first, last = window[0][1], window[-1][1]
            week_moves.append({
                "source": source, "product": product, "oil": oil,
                "brand": brand, "format": fmt,
                "from": round(first, 2), "to": round(last, 2),
                "delta": round(last - first, 2),
                "pct": round((last - first) / first * 100, 2),
                "n_obs": len(window),
            })

    today_moves.sort(key=lambda m: -abs(m["delta"]))
    week_moves.sort(key=lambda m: -abs(m["delta"]))

    def summarise(moves):
        if not moves:
            return {}
        out = {}
        for oil in {m["oil"] for m in moves}:
            ms = [m for m in moves if m["oil"] == oil]
            out[oil] = {
                "n_skus_changed": len(ms),
                "avg_delta": round(statistics.fmean(m["delta"] for m in ms), 2),
                "avg_pct": round(statistics.fmean(m["pct"] for m in ms), 2),
                "n_up": sum(1 for m in ms if m["delta"] > 0),
                "n_down": sum(1 for m in ms if m["delta"] < 0),
                "movers": sorted({m["source"] for m in ms}),
            }
        return out

    return {
        "latest_date": latest,
        "week_from": week_from,
        "today": today_moves,
        "week": week_moves,
        "today_summary": summarise(today_moves),
        "week_summary": summarise(week_moves),
    }


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
        # oil's standard pack, never a mix of 5L and 20L, or the average is meaningless.
        pack = oils_cfg[oil]["standard_pack"]
        if r["pack_value"] != pack["value"] or r["pack_unit"] != pack["unit"]:
            print(f"  ! {oil} {r['source']}: pack {r['pack_value']}{r['pack_unit']} "
                  f"!= standard {pack['value']}{pack['unit']} -- skipped (size mismatch)")
            continue
        per_unit, per_tonne = normalise(r, oils_cfg[oil], tonne_kg)
        panel[(oil, r["channel"])][r["source"]][r["date"]].append(
            {"product": r["product"], "format": r.get("format", ""),
             "brand": r.get("brand", ""), "url": r.get("url", ""),
             "price_per_unit": per_unit, "price_per_tonne": per_tonne}
        )

    out = {
        "generated": date.today().isoformat(),
        "metric_tonne_kg": tonne_kg,
        "std_dev_threshold": STD_DEV_THRESHOLD,
        "raw_count": len(rows),
        "changes": compute_changes(rows),
        "oils": {},
    }

    for oil, cfg in oils_cfg.items():
        out["oils"][oil] = {
            "label": cfg["label"],
            "color": cfg["color"],
            "basis": cfg["basis"],
            "standard_pack": cfg["standard_pack"],
            # How the dashboards should draw it. An oil in a different pack does
            # not share the others' price range, so it can ask for its own axis.
            "chart": cfg.get("chart", {}),
            "notes": cfg.get("notes", ""),
            "channels": defaultdict(list),
        }

    warnings = []
    print(f"Processing {len(rows)} observations (last price carried forward per seller)\n")
    for (oil, channel), sources in sorted(panel.items()):
        # stage 1: one price per seller per date (average that seller's products)
        seller_series, all_dates = {}, set()
        for source, datemap in sources.items():
            series = []
            for d, pts in datemap.items():
                series.append((d,
                               statistics.fmean(p["price_per_unit"] for p in pts),
                               statistics.fmean(p["price_per_tonne"] for p in pts),
                               list(pts)))          # keep the SKUs for the breakdown
                all_dates.add(d)
            seller_series[source] = sorted(series, key=lambda e: e[0])

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
                    age = (date.fromisoformat(day) - date.fromisoformat(latest[0])).days
                    sellers.append({"source": source,
                                    "as_of": latest[0],
                                    "price_per_unit": latest[1],
                                    "price_per_tonne": latest[2],
                                    "products": latest[3],
                                    "stale": latest[0] != day,
                                    "age_days": age,
                                    "lapsed": age > MAX_CARRY_DAYS})
            # a seller that has gone quiet for too long stops counting (see MAX_CARRY_DAYS)
            reporting = [s for s in sellers if not s["lapsed"]]
            lapsed = [s for s in sellers if s["lapsed"]]
            kept, excluded = filter_anomalies(reporting)  # stage 2: drop cross-seller outliers
            if not kept:
                kept = reporting or sellers
            agg_unit = statistics.fmean(s["price_per_unit"] for s in kept)
            agg_tonne = statistics.fmean(s["price_per_tonne"] for s in kept)
            n_fresh = sum(1 for s in kept if not s["stale"])
            # Raise a hand at anything wildly off the median. Advisory only: it does
            # not touch the aggregate, because whether such a SKU belongs in the
            # index at all is a question about the product, not about the numbers.
            suspects = flag_suspect(reporting)
            for s in suspects:
                warnings.append(
                    f"{date}  {oil}/{channel}: {s['source']} is {s['suspect_pct']:.0f}% "
                    f"from the median (£{s['price_per_tonne']:.0f}/t vs the group). "
                    f"Check the SKU is like-for-like -- a case price or a different "
                    f"pack looks exactly like this."
                )
            suspect_sources = {s["source"] for s in suspects}
            # full per-SKU-per-website breakdown behind the aggregate (sorted cheapest first)
            excluded_sources = {s["source"] for s in excluded}
            breakdown = sorted(
                ({
                    "source": s["source"],
                    "product": pr["product"],
                    "brand": pr.get("brand", ""),
                    "format": pr.get("format", ""),
                    "price_per_unit": round(pr["price_per_unit"], 2),
                    "price_per_tonne": round(pr["price_per_tonne"], 2),
                    "as_of": s["as_of"],
                    "stale": s["stale"],
                    "age_days": s["age_days"],
                    "lapsed": s["lapsed"],
                    "excluded": s["source"] in excluded_sources,
                    "suspect": s["source"] in suspect_sources,
                } for s in sellers for pr in s["products"]),
                key=lambda x: (x["source"], x["format"], x["brand"]),
            )
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
                    "lapsed": [                  # stopped reporting; no longer counted
                        {"source": s["source"], "last_seen": s["as_of"],
                         "days_ago": s["age_days"]}
                        for s in sorted(lapsed, key=lambda x: x["source"])
                    ],
                    "excluded": [
                        {"source": s["source"], "price_per_tonne": round(s["price_per_tonne"], 2)}
                        for s in excluded
                    ],
                    "breakdown": breakdown,      # every SKU at every website behind the mean
                }
            )
            flag = f"  [{len(excluded)} excl]" if excluded else ""
            cf = f", {len(kept) - n_fresh} carried" if n_fresh < len(kept) else ""
            lap = (f"  [LAPSED: {', '.join(s['source'] for s in lapsed)}]"
                   if lapsed else "")
            print(f"  {oil:12s} {channel:10s} {day}  £{agg_unit:8.2f}/unit  "
                  f"£{agg_tonne:8.2f}/tonne  (sellers={len(kept)}{cf}){flag}{lap}")

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

    # Last, and unmissable. A warning printed halfway up a 200-line log is a
    # warning nobody reads.
    if warnings:
        print("\n" + "!" * 78)
        print(f"{len(warnings)} PRICE(S) FAR FROM THE GROUP -- CHECK THE PRODUCT, NOT THE MATHS")
        print("!" * 78)
        for w in warnings:
            print(f"  {w}")
        print("\n  These are still IN the index. The 2-SD filter does not catch a")
        print("  single gross outlier at this many sellers, so this is the only")
        print("  notice you get. If a SKU is not like-for-like, remove it from")
        print("  config/targets.json -- see ARCHITECTURE.md section 3.")


def selftest():
    """Offline checks for the two cross-seller guards. No network, no files.

    These exist because both guards are silent when working. If flag_suspect()
    quietly stopped firing, nothing in a green daily run would reveal it, and the
    thing it protects against -- a mismatched SKU dragging the index -- is exactly
    the kind of error that goes unnoticed for months.
    """
    def pts(**kw):
        return [{"source": s, "price_per_tonne": v} for s, v in kw.items()]

    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        ok = ok and cond

    print("cross-seller guards")
    # The case this was built for: 2-SD misses it, the median warning does not.
    brakes = pts(JJ=1743, Marfast=2131, Magna=1946, Brakes=3600)
    _, excl = filter_anomalies([dict(p) for p in brakes])
    flagged = flag_suspect([dict(p) for p in brakes])
    check("2-SD filter misses a lone gross outlier (the reason this exists)", not excl)
    check("median warning catches it", [f["source"] for f in flagged] == ["Brakes"])
    check("and reports how far out it is", flagged[0]["suspect_pct"] > 40)

    check("quiet on a normal spread",
          not flag_suspect(pts(A=1850, B=1950, C=2100, D=2200)))
    check("quiet on today's live palm figures",
          not flag_suspect(pts(JJ=1743, Marfast=2131, Magna=1946)))
    check("off below 3 sellers, like the 2-SD filter",
          not flag_suspect(pts(A=1900, B=3900)))
    check("survives a zero median without dividing by it",
          flag_suspect(pts(A=0, B=0, C=0)) == [])

    print("\nSELFTEST PASSED" if ok else "\nSELFTEST FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(selftest() if "--selftest" in sys.argv else (build() or 0))
