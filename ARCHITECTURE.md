# Architecture

How this collects UK cash-and-carry cooking-oil prices reliably, and how to grow it
into a company-scale service. Written as a build guide, not a description of what
exists — some of it is deliberately ahead of the current code.

## 1. What the system is

A daily price index for **rapeseed** and **soybean ("vegetable")** oil at UK B2B
cash-and-carry sellers, used as a **movement proxy** — the question it answers is
*"are wholesale oil prices moving, and who moved first?"*, not *"what will I pay?"*.

Scope today: **15 SKUs × 5 sellers**, all 20 L, split by pack format (bag-in-box /
drum). All prices are **publicly visible — no login is used anywhere**.

## 2. The two rules that keep the data honest

Both come from real failures in this project, not theory.

**Rule 1 — a price must come from a labelled source.**
Accept a number only from JSON-LD `offers.price`, an internal JSON API field, or a
CSS selector known to be the price element. **Never** from a bare `£` regex over the
page. *Why:* a regex fallback once recorded a stray figure from a login-walled page
as if it were the product price, and it sat in the index for days.

**Rule 2 — fail loudly, never silently.**
If an adapter can't find a labelled price, it must record *nothing* and raise a
visible error. *Why:* the Booker scraper returned "no price found" on every run for
days while the dashboard still looked healthy.

Corollary: **every price carries provenance** — which method read it, and when. A
value whose method is unknown is not trustworthy.

## 3. Data model

```
observation  = one SKU, one seller, one date, one price
  date, oil, brand, format(bib|drum), channel, source, product, url,
  pack_value, pack_unit, price_gbp, notes
```

Aggregation is deliberately two-stage, then smoothed:

1. **Within a seller** — average that seller's SKUs into one *seller price*, so a shop
   listing four SKUs doesn't outvote a shop listing one.
2. **Across sellers** — drop any seller more than **2 standard deviations** from the
   cross-seller mean (only when ≥ 3 sellers), then average the rest.
3. **Carry-forward (LOCF)** — a seller that didn't report today keeps its last known
   price, so the index moves only on *real* price changes, never on missing data.

Normalisation: prices are standardised to the oil's fixed pack (20 L) and also
expressed in **£/tonne** using published densities, so oils are comparable.

**VAT:** UK cooking oils are zero-rated, so inc-VAT = ex-VAT. Prices are used as
listed. (Verified: the identical KTC 20 L was £30.69 inc-VAT at one seller and
£30.49 ex-VAT at another — a 20% gap would have been obvious.)

## 4. Fetch strategy — a tier per site, best first

| Tier | Method | Stability | Use when |
|------|--------|-----------|----------|
| 1 | **Internal JSON API** | Highest — survives redesigns | The site is an SPA calling its own endpoint (find via DevTools → Network → Fetch/XHR) |
| 2 | **JSON-LD** `offers.price` | High | Server-rendered store (WooCommerce, Magento, Shopify) |
| 3 | **CSS selector + Playwright** | Medium — breaks on redesign | JS-rendered price, no API found |
| 4 | *(never)* bare-£ regex | — | Prohibited by Rule 1 |

Expected route per seller (confirm with `tools/check_protection.sh`):

- **Magna Foodservice** — WooCommerce → JSON-LD *(easiest, build first)*
- **Marfast** — Magento-style, likely server-rendered → JSON-LD or selector
- **Booker** — direct product URLs, JS-rendered → Playwright
- **Brakes (Sysco)** — Playwright; check for Akamai
- **JJ Foodservice** — React SPA, 403s plain fetch → find the JSON API *(highest value)*

**JJ caveat:** its URLs are **branch-specific** (`/London-Enfield/`) and prices vary
by branch. Keep the branch fixed or the series drifts for no real reason.

## 5. The adapter interface

One module per seller. Small, independently testable, no shared cleverness.

```python
class Adapter:
    name: str                      # "Magna Foodservice"
    def fetch(self, sku) -> Quote  # raises AdapterError if no labelled price
```

```python
@dataclass
class Quote:
    price_gbp: float
    method: str        # "json-ld" | "json-api" | "selector:<sel>"
    source_url: str
    fetched_at: datetime
```

Rules for every adapter:
- return a `Quote` or **raise** — never return a guess;
- record `method` so provenance is auditable;
- one adapter's failure must not abort the others.

## 6. Validation gate (before anything is stored)

A quote is rejected — and alerted on — if it:
- has no `method` (Rule 1);
- sits outside a plausible band (currently £15–£60 for a 20 L pack);
- moves more than **±20 %** from that SKU's last price → *held for review*, not
  published (this catches both a mis-parse and a genuine shock, which deserve a human
  glance either way);
- is identical across *every* seller on a day where none were expected to change —
  a classic sign of scraping the same error page.

## 7. Anti-bot, self-hosted (no scraping API)

Volume here is ~15 page loads/day, which never trips rate limits. So the goal is
*not tripping detection*, not out-running it:

1. **Don't need evasion** — prefer the internal JSON API; it's usually unprotected.
2. **Egress from a non-datacenter IP** — office line, home box, or a 4G/5G dongle.
   Datacenter IPs (cloud VMs, CI runners) are what Cloudflare flags first. This is
   the single highest-leverage change and costs nothing.
3. **Look like a browser** — `curl_cffi` (`impersonate="chrome"`) fixes the TLS/JA3
   fingerprint for non-JS fetches; real Chrome headed under `xvfb` (via `nodriver`
   or `patchright`) for JS pages. Headless-shell is the most detectable option.
4. **Persist cookies** — reuse `cf_clearance` and session cookies; solve rarely,
   fetch cheaply.
5. **Be polite** — low concurrency, randomised delays, honour the site's terms.

Explicitly *not* recommended: hammering a site that is actively blocking you. If a
seller can't be read politely, drop it or collect it manually.

## 8. Scale & operations

- **Storage:** CSV is fine at this size; move to **Postgres** when history matters
  (one row per seller/SKU/date, plus `method` and `verified`).
- **Runtime:** Docker container, identical on laptop and server.
- **Scheduling:** cron → **Prefect/Dagster** when you want retries, backfills and
  per-adapter observability.
- **Secrets:** if logins ever become necessary, use a secrets manager (Vault, AWS/GCP
  Secret Manager) — never `.env` in the repo. *Currently no credentials are used.*
- **Monitoring:** track each adapter's success rate; alert when one returns nothing
  two runs running. That alone would have caught the Booker failure on day one.

## 9. Interfaces

- `dashboard_static.html` — no-JavaScript view (renders in mobile/embedded viewers
  that strip `<script>`). Chart + per-SKU price list grouped by brand + price-change
  tables.
- `index.html` — interactive: unit toggle (£/unit ↔ £/tonne), per-oil on/off,
  tap-a-point for the SKU breakdown. Needs a normal browser.
- `data/series.json` — the computed series, including `breakdown` (every SKU at every
  seller) and `changes` (today + trailing 7 days, with who moved).

## 10. Known gaps

- Adapters are not yet wired to the live sites; the current baseline is
  browser-verified by hand (2026-08-10).
- Booker's bib/drum mapping is inferred from source-list order — verify against page
  titles.
- No alerting yet; failures are visible only in CI logs.
- `data/observations_legacy.csv` holds the pre-verification history, including
  values that could not be confirmed. Do not merge it back into the live series.
