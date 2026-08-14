#!/usr/bin/env python3
"""
Write SUMMARY.md, and decide whether today is worth telling anyone about.

Two jobs, deliberately separate:

1. **SUMMARY.md** — rebuilt every day. GitHub renders it in the repository, so
   anyone can read the current index without cloning anything. This is the "go and
   look" view.

2. **The report** — written only when there is something to say, in both Markdown
   (posted as a comment on the report issue) and HTML (emailed). The daily workflow
   sends it when a seller actually changed a listed price, or on the weekly digest
   day.

That restraint is the whole point: a summary that arrives every morning saying
"nothing changed" gets filtered within a fortnight, and then the morning that matters
gets filtered with it. Silence has to mean something for noise to be worth reading.

    python3 scripts/render_summary.py                        # SUMMARY.md only
    python3 scripts/render_summary.py --report-out r.md --report-html r.html

Content is built once as a list of blocks, then rendered to Markdown or HTML, so the
two can never drift apart.

Exit status is always 0. Whether a report was written is printed as
`notify=true|false` and written to $GITHUB_OUTPUT when running in Actions.

Pure standard library.
"""

import argparse
import html
import json
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERIES = os.path.join(ROOT, "data", "series.json")
SUMMARY = os.path.join(ROOT, "SUMMARY.md")

DIGEST_WEEKDAY = 0          # Monday: send a digest even in a flat week

# Blocks are ("h", level, text) | ("p", text) | ("bullets", [text]) |
#            ("table", [headers], [[cells]]) | ("rule",)
# Cell text is plain; renderers escape for their own format.


def money(v):
    return f"£{v:,.2f}" if v < 100 else f"£{v:,.0f}"


def when(iso):
    """2026-08-11 -> 11 Aug 2026. Reports are read by people, not parsers."""
    try:
        return date.fromisoformat(iso).strftime("%-d %b %Y")
    except (TypeError, ValueError):
        return iso or "n/a"


# --------------------------------------------------------------------------- #
# content
# --------------------------------------------------------------------------- #
def moves_blocks(moves, limit=None):
    if not moves:
        return [("p", "No movements.")]
    shown = moves[:limit] if limit else moves
    rows = []
    for m in shown:
        arrow = "▲" if m["delta"] > 0 else "▼"
        rows.append([m["source"], m["oil"].capitalize(),
                     (m.get("format") or "").capitalize(),
                     money(m["from"]), money(m["to"]),
                     f'{arrow} {money(abs(m["delta"]))} ({m["pct"]:+.2f}%)'])
    blocks = [("table", ["Seller", "Oil", "Pack", "From", "To", "Change"], rows)]
    if limit and len(moves) > limit:
        blocks.append(("p", f"{len(moves) - limit} further movements not shown."))
    return blocks


def summary_bullets(summary):
    """One line per oil: how much, which way, and — the point — who moved."""
    if not summary:
        return []
    out = []
    for oil in sorted(summary):
        s = summary[oil]
        sign = "+" if s["avg_delta"] > 0 else "−"
        out.append(f'{oil.capitalize()} — {s["n_skus_changed"]} SKUs, '
                   f'avg {sign}{money(abs(s["avg_delta"]))} ({s["avg_pct"]:+.2f}%), '
                   f'{s["n_up"]} up / {s["n_down"]} down. '
                   f'Movers: {", ".join(s["movers"])}.')
    return [("bullets", out)] if out else []


def current_blocks(data):
    rows = []
    for oil in data["oils"].values():
        pts = (oil.get("channels", {}) or {}).get("cash_carry", [])
        if not pts:
            continue
        p, sp = pts[-1], oil["standard_pack"]
        rows.append([oil["label"], f'{sp["value"]} {sp["unit"]}',
                     money(p["price_per_unit"]), money(p["price_per_tonne"]),
                     str(p["n_used"])])
    return [("table", ["Oil", "Pack", "£/pack", "£/tonne", "Sellers"], rows)]


def lapsed_blocks(data):
    """Name any seller that has stopped reporting, wherever a price is shown."""
    seen = {}
    for oil in data["oils"].values():
        for p in (oil.get("channels", {}) or {}).get("cash_carry", []) or []:
            for l in p.get("lapsed", []) or []:
                seen[l["source"]] = l
    if not seen:
        return []
    who = "; ".join(f'{l["source"]} (last reported {when(l["last_seen"])}, '
                    f'{l["days_ago"]} days)' for l in seen.values())
    return [("p", f"Excluded from the average: {who}.")]


def summary_doc(data):
    ch = data.get("changes", {}) or {}
    day = when(ch.get("latest_date") or data.get("generated"))
    return ([("h", 1, "UK Cooking Oil Index"),
             ("p", f"Collection prices, standard unit sizes \u2014 20 L drums or bibs, "
                   f"12.5 kg blocks. Five UK cash-and-carry sellers. "
                   f"Updated {day}."),
             ("h", 2, "Index level")]
            + current_blocks(data) + lapsed_blocks(data)
            + [("h", 2, f"Movements — {day}")]
            + summary_bullets(ch.get("today_summary")) + moves_blocks(ch.get("today"))
            + [("h", 2, f'Week to {day}')]
            + summary_bullets(ch.get("week_summary"))
            + moves_blocks(ch.get("week"), limit=15)
            + [("rule",),
               ("p", "Per-SKU detail: index.html, or dashboard_static.html without "
                     "JavaScript. Underlying record: data/observations.csv.")])


def report_doc(data, is_digest):
    """The pushed message: what moved, and who moved it."""
    ch = data.get("changes", {}) or {}
    today, week = ch.get("today") or [], ch.get("week") or []
    day = when(ch.get("latest_date") or data.get("generated"))

    blocks = [("h", 2, f"UK Cooking Oil Index — {day}"), ("h", 3, "Movements")]
    blocks += (summary_bullets(ch.get("today_summary")) + moves_blocks(today)
               if today else [("p", "No movements.")])

    blocks += [("h", 3, "Index level")] + current_blocks(data) + lapsed_blocks(data)

    if is_digest:
        blocks += [("h", 3, f"Week to {day}")]
        blocks += summary_bullets(ch.get("week_summary")) + moves_blocks(week, limit=10)

    blocks += [("rule",),
               ("p", "Collection prices, standard unit sizes \u2014 20 L drums or bibs, "
                     "12.5 kg blocks. Five UK cash-and-carry sellers.")]
    return blocks


# --------------------------------------------------------------------------- #
# renderers
# --------------------------------------------------------------------------- #
def render_md(blocks):
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "h":
            out.append(f'{"#" * b[1]} {b[2]}\n')
        elif kind == "p":
            out.append(f"{b[1]}\n")
        elif kind == "bullets":
            out.append("\n".join(f"- {x}" for x in b[1]) + "\n")
        elif kind == "table":
            _, headers, rows = b
            out.append("| " + " | ".join(headers) + " |")
            out.append("|" + "---|" * len(headers))
            for r in rows:
                out.append("| " + " | ".join(r) + " |")
            out.append("")
        elif kind == "rule":
            out.append("---\n")
    return "\n".join(out).rstrip() + "\n"


def render_html(blocks, title):
    """Self-contained HTML for email. Inline styles only -- mail clients strip
    <style> blocks, and many strip classes entirely."""
    e = html.escape
    td = "padding:6px 10px;border-bottom:1px solid #e3e3e3;font-size:14px"
    th = ("padding:6px 10px;border-bottom:2px solid #ccc;font-size:12px;"
          "text-align:left;color:#555;text-transform:uppercase;letter-spacing:.04em")
    out = [f'<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;'
           f'color:#1a1a1a;max-width:760px;margin:0 auto;padding:8px">']
    for b in blocks:
        kind = b[0]
        if kind == "h":
            size = {1: 22, 2: 18, 3: 15}.get(b[1], 15)
            out.append(f'<h{b[1]} style="font-size:{size}px;margin:20px 0 8px">'
                       f'{e(b[2])}</h{b[1]}>')
        elif kind == "p":
            out.append(f'<p style="font-size:14px;line-height:1.5;margin:8px 0">'
                       f'{e(b[1])}</p>')
        elif kind == "bullets":
            items = "".join(f'<li style="font-size:14px;line-height:1.5;margin:4px 0">'
                            f'{e(x)}</li>' for x in b[1])
            out.append(f'<ul style="padding-left:20px;margin:8px 0">{items}</ul>')
        elif kind == "table":
            _, headers, rows = b
            head = "".join(f'<th style="{th}">{e(h)}</th>' for h in headers)
            body = ""
            for r in rows:
                cells = ""
                for c in r:
                    colour = ""
                    if c.startswith("▲"):
                        colour = ";color:#1e8449;font-weight:600"  # up: green
                    elif c.startswith("▼"):
                        colour = ";color:#c0392b;font-weight:600"  # down: red
                    cells += f'<td style="{td}{colour}">{e(c)}</td>'
                body += f"<tr>{cells}</tr>"
            out.append(f'<table style="border-collapse:collapse;width:100%;'
                       f'margin:10px 0"><tr>{head}</tr>{body}</table>')
        elif kind == "rule":
            out.append('<hr style="border:0;border-top:1px solid #e3e3e3;margin:18px 0">')
    out.append("</div>")
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<title>{e(title)}</title></head><body>' + "".join(out) + "</body></html>")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Build SUMMARY.md and the daily report.")
    ap.add_argument("--report-out", help="Markdown report (for the issue comment)")
    ap.add_argument("--report-html", help="HTML report (for email)")
    ap.add_argument("--force-report", action="store_true",
                    help="write the report even with no movement (for testing)")
    args = ap.parse_args()

    with open(SERIES, encoding="utf-8") as fh:
        data = json.load(fh)

    with open(SUMMARY, "w", encoding="utf-8") as fh:
        fh.write(render_md(summary_doc(data))
                 + "\n_Generated by `scripts/render_summary.py` — do not edit by hand._\n")
    print(f"wrote {SUMMARY}")

    ch = data.get("changes", {}) or {}
    moved = bool(ch.get("today"))
    try:
        is_digest = date.fromisoformat(ch.get("latest_date")).weekday() == DIGEST_WEEKDAY
    except (TypeError, ValueError):
        is_digest = False

    notify = bool(moved or is_digest or args.force_report)
    if notify:
        blocks = report_doc(data, is_digest or args.force_report)
        subject = (f"UK Cooking Oil Index — movements {when(ch.get('latest_date'))}"
                   if moved else
                   f"UK Cooking Oil Index — week to {when(ch.get('latest_date'))}")
        if args.report_out:
            with open(args.report_out, "w", encoding="utf-8") as fh:
                fh.write(render_md(blocks))
            print(f"wrote {args.report_out}")
        if args.report_html:
            with open(args.report_html, "w", encoding="utf-8") as fh:
                fh.write(render_html(blocks, subject))
            print(f"wrote {args.report_html}")

    why = ("prices moved" if moved else "weekly digest" if is_digest
           else "forced" if args.force_report else "nothing moved -- staying quiet")
    print(f"notify={'true' if notify else 'false'}  ({why})")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        subject = (f"UK Cooking Oil Index — movements {when(ch.get('latest_date'))}"
                   if moved else
                   f"UK Cooking Oil Index — week to {when(ch.get('latest_date'))}")
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"notify={'true' if notify else 'false'}\n")
            fh.write(f"subject={subject}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
