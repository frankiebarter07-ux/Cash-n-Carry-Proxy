# Price sources — verification record, 2026-08-10

> **A dated snapshot, not a living document.** This is the hand-verification the
> index was built against: every SKU opened in a browser and its collection price
> read off the page. Live prices are in `data/observations.csv`; the SKU list is
> `config/targets.json`. Do not update this file — its value is that it records what
> was true on the day.

**UK prices only. All 15 SKUs verified in-browser on 2026-08-10 — every seller shows
prices publicly, no trade login required anywhere.** Collection prices throughout.

Two oils, one pack size (20 L), two formats (bag-in-box / drum), five sellers.

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
