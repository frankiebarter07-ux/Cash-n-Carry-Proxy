#!/usr/bin/env python3
"""
Render a fully static (NO JavaScript) dashboard from data/series.json.

Why: some embedded HTML viewers (e.g. the Claude mobile app's preview) strip
<script> tags, so the interactive index.html shows blank. This writes
dashboard_static.html — an inline-SVG chart + table that renders anywhere,
including those viewers. It's theme-aware via CSS only (no JS).

Run after process.py:  python3 scripts/render_static.py
"""

import json
import os
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERIES = os.path.join(ROOT, "data", "series.json")
OUT = os.path.join(ROOT, "dashboard_static.html")

VW, VH = 1000, 440
PAD = {"l": 88, "r": 30, "t": 20, "b": 48}
PW, PH = VW - PAD["l"] - PAD["r"], VH - PAD["t"] - PAD["b"]
DAY = timedelta(days=1)


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def money(v):
    return "£" + (f"{v:,.2f}" if v < 100 else f"{v:,.0f}")


def build_chart(oils, metric):
    """Return an inline SVG string for the given metric across all oils (cash_carry)."""
    lines = []  # (color, label, [(t, v), ...])
    for key, o in oils.items():
        pts = (o.get("channels", {}) or {}).get("cash_carry", [])
        if not pts:
            continue
        series = [(datetime.fromisoformat(p["date"]), p[metric]) for p in pts]
        if len(series) == 1:  # flat line back one day so it's visible
            t, v = series[0]
            series = [(t - DAY, v), (t, v)]
        lines.append((o["color"], o["label"], series))
    if not lines:
        return "<p>No data.</p>"

    vals = [v for _, _, s in lines for _, v in s]
    times = [t for _, _, s in lines for t, _ in s]
    vmin, vmax = min(vals), max(vals)
    if vmin == vmax:
        vmin, vmax = vmin * 0.9, vmax * 1.1
    vpad = (vmax - vmin) * 0.12
    vmin, vmax = max(0, vmin - vpad), vmax + vpad
    tmin, tmax = min(times), max(times)
    if tmin == tmax:
        tmin, tmax = tmin - DAY, tmax + DAY
    span = (tmax - tmin).total_seconds() or 1

    def X(t):
        return PAD["l"] + PW * (t - tmin).total_seconds() / span

    def Y(v):
        return PAD["t"] + PH * (1 - (v - vmin) / (vmax - vmin))

    svg = [f'<svg viewBox="0 0 {VW} {VH}" preserveAspectRatio="xMidYMid meet" '
           f'xmlns="http://www.w3.org/2000/svg" role="img">']
    # y grid + labels
    for i in range(6):
        v = vmin + (vmax - vmin) * i / 5
        y = round(Y(v), 1)
        svg.append(f'<line class="grid" x1="{PAD["l"]}" y1="{y}" x2="{VW-PAD["r"]}" y2="{y}"/>')
        svg.append(f'<text class="ax" x="{PAD["l"]-10}" y="{y}" text-anchor="end" '
                   f'dominant-baseline="middle">{esc(money(v))}</text>')
    # x labels
    for t in sorted(set(times)):
        svg.append(f'<text class="ax" x="{round(X(t),1)}" y="{VH-PAD["b"]+22}" '
                   f'text-anchor="middle">{t.strftime("%d %b %y")}</text>')
    # caption
    cy = PAD["t"] + PH / 2
    cap = "£ per standard unit" if metric == "price_per_unit" else "£ per metric tonne"
    svg.append(f'<text class="ax" x="20" y="{cy}" text-anchor="middle" '
               f'transform="rotate(-90 20 {cy})">{cap}</text>')
    # series
    for color, label, series in lines:
        pts = " ".join(f"{round(X(t),1)},{round(Y(v),1)}" for t, v in series)
        svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" '
                   f'stroke-width="2.6" stroke-linejoin="round"/>')
        t, v = series[-1]
        svg.append(f'<circle class="mk" cx="{round(X(t),1)}" cy="{round(Y(v),1)}" '
                   f'r="5.5" fill="{color}"/>')
    svg.append("</svg>")
    return "\n".join(svg)


def build():
    with open(SERIES, encoding="utf-8") as fh:
        data = json.load(fh)
    oils = data["oils"]

    legend = "".join(
        f'<span class="chip"><span class="dot" style="background:{o["color"]}"></span>{esc(o["label"])}</span>'
        for o in oils.values()
        if (o.get("channels", {}) or {}).get("cash_carry")
    )

    rows = ""
    for o in oils.values():
        pts = (o.get("channels", {}) or {}).get("cash_carry", [])
        if not pts:
            continue
        p = pts[-1]
        sp = o["standard_pack"]
        rows += (f'<tr><td><span class="dot" style="background:{o["color"]}"></span>{esc(o["label"])}</td>'
                 f'<td>{sp["value"]} {sp["unit"]}</td>'
                 f'<td>{esc(money(p["price_per_unit"]))}</td>'
                 f'<td>{esc(money(p["price_per_tonne"]))}</td>'
                 f'<td>{p["n_used"]}</td></tr>')

    chart = build_chart(oils, "price_per_unit")

    # Full per-SKU-per-website breakdown behind each aggregate line (latest date).
    bd_sections = ""
    for o in oils.values():
        pts = (o.get("channels", {}) or {}).get("cash_carry", [])
        if not pts:
            continue
        p = pts[-1]
        rows_b = ""
        for b in p.get("breakdown", []):
            flags = []
            if b.get("stale"):
                flags.append(f"carried from {b['as_of'][5:]}")
            if b.get("excluded"):
                flags.append("outlier — excluded")
            if b.get("lapsed"):
                flags.append(f"stopped reporting {b['age_days']}d ago — not counted")
            fl = f' <span class="flag">({" · ".join(flags)})</span>' if flags else ""
            rows_b += (f'<tr><td>{esc(b["source"])}</td>'
                       f'<td>{esc(b.get("brand",""))}</td>'
                       f'<td>{esc((b.get("format") or "").upper())}</td>'
                       f'<td>{esc(b["product"])}{fl}</td>'
                       f'<td>{esc(money(b["price_per_unit"]))}</td>'
                       f'<td>{esc(money(b["price_per_tonne"]))}</td></tr>')
        lapsed_note = ""
        if p.get("lapsed"):
            who = ", ".join(f'{esc(l["source"])} (last seen {esc(l["last_seen"])})'
                            for l in p["lapsed"])
            lapsed_note = (f'<p class="note"><strong>Not counted in this average:</strong> '
                           f'{who}. A seller drops out after 7 days without a fresh '
                           f'price, so a blocked site cannot sit frozen in the index '
                           f'pretending nothing has moved.</p>')
        bd_sections += (
            f'<div class="card"><div class="oilhead"><span class="dot" style="background:{o["color"]}"></span>'
            f'{esc(o["label"])} &mdash; full price list ({esc(p["date"])}) &middot; '
            f'aggregate {esc(money(p["price_per_unit"]))}/unit</div>'
            f'{lapsed_note}'
            f'<table><tr><th>Website</th><th>Brand</th><th>Pack</th><th>Product (SKU)</th><th>£/20L</th><th>£/tonne</th></tr>'
            f'{rows_b}</table></div>')

    # ---- price changes: today, and across the trailing week -------------------
    ch = data.get("changes", {}) or {}

    def moves_table(moves, extra_col=None):
        if not moves:
            return '<p class="note">No price changes recorded in this window.</p>'
        head = ("<tr><th>Website</th><th>Oil</th><th>Brand</th><th>Pack</th>"
                "<th>From</th><th>To</th><th>Change</th></tr>")
        body = ""
        for m in moves:
            up = m["delta"] > 0
            cls = "up" if up else "down"
            arrow = "▲" if up else "▼"
            body += (f'<tr><td>{esc(m["source"])}</td><td>{esc(m["oil"])}</td>'
                     f'<td>{esc(m.get("brand",""))}</td><td>{esc((m.get("format") or "").upper())}</td>'
                     f'<td>{esc(money(m["from"]))}</td><td>{esc(money(m["to"]))}</td>'
                     f'<td class="{cls}">{arrow} {esc(money(abs(m["delta"])))} '
                     f'({m["pct"]:+.2f}%)</td></tr>')
        return f"<table>{head}{body}</table>"

    def summary_line(summary):
        if not summary:
            return ""
        bits = []
        for oil, s in sorted(summary.items()):
            movers = ", ".join(s["movers"])
            bits.append(
                f'<li><b>{esc(oil.title())}</b>: {s["n_skus_changed"]} SKU(s) moved '
                f'(<span class="up">{s["n_up"]} up</span>, <span class="down">{s["n_down"]} down</span>), '
                f'average {s["avg_delta"]:+.2f} ({s["avg_pct"]:+.2f}%) &mdash; '
                f'moved by: {esc(movers)}</li>')
        return "<ul class='sumlist'>" + "".join(bits) + "</ul>"

    changes_html = (
        f'<h2 class="sechead">Price changes</h2>'
        f'<div class="card"><div class="oilhead">Today &mdash; {esc(ch.get("latest_date") or "n/a")}</div>'
        f'{summary_line(ch.get("today_summary"))}{moves_table(ch.get("today", []))}</div>'
        f'<div class="card"><div class="oilhead">Past 7 days '
        f'({esc(ch.get("week_from") or "")} &rarr; {esc(ch.get("latest_date") or "")})</div>'
        f'{summary_line(ch.get("week_summary"))}{moves_table(ch.get("week", []))}</div>'
    )

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cash &amp; Carry Cooking Oil Price Proxy — static</title>
<style>
  :root {{ --bg:#f7f7f5; --panel:#fff; --ink:#1c1c1e; --muted:#6b6b70; --grid:#e6e6e3; --line:#e3e3e0; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#16171a; --panel:#1f2126; --ink:#f2f2f4; --muted:#9a9ba1; --grid:#2b2e35; --line:#2e3138; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:26px 20px 60px; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  .sub {{ color:var(--muted); font-size:14px; margin:0 0 18px; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:18px; margin-top:16px; }}
  svg {{ width:100%; height:auto; display:block; }}
  svg .grid {{ stroke:var(--grid); stroke-width:1; }}
  svg .ax {{ fill:var(--muted); font-size:13px; font-family:inherit; }}
  svg .mk {{ stroke:var(--panel); stroke-width:2; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }}
  .chip {{ display:inline-flex; align-items:center; gap:8px; border:1px solid var(--line);
    border-radius:999px; padding:6px 12px; font-size:13px; }}
  .dot {{ width:11px; height:11px; border-radius:50%; display:inline-block; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; margin-top:4px; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:500; }}
  td .dot {{ margin-right:8px; }}
  .note {{ color:var(--muted); font-size:12.5px; margin-top:14px; }}
  .oilhead {{ font-weight:600; margin-bottom:8px; display:flex; align-items:center; gap:8px; font-size:14px; flex-wrap:wrap; }}
  .flag {{ color:var(--muted); font-weight:400; font-size:12px; }}
  .up {{ color:#1e8449; font-weight:600; }}   /* market convention: green up */
  .down {{ color:#c0392b; font-weight:600; }}
  .sumlist {{ margin:4px 0 12px; padding-left:18px; font-size:13px; }}
  .sumlist li {{ margin-bottom:4px; }}
  .sechead {{ font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:28px 4px 2px; }}
</style></head>
<body><div class="wrap">
  <h1>Cash &amp; Carry Cooking Oil Price Proxy</h1>
  <p class="sub">UK B2B index — reliable wholesale / cash-and-carry sellers, one fixed pack size per oil. Static view (no JavaScript) generated {esc(data["generated"])}.</p>

  <div class="card">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:8px">Price per standard unit</div>
    {chart}
    <div class="legend">{legend}</div>
    <p class="note">Single snapshot so far, drawn as a flat line from the previous day so every line is visible. Each point is the cross-seller mean after dropping anomalies beyond {data["std_dev_threshold"]} SD.</p>
  </div>

  <div class="card">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:8px">Both units &amp; seller counts</div>
    <table>
      <tr><th>Oil / fat</th><th>Unit</th><th>£ / unit</th><th>£ / tonne</th><th>Sellers</th></tr>
      {rows}
    </table>
    <p class="note">Lines are the cross-seller aggregate per oil. The full list of every SKU at every website is below.</p>
  </div>

  <h2 class="sechead">Full price list per oil — every SKU at every website (grouped by brand)</h2>
  {bd_sections}
  {changes_html}
</div></body></html>"""

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
