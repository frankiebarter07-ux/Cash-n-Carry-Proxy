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
3. **Carry-forward (LOCF), bounded** — a seller that didn't report today keeps its
   last known price, so the index moves only on *real* price changes, never on missing
   data. But only for `MAX_CARRY_DAYS` (7): after that the seller **lapses** — dropped
   from the aggregate, still listed in the breakdown as "stopped reporting". Unbounded
   carry-forward would let a permanently blocked seller sit frozen at its last price
   and keep pulling the mean, so *"no data"* would render as *"no change"*. A seller
   rejoins automatically as soon as it reports again.

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

Actual route per seller, as built and verified on 2026-08-10:

| Seller | Route | Note |
|---|---|---|
| **JJ Foodservice** | JSON-LD | The React SPA was predicted to be hardest; it was the easiest. No JSON API needed. |
| **Brakes (Sysco)** | CSS selector | No Akamai challenge encountered. |
| **Marfast** | Collection label, scoped to `div.product-info-main` | Magento. JSON-LD/meta give the *delivery* price — do not use them here. |
| **Magna Foodservice** | Collection label, scoped to `div.summary.entry-summary` | WooCommerce. JSON-LD is stale *and* names the wrong figure; the predicted "easiest, build first" route was wrong twice over. |
| **Booker** | Embedded JSON in the product document | Parser done and tested; blocked by IP, needs the self-hosted runner. |

Worth noting how badly the *predictions* in this section scored: the site expected to
need an internal API needed none, and the two expected to be trivial produced every
wrong number in the project. Probe before designing.

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

## 9a. Live findings (2026-08-10, GitHub runner)

Final state after three rounds of fixes — **11/11 cloud SKUs read correctly**; the
only outstanding gap is Booker, which is an access problem, not a parsing one.

| Seller | Result | Diagnosis |
|--------|--------|-----------|
| **JJ Foodservice** | ✅ 3/3 via JSON-LD, matches the browser exactly | Working. The "hardest" site was the easiest. |
| **Brakes (Sysco)** | ✅ 2/2 via selector, matches exactly | Working. |
| **Marfast** | ✅ 3/3 via `label:Collection@scope` | Fixed. Was returning the *delivery* price (£34.29 not £32.79) — both prices share an identical class path, so only the label distinguishes them. |
| **Magna** | ✅ 3/3 via `label:Collection@scope` | Fixed in two steps: label anchoring, then scoping. Whole-page label search still returned other products' prices (£12.49 from a `Delivery £0.00` row; the bib's price on the drum page). |
| **Booker** | ❌ 0/4 | **HTTP 403, "Access Denied", ~400-byte edge block.** A probe of 11 endpoints — including `robots.txt` — was blocked 11/11, which proves the filter is on the *IP*, not the path. Parsing is already solved (§ `price_from_booker_embedded`); only access is missing. Needs a self-hosted runner. |

Three fixes, each invisible until specifically looked for:

1. **Delivery vs collection** — a properly labelled price that is the wrong price.
2. **A JS escaping bug** — the pattern was built as `new RegExp(label + '\s*…')` inside
   a JS *string* literal, where `\s` collapses to `s`. It matched nothing, so the label
   tier silently never fired and the adapter quietly used the next tier down.
3. **Unscoped label search** — the right label, on the wrong product. See §9b.

Each of these produced a green run. That is the whole reason for §2's Rule 2 and for
the validation gate: the gate *held* the £12.49, so no bad value was ever published.

Two lessons worth generalising:
1. **A successful fetch is not a correct fetch.** Marfast and Magna both returned a
   properly labelled price that was simply the wrong one. Validation must compare
   against a human-verified baseline, not just check the value is parseable.
2. **Structured data can be stale.** JSON-LD is stable and easy, but where it
   disagrees with the displayed price, the displayed price is what the buyer pays —
   hence the `prefer_rendered` flag on affected adapters.

## 9b. Why prices are anchored on the word "Collection"

Diagnostics showed these sellers render **both** prices together:

```
Delivery £28.99   Collection £27.99      <- Magna, KTC Veg BIB 20L
Collection £32.79 Delivery £34.29        <- Marfast (order varies)
```

Any position-based selector picks whichever comes first in the DOM, which is why
early runs recorded the *delivery* price and looked perfectly healthy doing it. The
distinguishing CSS was a Bootstrap spacing class (`ms-2` = delivery, `ms-3` =
collection) — that would break on any restyle.

So affected adapters set `price_label = "Collection"` and read the value that follows
that word in the tightest element containing both. **Business meaning is more durable
than layout.** The tier order is: label → rendered selector → static (JSON-LD/meta).

**The label alone is not enough — it must be scoped.** A product page also shows
*other* products (related items, recently viewed, basket), and each carries its own
"Collection £x". Searching the whole page returned Magna's £12.49 (a `Delivery £0.00
Collection £12.49` row belonging to something else) and, on the drum page, the *bib's*
£27.99. The search is therefore confined to one root, chosen in this order:

1. a per-seller `label_scope` selector (WooCommerce `div.summary.entry-summary`,
   Magento `div.product-info-main`) — a hint, skipped if it doesn't match;
2. **the smallest ancestor of the page's `<h1>` that also contains the label** — the
   main product block, defined semantically, so it works on untuned sellers too;
3. the whole page, as a last resort.

Which root was used is recorded in the price's method (`label:Collection@product-block`),
so a wrong value can be traced without re-running anything.

This tracks the **collection** price throughout, which is what the index is defined
on. If you ever want delivery instead, change `price_label` — do not change it per
seller, or the series stops being comparable.

## 10. Known gaps

- **Booker cannot be collected from CI** (datacenter IP blocked at the edge). It
  needs residential/business egress or manual entry — see §7 item 2 and §11.
- Booker's bib/drum mapping is inferred from source-list order — verify against page
  titles the first time the self-hosted runner reads it.
- The label tier depends on sellers continuing to use the word "Collection". If one
  relabels it ("Depot price", "Click & collect"), that adapter fails loudly rather
  than returning the wrong number — but it does need a human to update the label.
- Only one pack size (20 L) per oil, so the index cannot see price moves that show up
  first in smaller packs.
- `data/observations_legacy.csv` holds the pre-verification history, including
  values that could not be confirmed. Do not merge it back into the live series.

## 11. Collecting from a normal connection (the Booker problem)

Booker returns HTTP 403 "Access Denied" to GitHub's runners because they use
**datacenter IPs**. Every internet connection carries an IP address, and CDNs treat
them differently:

- **Residential / business IPs** — home broadband, an office line, a phone's 4G.
  Real people browse from these, so they are trusted.
- **Datacenter IPs** — cloud servers (GitHub Actions runs on Azure). No ordinary
  shopper browses from one, so bot filters block them by default.

The prices are genuinely public; the blocker is *where the request comes from*. Three
ways to solve it, in order of effort:

**A. Manual entry (works today, zero setup).**
`.github/workflows/add-booker-prices.yml` is a browser form: read the four Booker
pages on any device, type the prices in, press Run. It calls
`scripts/manual_prices.py`, rebuilds the index and commits. Re-running replaces that
day's Booker rows, so a typo is fixed by submitting again.

**B. Self-hosted runner (full automation, ~15 minutes' setup).**
Register a machine on your own network as a GitHub Actions runner
(*Settings → Actions → Runners → New self-hosted runner*). Same workflows, same logs
— but the requests now leave from a normal IP, so Booker serves the real page. Any
always-on machine works: an office PC, an old laptop, a mini-PC, a Raspberry Pi.
`tools/setup-windows-runner.ps1` does the whole install on Windows; HANDOVER.md §3
covers it, including the security rules that come with a self-hosted runner.

**C. Residential egress for a cloud collector.**
Keep the collector in the cloud but route its traffic through a residential
connection (office line, 4G/5G dongle, or a residential proxy). More moving parts;
only worth it at larger scale.

Recommended path: **A now, B when you want it hands-off.** Note that B also removes
the datacenter-IP risk for every other seller, so it is the single change that most
improves collection reliability overall.
