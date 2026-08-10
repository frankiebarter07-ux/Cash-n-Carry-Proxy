#!/usr/bin/env python3
"""
Write SUMMARY.md, and decide whether today is worth telling anyone about.

Two jobs, deliberately separate:

1. **SUMMARY.md** — rebuilt every day. GitHub renders it in the repository, so
   anyone can read the current index on a phone without cloning anything or
   downloading an HTML file. This is the "go and look" view.

2. **The report body** — written only when there is something to say. The daily
   workflow posts it as a comment on a single long-running issue, which GitHub
   emails to everyone watching the repository. This is the "come and tell me" view.

The second only fires when a price actually moved, or on the weekly digest day.
That restraint is the whole point: a summary that arrives every morning saying
"nothing changed" gets filtered within a fortnight, and then the morning that
matters gets filtered with it. Silence has to mean something for noise to be worth
reading.

    python3 scripts/render_summary.py                  # write SUMMARY.md only
    python3 scripts/render_summary.py --report-out r.md # ...and a report if warranted

Exit status is always 0. Whether a report was written is reported on stdout as
`notify=true|false`, and to $GITHUB_OUTPUT when running in Actions.

Pure standard library.
"""

import argparse
import json
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERIES = os.path.join(ROOT, "data", "series.json")
SUMMARY = os.path.join(ROOT, "SUMMARY.md")

DIGEST_WEEKDAY = 0          # Monday: send a digest even in a flat week


def money(v):
    return f"£{v:,.2f}" if v < 100 else f"£{v:,.0f}"


def moves_table(moves, limit=None):
    """Markdown table of per-SKU movements, biggest first."""
    if not moves:
        return "_No price changes in this window._\n"
    shown = moves[:limit] if limit else moves
    out = ["| Seller | Oil | Pack | From | To | Change |",
           "|---|---|---|---|---|---|"]
    for m in shown:
        arrow = "🔺" if m["delta"] > 0 else "🔻"
        out.append(
            f'| {m["source"]} | {m["oil"]} | {(m.get("format") or "").upper()} '
            f'| {money(m["from"])} | {money(m["to"])} '
            f'| {arrow} {money(abs(m["delta"]))} ({m["pct"]:+.2f}%) |')
    if limit and len(moves) > limit:
        out.append(f'| … | | | | | _{len(moves) - limit} more_ |')
    return "\n".join(out) + "\n"


def summary_lines(summary):
    """One line per oil: how much, which way, and — the point — who moved."""
    if not summary:
        return ""
    out = []
    for oil in sorted(summary):
        s = summary[oil]
        direction = "up" if s["avg_delta"] > 0 else "down"
        out.append(
            f'- **{oil}**: {s["n_skus_changed"]} SKU(s) moved, average {direction} '
            f'{money(abs(s["avg_delta"]))} ({s["avg_pct"]:+.2f}%) — '
            f'{s["n_up"]} up, {s["n_down"]} down. '
            f'Moved by: {", ".join(s["movers"])}.')
    return "\n".join(out) + "\n"


def current_table(data):
    rows = ["| Oil | Pack | £ per pack | £ per tonne | Sellers counted |",
            "|---|---|---|---|---|"]
    for oil in data["oils"].values():
        pts = (oil.get("channels", {}) or {}).get("cash_carry", [])
        if not pts:
            continue
        p = pts[-1]
        sp = oil["standard_pack"]
        rows.append(f'| {oil["label"]} | {sp["value"]} {sp["unit"]} '
                    f'| {money(p["price_per_unit"])} | {money(p["price_per_tonne"])} '
                    f'| {p["n_used"]} |')
    return "\n".join(rows) + "\n"


def lapsed_note(data):
    """Name any seller that has stopped reporting, on every view that shows a price."""
    seen = {}
    for oil in data["oils"].values():
        for p in (oil.get("channels", {}) or {}).get("cash_carry", []) or []:
            for l in p.get("lapsed", []) or []:
                seen[l["source"]] = l
    if not seen:
        return ""
    who = "; ".join(f'{l["source"]} (last seen {l["last_seen"]}, '
                    f'{l["days_ago"]} days ago)' for l in seen.values())
    return (f"\n> ⚠️ **Not counted in these figures:** {who}. "
            f"A seller drops out after 7 days without a fresh price, so a blocked "
            f"site cannot sit frozen in the index pretending nothing has moved.\n")


def build_summary(data):
    ch = data.get("changes", {}) or {}
    generated = data.get("generated", "unknown")
    parts = [
        "# Cooking oil price index — current",
        "",
        f"_Rebuilt automatically. Latest data: **{ch.get('latest_date') or generated}**._",
        "",
        "UK cash-and-carry **collection** prices for rapeseed and vegetable (soybean) "
        "oil. A movement proxy — it answers *are wholesale oil prices moving, and who "
        "moved first?*, not *what will I pay?*",
        "",
        "## Where it stands",
        "",
        current_table(data),
        lapsed_note(data),
        "## What moved today",
        "",
        summary_lines(ch.get("today_summary")),
        "",
        moves_table(ch.get("today")),
        "",
        f"## Trailing week (since {ch.get('week_from') or 'n/a'})",
        "",
        summary_lines(ch.get("week_summary")),
        "",
        moves_table(ch.get("week"), limit=15),
        "",
        "---",
        "",
        "**Full detail:** `dashboard_static.html` (opens anywhere, no JavaScript) or "
        "`index.html` (interactive, £/unit ↔ £/tonne). Raw record: "
        "`data/observations.csv`. How it works and what to do when it breaks: "
        "[`HANDOVER.md`](HANDOVER.md).",
        "",
        "_Generated by `scripts/render_summary.py` — do not edit by hand._",
        "",
    ]
    return "\n".join(parts)


def build_report(data, is_digest):
    """The pushed message. Shorter than SUMMARY.md: what moved, who moved it."""
    ch = data.get("changes", {}) or {}
    today, week = ch.get("today") or [], ch.get("week") or []
    when = ch.get("latest_date") or data.get("generated", "")

    if today:
        head = [f"## Prices moved — {when}", "", summary_lines(ch.get("today_summary")),
                "", moves_table(today), ""]
    else:
        head = [f"## Weekly digest — {when}", "",
                "No price changed today.", ""]

    body = head + ["### Where it stands", "", current_table(data), lapsed_note(data)]

    if is_digest:
        body += ["", f"### Trailing week (since {ch.get('week_from') or 'n/a'})", "",
                 summary_lines(ch.get("week_summary")) or "_Flat across the week._\n",
                 "", moves_table(week, limit=10)]

    body += ["", "---",
             "_Posted automatically by the daily collection. "
             "Full detail in [`SUMMARY.md`](SUMMARY.md); "
             "silence means no seller changed a listed price._"]
    return "\n".join(body)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report-out", help="write the pushed report here, if one is warranted")
    ap.add_argument("--force-report", action="store_true",
                    help="write the report even with no movement (for testing)")
    args = ap.parse_args()

    with open(SERIES, encoding="utf-8") as fh:
        data = json.load(fh)

    with open(SUMMARY, "w", encoding="utf-8") as fh:
        fh.write(build_summary(data))
    print(f"wrote {SUMMARY}")

    ch = data.get("changes", {}) or {}
    moved = bool(ch.get("today"))
    latest = ch.get("latest_date")
    try:
        is_digest = date.fromisoformat(latest).weekday() == DIGEST_WEEKDAY
    except (TypeError, ValueError):
        is_digest = False

    notify = bool(moved or is_digest or args.force_report)
    if notify and args.report_out:
        with open(args.report_out, "w", encoding="utf-8") as fh:
            fh.write(build_report(data, is_digest or args.force_report))
        print(f"wrote {args.report_out}")

    why = ("prices moved" if moved else
           "weekly digest" if is_digest else
           "forced" if args.force_report else
           "nothing moved -- staying quiet")
    print(f"notify={'true' if notify else 'false'}  ({why})")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"notify={'true' if notify else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
