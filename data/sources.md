# Price sources

**UK prices only — this is a UK index.** Every price is the **single standalone pack
price** as listed on a UK seller, **including any current discount** — a reliable shop
dropping its price is the signal this index exists to catch, so sale prices are kept, not
reverted to RRP. £/tonne is computed in `scripts/process.py` from published oil densities.

**Reliable / established sellers only.** Small online shops and loss-leaders are excluded
from the aggregate (see the excluded list below). **No blends. No supermarket D2C retail.**

**One fixed pack size per oil** (enforced in `process.py` — any observation at a
different size is rejected):

| Oil | Fixed size |
|-----|-----------|
| Rapeseed | 20 L |
| Soybean (pure veg, 100% soya) | 20 L |

**Two-stage aggregation:** (1) a seller's multiple products for an oil are averaged
into one **seller price** (a shop listing 4 rapeseed SKUs counts as one seller, not
four); (2) across sellers, any seller more than **2 standard deviations** from the
cross-seller mean (in £/tonne) is dropped, then survivors are averaged (stage 2 applies
with ≥ 3 sellers). On days when only some sellers report (e.g. only the auto-scraped
ones), each other seller's **last known price is carried forward**, so the seller set
stays comparable and the index moves only when a seller's price actually changes.

**VAT:** UK cooking oils and fats are **zero-rated food (0% VAT)**, so a seller's
inc-VAT price equals its ex-VAT price — confirmed by the identical KTC Vegetable Oil
20L at £30.69 inc-VAT (Booker) vs £30.49 ex-VAT (JJ). Prices are used as listed, no VAT
adjustment.

## Exact products in the aggregate (as of 2026-07-29)

Prices are per single pack. Where a seller lists several products for an oil, they are
averaged into the one seller-price shown in brackets.

*Auto-updating (no login) sellers are **bold**.*

### Rapeseed — 20 L  *(4 sellers)*
- JJ Foodservice *(£33.24 avg)* — Ext Life Drum £32.99 · Ext Life BIB £32.49 · Pride £33.99 · KTC Chef's Choice £33.49
- Brakes (Sysco) *(£36.75 avg)* — Sysco Classic Ext Life Drum £33.99 · Sysco Classic BIB £39.51
- **Booker** — Chef's Larder Rapeseed 20L — £33.99
- Marfast — KTC Chef's Choice Rapeseed 20L — £42.99

### Soybean (pure veg, 100% soya = KTC Vegetable) — 20 L  *(4 sellers)*
- JJ Foodservice *(£30.24 avg)* — KTC Veg Drum £30.49 · KTC Veg BIB £29.99
- **Booker** — KTC Vegetable Oil 20L — £30.69
- **CK Fast Foods** — KTC Vegetable Oil 20L — £25.39
- Brakes (Sysco) — KTC Vegetable Oil BIB 20L — £35.33

## Reliable sellers used

JJ Foodservice, Brakes (Sysco UK), Booker, Marfast, CK Fast Foods.

**Auto-updating (no login, scraped daily):** Booker (public listing) and CK Fast Foods.
These drive the live movement; the login-gated sellers (JJ, Brakes, Marfast,
Cater-Choice) carry their last price forward until refreshed. Costco/Bestway/Bidfood are
disabled — they need a trade account/login the user does not have.

## Excluded — small shops / loss-leaders (not in the aggregate)

YesDeal UK, Bakers Street (£22.50 soya looked like a loss-leader), Surulere Foods,
Asetena Pa, Everest Cash & Carry, PJ Martinelli. Kept out per the reliability rule.

## Reliable sellers to add once a trade price is available (login-gated)

Bidfood, Bestway Wholesale, Magna Foodservice, Country Range, Cater-Choice (more lines),
Woods Foodservice, Turner Price, Henry Colbeck, Friars Pride, Nortech, V.A. Whitley,
Costco *KTC Vegetable Oil 20L Box*, Costco *KTC Super Hi-Fry 20L*.

## Collection reliability

- **Auto-scrapable** (Costco, Foodomarket, CK Fast Foods): re-read daily by
  `scripts/scrape.py`.
- **Gated** (JJ Foodservice, Brakes/Sysco, Marfast, Cater-Choice): HTTP 403 to bots or a
  trade login → refreshed via `scripts/add_observation.py`.
- No public price API / push feed exists, so collection is **daily best-effort scrape +
  assisted top-up**, not real-time. Wholesale prices move over days/weeks.
