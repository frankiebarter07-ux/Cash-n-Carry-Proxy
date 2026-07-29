# Price sources

**UK prices only — this is a UK index.** Every price is the **single standalone pack
price** as listed on a UK seller (the price of one drum / block / tin). The £/tonne
figure is computed in `scripts/process.py` from published oil densities — sites are
**not** required to publish a per-tonne price.

Focus is **B2B / cash & carry** (wholesale, foodservice, warehouse clubs). Supermarket
(D2C) retail is **excluded** unless a supermarket stocks the exact bulk drum/block the
B2B sellers use — none currently do, so there are no supermarket rows.

Prices are aggregated **across multiple sites per oil**, then any observation more than
**2 standard deviations** from the cross-site mean (measured in £/tonne) is dropped
before the mean is taken.

## Sites used (the exact products are in `config/products.json`)

| Site | Type | URL | Oils | Auto-scrape? |
|------|------|-----|------|--------------|
| **JJ Foodservice** | Cash & carry / foodservice | jjfoodservice.com | Sunflower, Rapeseed, Soybean, Palm, Olive EV | No — bot-protected (HTTP 403) |
| **Brakes (Sysco UK)** | B2B foodservice | brake.co.uk | Rapeseed, Olive EV | No — trade login |
| **Costco UK** | Warehouse club (business) | costco.co.uk | Sunflower, Olive EV | Yes — JSON-LD price |
| **YesDeal UK** | Online cash & carry | yesdealuk.com | Soybean | Yes — Shopify JSON-LD |
| **Surulere Foods** | Online cash & carry | surulerefoods.com | Soybean | Yes — Shopify JSON-LD |
| **Foodomarket** | UK wholesale price index | foodomarket.com | Olive EV | Yes — index figure |

*Sysco = Brakes in the UK; "Sysco Classic" is their own-label range. Costco is a
membership warehouse (business membership), treated here as B2B, not supermarket retail.*

## Exact products currently in the aggregate

- **Sunflower** — JJ Foodservice *KTC High Oleic Sunflower BIB 20L*; Costco UK *Pura Sunflower Oil 5L*
- **Rapeseed** — JJ Foodservice *Pride Rapeseed Oil Drum 20L*; Brakes *Sysco Classic Extended Life Rapeseed Oil 20L*
- **Soybean (pure veg, 100% soya)** — JJ Foodservice *KTC Pure Vegetable Oil 20L*; YesDeal *KTC Vegetable Oil 20L*; Surulere Foods *KTC Vegetable Oil 20L*
- **Palm** — JJ Foodservice *JJ SG Palm Oil 12.5kg*; JJ Foodservice *Palmax SG Palm Oil 12.5kg*
- **Olive (extra virgin)** — JJ Foodservice *Antica Tradizione EVOO 5L*; Brakes *Sysco Classic EVOO 5L*; Brakes *Barbera EVOO 5L*; Costco UK *Filippo Berio EVOO 5L*; Foodomarket *UK EVOO 5L index*

## Reliability of daily collection

- **Auto-scrapable sites** (Costco, YesDeal, Surulere, Foodomarket) are re-read every
  day by `scripts/scrape.py` via the GitHub Action, reading the price from the page's
  JSON-LD or a £-price match.
- **Bot-protected / login-gated sites** (JJ Foodservice, Brakes/Sysco) return HTTP 403
  to automated fetchers or hide prices behind a trade login, so they **cannot** be
  scraped reliably from CI. They are refreshed with `scripts/add_observation.py`
  (assisted top-up). This is why the pipeline is *daily best-effort scrape + manual
  top-up*, not a live feed.
- There is **no public price API and no push feed** from these sellers, so true
  "instant" monitoring is not possible. Wholesale oil prices move over days/weeks, so a
  once-a-day pass captures all real movement (see README → "Why daily, not real-time").

## No blends

UK "vegetable oil" is often a rapeseed/palm **blend** — excluded. Only **KTC Pure
Vegetable (100% soya bean)** is used, tracked as *Soybean*. KTC Pomace/Olive blends at
Costco are also excluded.

## Candidate UK sites to broaden coverage (prices gated / not yet added)

Bidfood, Magna Foodservice, Bestway Wholesale, Country Range, Cater-Choice, KFF, Woods
Foodservice, Adams Food Service, Ram's Cash & Carry, Marfast, Bulk Buy Direct, The
Fryer Supplier. Add any of them via `scripts/add_observation.py` once you have a price.
