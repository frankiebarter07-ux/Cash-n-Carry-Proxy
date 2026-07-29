# Cash & Carry Cooking Oil Price Proxy

A lightweight indicator that tracks the price of **single-source cooking oils** at UK
cash & carry / wholesale outlets (with a retail comparison), aggregated **across
multiple websites**, so you can watch when these oils move. No oil blends.

Open **[`index.html`](index.html)** in a browser for the interactive chart:

- **A line per oil** on one axis — toggle each on/off from the legend.
- **Unit switch:** *£ per unit* (the standard pack for that oil) ↔ *£ per metric tonne*.
- **Channel switch:** cash & carry / retail / both.
- Hover any point to see the price, how many sites fed it, and how many anomalies
  were dropped.

![units: £/unit or £/tonne · lines per oil · channel toggle]

## Oils tracked & their standard unit

| Oil | Standard unit | Basis |
|-----|---------------|-------|
| Sunflower | 20 L drum | volume |
| Rapeseed | 20 L drum | volume |
| Soybean (pure veg, 100% soya) | 20 L drum | volume |
| Palm | 12.5 kg block | weight |
| Olive (extra virgin) | 5 L tin | volume |

*Palm* is priced by weight, so its per-kg price scales straight to per-tonne. The
volume oils convert £/L → £/tonne using published densities (see `config/oils.json`).
*"Price per unit"* means the price of that oil's standard pack; *"price per metric
tonne"* normalises every oil to 1,000 kg so they sit on a comparable scale.

## Methodology

1. **Collect** — each row in `data/observations.csv` is one product seen on one site
   on one day, recorded as the **single standalone pack price** (e.g. one 20 L drum).
2. **Standardise** — every observation is scaled to the oil's standard unit.
3. **Convert** — every observation is also expressed in £/metric tonne.
4. **Drop anomalies** — for each oil × channel × date, any observation more than
   **2 standard deviations** from the cross-site mean (in £/tonne) is excluded.
   *(Applied only when a group has ≥ 3 sites; with fewer, there is nothing to
   compare against.)*
5. **Aggregate** — the surviving observations are averaged into one point.

Run it:

```bash
python3 scripts/process.py      # rebuilds data/series.js + data/series.json
```

No third-party dependencies — Python 3 standard library only.

## Sources

Aggregated across **JJ Foodservice, Brakes, YesDeal, Surulere Foods, Foodomarket**
(cash & carry / wholesale) and **Tesco** (retail). Full details, reliability notes,
and candidate sites to add are in **[`data/sources.md`](data/sources.md)**.

> Wholesalers block automated scraping (HTTP 403) and several hide prices behind a
> trade login, so this collects data **seed-now + manual/assisted top-ups** rather
> than via a live scraper. It's a *movement proxy*, not a live trading price.

## Adding new prices (building the history)

The seed is a single snapshot. Each time you add prices for a new date, the lines
grow and movement becomes visible. Add a point with:

```bash
python3 scripts/add_observation.py \
  --oil rapeseed --channel cash_carry \
  --source "Bestway" --product "Consumer's Pride Rapeseed 20L" \
  --url "https://www.bestwaywholesale.co.uk/product/388027-1" \
  --pack 20 --unit L --price 34.50 \
  --date 2026-08-05 --note "collection price"
```

That appends to `data/observations.csv` and rebuilds the series automatically. You can
also edit the CSV by hand and re-run `process.py`.

## Files

```
config/oils.json          oil registry: standard unit, density, colour (edit to add an oil)
data/observations.csv     raw price observations (the ground truth you top up)
data/sources.md           every website used, with reliability notes
data/series.js / .json    generated aggregate series (do not edit by hand)
scripts/process.py        standardise + convert + anomaly-filter + aggregate
scripts/add_observation.py append one price and rebuild
index.html                self-contained dashboard (no external libraries)
```
