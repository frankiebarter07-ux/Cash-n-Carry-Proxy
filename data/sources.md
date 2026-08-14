# Price sources — verification record, 2026-08-10

> **A dated snapshot, not a living document.** This is the hand-verification the
> index was built against: every SKU opened in a browser and its collection price
> read off the page. Live prices are in `data/observations.csv`; the SKU list is
> `config/targets.json`. Do not update this file — its value is that it records what
> was true on the day.

**UK prices only. The original 15 SKUs were verified in-browser on 2026-08-10 — every
seller shows prices publicly, no trade login required anywhere.** Collection prices
throughout. The five palm SKUs were added later from a catalogue search and have not
had the same in-browser verification — see the note at the foot of this file.

Three oils. Rapeseed and soybean in 20 L (bag-in-box / drum); palm in a 12.5 kg box.
Five sellers.

**Aggregation:** a seller's SKUs are averaged into one seller-price, then averaged
across sellers with a 2-standard-deviation outlier filter. A non-reporting seller's
last price is carried forward for up to 7 days so the index moves only on real price
changes, after which that seller drops out of the average.

**VAT:** UK cooking oils are zero-rated, so inc-VAT = ex-VAT; prices used as listed.

## Verified prices (2026-08-10)

### Rapeseed — 20 L

| Seller | Format | Product | £ / 20L |
|---|---|---|---|
| Magna Foodservice | DRUM | KTC Extended Life Rapeseed Oil 20ltr | £31.49 |
| Marfast | DRUM | KTC Chef's Choice Rapeseed Oil 20ltr (Drum) | £32.79 |
| JJ Foodservice | DRUM | KTC Chef's Choice Rapeseed Oil Drum 1x20L | £33.99 |
| Booker | BIB | Chef's Larder Rapeseed Cooking Oil 20 Litres (141775) | £33.99 |
| Booker | DRUM | Chef's Larder Rapeseed Cooking Oil 20 Litres (570135) | £33.99 |
| Brakes (Sysco) | BIB | Sysco Classic Extended Life Rapeseed Oil 20L | £39.51 |

### Soybean — 20 L

| Seller | Format | Product | £ / 20L |
|---|---|---|---|
| Magna Foodservice | BIB | KTC Vegetable Oil Box 20ltr | £27.99 |
| JJ Foodservice | BIB | KTC Vegetable Cooking Oil BIB 1x20L | £28.99 |
| Magna Foodservice | DRUM | KTC Vegetable Oil Tin 20ltr | £28.99 |
| JJ Foodservice | DRUM | KTC Vegetable Cooking Oil Drum 1x20L | £29.49 |
| Marfast | BIB | KTC (Bottle In Box) 20ltr Vegetable Oil | £29.99 |
| Marfast | DRUM | KTC Vegetable Oil 20ltr (Drum) | £30.49 |
| Booker | BIB | KTC Vegetable Cooking Oil 20 Litres (181801) | £30.69 |
| Booker | DRUM | KTC Vegetable Cooking Oil 20 Litres (51332) | £30.69 |
| Brakes (Sysco) | BIB | KTC Vegetable Oil (Bottle in Box) 20L | £35.33 |

## Sellers

JJ Foodservice · Brakes (Sysco) · Booker · Marfast · Magna Foodservice

All five are auto-scrape targets (`config/auth_sites.json`), fetched with a real
browser. No credentials are used. A price is accepted **only** from a labelled
selector — the bare-£ regex fallback was removed after it once recorded a stray
number from a gated page as a real price.

## Removed

CK Fast Foods — its page is login-walled, and the values the old regex scraper
recorded (£25.39 / £25.49) could not be verified. Dropped from the index.
Earlier data is archived in `data/observations_legacy.csv`.

## Palm (added 2026-08-14) — not yet in-browser verified

Five 12.5 kg palm SKUs were added from a `scripts/discover.py` catalogue search:
two at Marfast, three at Magna. They are recorded here as **unverified** because
the search reads a results grid, not a labelled price on the product page — the
adapters do that on the next run, and only a labelled price is ever written.

Two things still want a human eye on the actual product pages:

- **Composition.** The index tracks pure single-source oils. *Palmax Fat Oil*,
  *Caterfry* and *Eden Harvest OptiPalm* are brand names that do not state
  composition, so any of them could be a blend and would then have to be dropped.
- **Pack.** All five are listed as 12.5 kg boxes. Confirm that is the pack the
  price refers to, not a case of smaller units.

JJ Foodservice, Brakes and Booker returned no palm. For Booker that is the usual
datacenter-IP block; for the other two the catalogue search simply found nothing,
which is not the same as proof they do not stock it.

### Brakes palm — listed, deliberately excluded (2026-08-14)

Brakes stocks palm but at roughly twice JJ's price for a nominally similar
product, and it was excluded on that basis.

**This exclusion should be re-checked, because "expensive" alone is not a valid
reason to drop a seller from a price index** — dropping the dear ones biases the
index downward, and the 2-SD filter exists precisely to handle genuine outliers
on the record rather than by omission. The exclusion is sound only if the Brakes
product is *not comparable*: a 2×12.5kg case, a 25kg unit, or per-case pricing
would each explain a doubling and would each justify leaving it out.

If it turns out to be a like-for-like 12.5kg box, add it back and let the outlier
filter decide — that is what it is for, and the exclusion will be visible in
`n_excluded` rather than invisible in this file.
