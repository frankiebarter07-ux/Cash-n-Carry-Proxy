# Handover

Everything needed to run and maintain the cooking-oil price index **without the
person who built it**. Read this first.

---

## 0. Do these before anything else

Four tasks, each with its own step-by-step guide in [`docs/`](docs/). The first two
are blockers: the system works without them, but Olleco cannot *keep* it.

| # | Task | Guide | Why |
|---|---|---|---|
| 1 | **Transfer ownership to Olleco** | [`docs/01-transfer-ownership.md`](docs/01-transfer-ownership.md) | The repo is on a personal account. When that access ends, Olleco loses the data, the schedule and the dashboard. |
| 2 | **Move email off a personal account** | [`docs/02-email-sender.md`](docs/02-email-sender.md) | Reports currently send via a private individual's mailbox, using their app password. |
| 3 | Decide how Booker is collected | [`docs/03-booker-collection.md`](docs/03-booker-collection.md) | Four of fifteen SKUs. Manual entry works today; automation needs a security decision. |
| 4 | Understand the hosting | [`docs/04-hosting.md`](docs/04-hosting.md) | Nothing to do — but know what it is and when to change it. |

**And the step people forget:** a monitored company account must
**Watch → All Activity** on the repository. Failure alerts and price reports both
arrive that way. Without it the system collects perfectly and tells nobody.

---

## 1. What this is

A daily price index for **rapeseed** and **vegetable (soybean)** oil across five UK
cash-and-carry sellers — 15 SKUs, all 20 L, split by bag-in-box vs drum. It answers
*"are wholesale oil prices moving, and who moved first?"*

| Seller | SKUs | Collected by |
|---|---|---|
| JJ Foodservice | 3 | Cloud (JSON-LD) ✅ verified |
| Brakes (Sysco) | 2 | Cloud (selector) ✅ verified |
| Marfast | 3 | Cloud (Collection label) ✅ verified |
| Magna Foodservice | 3 | Cloud (Collection label) ✅ verified |
| **Booker** | 4 | **Self-hosted runner only** — blocks datacenter IPs |

No logins or credentials are used anywhere. All prices are publicly visible.

---

## 2. How it runs

`.github/workflows/daily-prices.yml`, 06:00 UTC daily:

1. **collect-cloud** (GitHub runner) — 11 SKUs from the four reachable sellers.
2. **collect-booker** (self-hosted runner) — Booker's 4 SKUs. `continue-on-error`,
   so if the machine is off, nothing else breaks.
3. **build-and-commit** — merges both, rebuilds the index, commits.
4. **alert-on-failure** — opens an issue if anything went wrong.

**If the self-hosted runner is offline**, Booker's last known price carries forward
for up to **7 days**, then Booker lapses: it stops counting towards the index and is
shown on the dashboard as *"stopped reporting — not counted"*. It rejoins by itself
the moment it reports again.

That limit matters. Carried indefinitely, a permanently blocked seller would sit
frozen at its final price and still pull the average — making *"we have no data"*
look exactly like *"the price did not move"*, which is the one thing this index must
never do. Change the window via `MAX_CARRY_DAYS` in `scripts/process.py`.

---

## 3. Booker

Not collected automatically: Booker blocks GitHub's datacenter IPs at its CDN edge.
Its last price carries forward for 7 days, then it lapses out of the average and the
dashboard says so.

Two routes, and the choice is a security decision because this repository is public:
**[`docs/03-booker-collection.md`](docs/03-booker-collection.md)**.

---

## 4. If you never install a runner

Booker can be entered by hand — the prices are public and take a minute to read.

*Actions → **Add Booker prices** → Run workflow* → type the four collection prices →
Run. It records them, rebuilds and commits. Re-running replaces that day's Booker
rows, so a typo is fixed by submitting again.

The other four sellers keep collecting automatically regardless.

---

## 4a. The dashboard and the reports

- **Where it is hosted, and when to change that:**
  [`docs/04-hosting.md`](docs/04-hosting.md)
- **Changing the sending mailbox:** [`docs/02-email-sender.md`](docs/02-email-sender.md)

**Testing email at any time:** *Actions → Test email → Run workflow*, with your own
address in `to`. It fails with a named list if a setting is missing, so a green run
always means a message really went out.

---

## 4b. Subscriptions — and why the addresses are NOT in this repository

The dashboard has a **Receive market reports** form. It composes an email to
`oilindex@olleco.co.uk` asking for an address to be added, and whoever runs the
index appends it to the **`REPORT_TO` secret**.

> ⚠️ **Set `SUBSCRIBE_TO` in `index.html` to a real, monitored mailbox.**
> `oilindex@olleco.co.uk` is a placeholder. If that address does not exist,
> subscription requests bounce and nobody finds out.

**Why it works this way, rather than storing addresses in the repo:**

1. **This repository is public.** Anything committed here is world-readable, by
   anyone, permanently — git history keeps it even after deletion. Subscriber email
   addresses are personal data; publishing them would be a UK GDPR breach and would
   expose customers to spam and phishing. There is no "secure place" in a public
   repo. There is no such thing.
2. **A GitHub Pages site is static.** There is no server to receive a form, so a
   page here *cannot* write to the repository however the form is built.

The distribution list therefore lives in the `REPORT_TO` Actions secret, which is
encrypted, never printed in logs, and not exposed to forks. That is the secure
place, and it already exists.

**Adding a subscriber:** *Settings → Secrets and variables → Actions → `REPORT_TO`
→ Update*, and append the address, comma-separated. Takes about twenty seconds.

**If subscriptions become frequent enough that this is a chore**, the options in
increasing order of effort are: a private mailing list or Microsoft 365 distribution
group set as the single `REPORT_TO` value (best — the company manages membership
with its own tools, and no code changes); a hosted form provider such as Formspree
writing to a private inbox; or making this repository private again and adding a
small serverless endpoint. **Do not** solve it by committing addresses to the repo.

---

## 5. Reading the output

**The easiest way, and the one to show people:** the published dashboard URL
(§4a) — it needs no GitHub account and no download. Failing that, open
[`SUMMARY.md`](SUMMARY.md) in the repository. GitHub renders it, so it reads properly
on a phone with nothing to download — current prices, what moved today, the trailing
week, and any seller that has stopped reporting. It is rebuilt on every run.

**You will also be emailed when something moves.** The daily job posts to a single
issue thread, *📈 Cooking oil price reports*, and GitHub emails everyone watching the
repository. If the SMTP secrets are set (§4a), the same report is emailed to a named
list of addresses as well, for people who do not use GitHub. It posts only when a seller actually changed a listed price, plus a
Monday digest so a quiet week still proves the system is alive.

> **Silence is information here.** No email means no seller moved a price — not that
> the collection failed. Failures open a *separate* issue labelled
> `collection-failure`. If you would rather hear every day regardless, remove the
> `if:` condition on the *Notify watchers* step in `daily-prices.yml`; be aware that
> daily "nothing changed" mail is exactly what trains people to filter the folder.

To receive the emails: **Watch → All Activity** on the repository (§0.3). Anyone who
should see prices needs this; it is the only step that makes the reports reach a human.

- **`dashboard_static.html`** — open in any browser. Works with JavaScript disabled
  and in embedded viewers. Chart, per-SKU price list by seller, and price-change
  tables (today + trailing 7 days, showing who moved).
- **`index.html`** — interactive version (£/unit ↔ £/tonne toggle, tap a point for
  the SKU breakdown, same price-change tables). Needs a normal browser.
- **`data/observations.csv`** — the raw record, one row per SKU per day.
- **`data/series.json`** — computed series, breakdown and changes.

---

## 6. When something breaks

**A `collection-failure` issue appears.** Read which job failed.

| Symptom | Likely cause | Fix |
|---|---|---|
| `collect-booker` failed | Runner offline / machine off | Check the PC is on; `services.msc` → the `actions.runner.*` service should be *Running* |
| One seller `✗ no labelled price` | They redesigned their page | Run *Test adapters* with diagnostics; update that adapter's selectors |
| A seller returns 403 / "Access Denied" | They started blocking datacenter IPs | Move that seller to the self-hosted runner (`--only`), or collect manually |
| Prices look wrong but jobs are green | Adapter reading the *wrong* price element | See §7 — this has happened three times |

**Diagnosing a broken adapter:** *Actions → Test adapters → Run workflow*, put the
seller's name in the `diagnose` box. It prints every price-like element on the page
with its CSS path and surrounding label, so the correct selector can be written from
evidence rather than guesswork.

---

## 7. The one failure mode to watch for

**A green run is not necessarily a correct run.** Three times, adapters returned a
perfectly valid, properly-labelled price that was simply the *wrong* price:

- **Marfast** renders two prices under an identical CSS class — delivery (£34.29)
  and collection (£32.79). The obvious `meta[itemprop=price]` returns the delivery
  one.
- **Magna** publishes £28.99 in its JSON-LD while displaying £27.99 on the page —
  stale structured data.
- **Magna again**, after the label fix: the right label on the *wrong product*. A
  page also lists related items, each with its own "Collection £x", and one of those
  (£12.49) was a tighter match than the real one.

All three are fixed: prices are read from the *displayed* page (`prefer_rendered`),
anchored on the word **Collection**, and searched only inside the main product block.
Note that the same confusion catches humans, not just parsers: the hand-entered
baseline for Magna's KTC Vegetable Oil Tin 20 L was £28.99, which is that page's
*delivery* price. Corrected to the collection price, £27.99, on 2026-08-10 — the
reason is written into that row's `notes` column in `data/observations.csv`.

**Every few weeks, spot-check two or three SKUs against the live sites.** Read the
`method` column in `data/adapter_run.json` while you do: `label:Collection@scope` and
`label:Collection@product-block` are trustworthy, `label:Collection@page` means the
scoping fell through to a whole-page search and the value deserves a closer look.
Guard rails catch nonsense (implausible values, >20% jumps held for review) but they
cannot catch a plausible wrong number.

---

## 7a. The index contains unverified pre-index rows

At the owner's request the series starts **9 August 2026**, backfilled from
`data/observations_legacy.csv`. Those rows predate the labelled-source rule and are
marked `UNVERIFIED pre-index backfill` in the `notes` column. Specifically:

One row survives the backfill: **Magna soybean £28.99, 9 August.** It is that page's
**delivery** price — the product block reads `Delivery £28.99 Collection £27.99` — and
this index is defined on collection. CK Fast Foods' rows were removed at the owner's
instruction and are not in the index.

**Consequences to be aware of when reading the chart:**

- 9 August rests on **one seller**; 10 August onwards on five. The step between them
  is a change of constituents, not a market move.
- There is **no rapeseed observation on 9 August** — none exists in any source. The
  rapeseed series therefore begins 10 August, and that is correct rather than missing.

To remove the backfill, delete the rows whose `notes` begin `UNVERIFIED` from
`data/observations.csv` and re-run `scripts/process.py`.

---

## 8. Design rules — do not remove these

They exist because of real incidents.

1. **A price is only accepted from a labelled source** (JSON-LD `offers.price`, a
   JSON API field, or a known price selector) — **never** a bare `£` regex over the
   page. A regex fallback once recorded a delivery-threshold figure from a blocked
   page as a product price, and it sat in the index for days.
2. **Fail loudly.** No labelled price means *no data written*, plus a visible error.
   An earlier scraper returned nothing for days while the dashboard looked healthy.
3. **Carry-forward, not gap-filling — but bounded.** A seller that doesn't report
   keeps its last price so the index moves only on real changes, for at most
   `MAX_CARRY_DAYS` (7). After that it lapses out of the average rather than sitting
   frozen and making *no data* look like *no change*. Do not remove the bound.
4. **Per-seller averaging before cross-seller averaging**, so a shop listing four
   SKUs doesn't outvote one listing a single SKU.

Full reasoning in `ARCHITECTURE.md`.

---

## 9. Adding a seller or SKU

1. Add it to `config/targets.json` (seller, oil, format, product, URL).
2. Add an adapter class in `scripts/adapters.py` if the seller is new. Copy the
   closest existing one. In practice most B2B sites show a delivery price *and* a
   collection price together, so start from `MagnaAdapter`: set
   `price_label = "Collection"` and give `label_scope` the seller's main product
   container. JSON-LD alone has twice been the wrong number.
3. Run *Test adapters* with the seller in the `diagnose` box **first** — it prints
   every price-like element with its CSS path and surrounding label, so you write the
   adapter from evidence instead of guessing.
4. Cross-check against the live site before trusting it. A parseable price is not
   necessarily the right price (§7).

---

## 10. Cost

£0. GitHub Actions is free for this volume (~2 minutes/day), and GitHub Pages is free
for public repositories. Optional costs, only if you want them:

- a small always-on PC for the Booker runner (and only on a **private** repo, §0.2);
- an email provider, if the company mailbox cannot do SMTP — free tiers are ample at
  a handful of messages a month.
