# Cash & Carry Cooking Oil Price Proxy

> **Taking this over or running it in production? Start with
> [`HANDOVER.md`](HANDOVER.md)** — ownership, security, the daily schedule and what
> to do when something breaks. Design rationale is in
> [`ARCHITECTURE.md`](ARCHITECTURE.md).

A daily index of **rapeseed** and **vegetable (soybean)** oil prices across five UK
**cash-and-carry / B2B** sellers. It's a *movement proxy* — it answers *"are wholesale
oil prices moving, and who moved first?"*, not *"what will I pay?"*

No blends, no supermarket retail, no logins: every price tracked is publicly visible.

## What's tracked

15 SKUs, all **20 L**, split by pack format (**bib** = bag-in-box, **drum**):

| Seller | Rapeseed | Soybean | Collected by |
|---|---|---|---|
| JJ Foodservice | drum | bib, drum | Cloud — JSON-LD ✅ |
| Brakes (Sysco) | bib | bib | Cloud — selector ✅ |
| Marfast | drum | bib, drum | Cloud — displayed price |
| Magna Foodservice | drum | bib, drum | Cloud — displayed price |
| **Booker** | bib, drum | bib, drum | **Self-hosted runner** (blocks datacenter IPs) |

Exact products and URLs: [`config/targets.json`](config/targets.json).

## Viewing it

- **[`dashboard_static.html`](dashboard_static.html)** — works everywhere, including
  with JavaScript disabled and in embedded viewers. Chart, full per-SKU price list by
  seller, and price-change tables (today + trailing 7 days, showing who moved).
- **[`index.html`](index.html)** — interactive: £/unit ↔ £/tonne toggle, per-oil
  on/off, tap a point for the SKU breakdown. Needs a normal browser.

## Method

1. **Collect** — one row per SKU per seller per day, at the **collection price** for a
   single 20 L pack.
2. **Standardise** — every price expressed per 20 L *and* per **metric tonne** (using
   published densities), so the two oils are comparable.
3. **Average within a seller** — a seller's SKUs collapse to one *seller price*, so a
   shop listing four SKUs doesn't outvote one listing a single SKU.
4. **Average across sellers** — dropping any seller more than **2 standard deviations**
   from the cross-seller mean (only applied with ≥ 3 sellers).
5. **Carry forward** — a seller that didn't report keeps its last price, so the index
   moves only on *real* price changes, never on missing data.

**VAT:** UK cooking oils are zero-rated, so inc-VAT = ex-VAT; prices are used as listed.

## Running it

Automatic — `.github/workflows/daily-prices.yml` at 06:00 UTC daily. Any failure opens
a GitHub issue labelled `collection-failure`, so it cannot fail silently.

By hand:

```bash
python3 scripts/adapters.py --selftest   # offline tests, no network
python3 scripts/adapters.py --run        # live fetch, report only
python3 scripts/adapters.py --run --write   # ...and record the results
python3 scripts/process.py               # rebuild the series
python3 scripts/render_static.py         # rebuild the static dashboard
```

Only `scripts/adapters.py` needs a third-party package (Playwright, in
`requirements.txt`); everything else is the Python standard library.

## The rule that keeps the data honest

**A price is only ever accepted from a labelled source** — JSON-LD `offers.price`, a
JSON API field, or a known price selector — and **never** from a bare `£` match on the
page. If no labelled price is found, nothing is written and the run fails loudly.

This exists because a regex fallback once recorded a delivery-threshold figure from a
blocked page as if it were a product price. See `ARCHITECTURE.md` §2.

Related: a *green run is not necessarily a correct run*. Two sellers have returned
properly-labelled but **wrong** prices (delivery instead of collection; stale
structured data). Spot-check a few SKUs against the live sites periodically —
`HANDOVER.md` §7.

## Files

```
HANDOVER.md               runbook: ownership, security, setup, failure triage
ARCHITECTURE.md           design: rules, data model, fetch tiers, anti-bot, gaps
config/targets.json       the 15 SKUs: seller, oil, format, product, URL
config/oils.json          oil registry: pack size, density, colour
data/observations.csv     raw record, one row per SKU per day
data/series.json|.js      computed series + per-SKU breakdown + price changes
scripts/adapters.py       per-seller price adapters (+ selftest, diagnose)
scripts/process.py        standardise, aggregate, carry forward, compute changes
scripts/render_static.py  build the no-JavaScript dashboard
scripts/manual_prices.py  record a blocked seller's prices by hand
tools/check_protection.sh probe each site for bot-protection / price visibility
.github/workflows/        daily collection, adapter tests, manual Booker entry
```

`data/observations_legacy.csv` is the pre-verification history. It contains values
that could not be confirmed — **do not merge it back into the live series.**
