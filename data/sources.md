# Price sources

Every price is the **single standalone pack price** as listed on the site (the price
of one drum / block / tin). The £/tonne figure is computed in `scripts/process.py`
from published oil densities — sites are **not** required to publish a per-tonne price.

Prices are aggregated **across multiple sites per oil**, then any observation more
than **2 standard deviations** from the cross-site mean (measured in £/tonne) is
dropped before the mean is taken.

## Cash & carry / wholesale

| Site | URL | Used for | Notes |
|------|-----|----------|-------|
| **JJ Foodservice** | jjfoodservice.com | Sunflower, Rapeseed, Soybean, Palm, Olive EV | Best source: clean per-product pages showing both pack price and per-litre/per-kg unit price. Collection (pickup) prices used. |
| **Brakes Foodservice** | brake.co.uk | Olive EV | Barbera & Sysco Classic 5L EVOO. |
| **YesDeal UK** | yesdealuk.com | Soybean (KTC pure veg) | Listed 20L price. |
| **Surulere Foods** | surulerefoods.com | Soybean (KTC pure veg) | Listed 20L price. |
| **Foodomarket** | foodomarket.com | Olive EV | UK wholesale market index (per-pack), useful as a market-wide cross-check. |

## Retail (for the retail channel toggle)

| Site | URL | Used for | Notes |
|------|-----|----------|-------|
| **Tesco** | tesco.com/groceries | Sunflower, Rapeseed, Olive | Shelf prices, per-litre. |

## Reliability notes

- **Bot protection.** JJ Foodservice, Magna, Bestway and most wholesalers return
  HTTP 403 to automated fetchers, so prices here were read from the live listings /
  search-indexed snapshots rather than scraped. This is why collection is
  **seed-now + manual/assisted top-ups** (see the README) rather than a live scraper.
- **Login walls.** Some wholesalers (Cater-Choice, KFF, Magna, Country Range) hide
  prices behind a trade login, so they are listed as *sources* but not yet used for a
  numeric point. Add them via `add_observation.py` once you have a trade price.
- **Single source, no blends.** "Vegetable oil" in the UK is often a rapeseed/palm
  blend — those are excluded. Only **KTC Pure Vegetable (100% soya bean)** is used,
  tracked as *Soybean*.

## Candidate sites to broaden coverage (prices gated / not yet added)

Magna Foodservice, Bestway Wholesale, Country Range, Cater-Choice, KFF, Woods
Foodservice, Adams Food Service, Ram's Cash & Carry, Bulk Buy Direct, The Fryer
Supplier, Amazon Business, Sainsbury's / Asda / Morrisons (retail).
