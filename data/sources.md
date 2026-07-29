# Price sources

**UK prices only — this is a UK index.** Every price is the **single standalone pack
price** as listed on a UK seller, **including any current discount** — a reliable shop
dropping its price is the signal this index exists to catch, so sale prices are kept, not
reverted to RRP. £/tonne is computed in `scripts/process.py` from published oil densities.

**Reliable / established sellers only.** Small online shops and loss-leaders are excluded
from the aggregate (see the excluded list below). **No blends. No supermarket D2C retail.**

**One fixed pack size per oil** (enforced in `process.py` — any observation at a
different size is rejected):

| Oil / fat | Fixed size |
|-----------|-----------|
| Sunflower | 20 L |
| Rapeseed | 20 L |
| Soybean (pure veg, 100% soya) | 20 L |
| Palm | 12.5 kg |
| Olive (extra virgin) | 5 L |
| Beef dripping (refined) | 12.5 kg |

Prices are aggregated **across multiple sellers per oil**; any observation more than
**2 standard deviations** from the cross-seller mean (in £/tonne) is dropped before the
mean is taken (only applied when a group has ≥ 3 sellers).

## Exact products in the aggregate (as of 2026-07-29)

### Sunflower — 20 L  *(1 reliable seller — needs more; 20L sunflower is mostly trade-login gated)*
- JJ Foodservice — *KTC High Oleic Sunflower BIB 20L* — £44.00

### Rapeseed — 20 L  *(3)*
- JJ Foodservice — *Pride Rapeseed Oil Drum 20L* — £33.99
- Brakes (Sysco) — *Sysco Classic Extended Life Rapeseed 20L* — £31.99
- Marfast — *KTC Chef's Choice Rapeseed 20L* — £42.99

### Soybean (pure veg, 100% soya) — 20 L  *(2)*
- JJ Foodservice — *KTC Pure Vegetable Oil 20L* — £29.00
- CK Fast Foods — *KTC Vegetable Oil 20L Drum* — £25.39

### Palm — 12.5 kg  *(4)*
- JJ Foodservice — *JJ SG Palm Oil 12.5kg* — £21.79
- JJ Foodservice — *Palmax SG Palm Oil 12.5kg* — £22.25
- JJ Foodservice — *Frymax Solid Palm Frying Oil 12.5kg* — £29.99
- Brakes (Sysco) — *Palmax Refined Palm Oil 12.5kg* — £43.01

### Olive (extra virgin) — 5 L  *(6)*
- JJ Foodservice — *Antica Tradizione EVOO 5L* — £30.99
- JJ Foodservice — *Filippo Berio EVOO 5L* — £36.99
- Brakes (Sysco) — *Barbera EVOO 5L* — £35.94
- Brakes (Sysco) — *Sysco Classic EVOO 5L* — £27.05
- Costco UK — *Filippo Berio EVOO 5L* — £31.99
- Foodomarket — *UK EVOO 5L wholesale index* — £35.43

### Beef dripping (refined & deodorised) — 12.5 kg  *(2)*
- JJ Foodservice — *KTC Halal Beef Dripping 12.5kg* — £28.00
- Cater-Choice — *KTC Halal Beef Dripping 12.5kg* — £26.99

*Beef dripping = refined beef tallow (same trade product), tracked as one line. 12.5kg is
the most common single-block size (KTC, Henry Colbeck, Q Bronze) vs 20kg 4×5kg boxes.*

## Reliable sellers used

JJ Foodservice, Brakes (Sysco UK), Costco UK, Marfast, CK Fast Foods, Cater-Choice, and
the Foodomarket UK wholesale index.

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
