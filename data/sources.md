# Price sources

**UK prices only — this is a UK index.** Every price is the **single standalone pack
price** as listed on a UK seller. The £/tonne figure is computed in `scripts/process.py`
from published oil densities — sites are **not** required to publish a per-tonne price.

**One fixed pack size per oil** (enforced in `process.py` — any observation at a
different size is rejected):

| Oil | Fixed size |
|-----|-----------|
| Sunflower | 20 L |
| Rapeseed | 20 L |
| Soybean (pure veg, 100% soya) | 20 L |
| Palm | 12.5 kg |
| Olive (extra virgin) | 5 L |

Focus is **B2B / cash & carry** (wholesale, foodservice, warehouse clubs). Supermarket
D2C retail is excluded unless a supermarket stocks the exact bulk pack — none do.

Prices are aggregated **across multiple sites per oil**; any observation more than
**2 standard deviations** from the cross-site mean (in £/tonne) is dropped before the
mean is taken (only applied when a group has ≥ 3 sites).

## Exact products in the aggregate (as of 2026-07-29)

### Sunflower — 20 L  *(2 sites — the thinnest oil; 20 L sunflower is mostly login-gated)*
- JJ Foodservice — *KTC High Oleic Sunflower BIB 20L* — £44.00
- Everest Cash & Carry — *KTC Sunflower Oil 20L* — £27.81

### Rapeseed — 20 L  *(3 sites)*
- JJ Foodservice — *Pride Rapeseed Oil Drum 20L* — £33.99
- Brakes (Sysco) — *Sysco Classic Extended Life Rapeseed 20L* — £31.99
- Marfast — *KTC Chef's Choice Rapeseed 20L* — £42.99

### Soybean (pure veg, 100% soya) — 20 L  *(5 sites)*
- JJ Foodservice — *KTC Pure Vegetable Oil 20L* — £29.00
- YesDeal UK — *KTC Vegetable Oil 20L* — £27.99
- Surulere Foods — *KTC Vegetable Oil 20L* — £30.99
- Bakers Street — *KTC Vegetable Oil BIB 20L* — £22.50
- CK Fast Foods — *KTC Vegetable Oil 20L Drum* — £25.39

### Palm — 12.5 kg  *(6 sites — widest cross-seller spread)*
- JJ Foodservice — *JJ SG Palm Oil 12.5kg* — £21.79
- JJ Foodservice — *Palmax SG Palm Oil 12.5kg* — £22.25
- JJ Foodservice — *Frymax Solid Palm Frying Oil 12.5kg* — £29.99
- Asetena Pa — *SG Palm Oil 12.5kg* — £32.98
- Asetena Pa — *Palmax SG Palm Oil 12.5kg* — £30.36
- Brakes (Sysco) — *Palmax Refined Palm Oil 12.5kg* — £43.01

### Olive (extra virgin) — 5 L  *(7 sites)*
- JJ Foodservice — *Antica Tradizione EVOO 5L* — £30.99
- JJ Foodservice — *Filippo Berio EVOO 5L* — £36.99
- Brakes (Sysco) — *Barbera EVOO 5L* — £35.94
- Brakes (Sysco) — *Sysco Classic EVOO 5L* — £27.05
- Costco UK — *Filippo Berio EVOO 5L* — £31.99
- PJ Martinelli — *Filippo Berio EVOO 5L* — £29.50
- Foodomarket — *UK EVOO 5L wholesale index* — £35.43

## Reliability of daily collection

- **Auto-scrapable** (Shopify storefronts, Costco, Foodomarket, CK Fast Foods, Everest,
  Bakers Street, Asetena, PJ Martinelli): re-read daily by `scripts/scrape.py`.
- **Gated** (JJ Foodservice, Brakes/Sysco, Marfast): HTTP 403 to bots or a trade login,
  refreshed via `scripts/add_observation.py` (assisted top-up).
- No public price API / push feed exists, so collection is **daily best-effort scrape +
  manual top-up**, not real-time. (Wholesale oil prices move over days/weeks.)

## No blends

UK "vegetable oil" is often a rapeseed/palm blend — excluded. Only KTC Pure Vegetable
(100% soya) is used, as *Soybean*. Long-life "frying oil" blends and olive pomace blends
are excluded.

## Candidate UK sites to broaden coverage (prices login-gated — add via top-up)

Bidfood, Bestway Wholesale, Magna Foodservice, Country Range, Cater-Choice, KFF, Woods
Foodservice, Adams Food Service, Turner Price, Philip Dennis, Colbeck, Thompsons, Ram's
Cash & Carry, Variety Foods, Ofoodi, The Warehouse Distribution, Kent Foods Direct.
