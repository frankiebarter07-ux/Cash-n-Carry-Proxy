# Handover

Everything needed to run and maintain the cooking-oil price index **without the
person who built it**. Read this first.

---

## 0. Do these before anything else

Three items are blockers. The system works without them, but the company cannot
*keep* it.

### 0.1 Transfer the repository to the company — CRITICAL
The repo currently sits on an individual's personal GitHub account
(`frankiebarter07-ux`). When that person's access ends, the company loses the data,
the schedule and the ability to fix anything.

*Settings → General → Danger Zone → Transfer ownership* → a company organisation.

### 0.2 Make the repository private — CRITICAL if using a self-hosted runner
The repo is currently **public and forkable**. GitHub's own guidance:

> Only use self-hosted runners with private repositories. Forks of a public
> repository can run dangerous code on your self-hosted runner machine.

A self-hosted runner sits **inside the company network**. On a public repo, anyone
could open a pull request that executes code on it. **Make the repo private before
installing a runner.**

*Settings → General → Danger Zone → Change visibility → Private.*

### 0.3 Point failure alerts at a company address
The daily workflow opens a GitHub **issue** on any failure (label
`collection-failure`). Make sure a monitored company account watches the repo, or
those issues go unread and the index dies quietly.

---

## 1. What this is

A daily price index for **rapeseed** and **vegetable (soybean)** oil across five UK
cash-and-carry sellers — 15 SKUs, all 20 L, split by bag-in-box vs drum. It answers
*"are wholesale oil prices moving, and who moved first?"*

| Seller | SKUs | Collected by |
|---|---|---|
| JJ Foodservice | 3 | Cloud (JSON-LD) ✅ verified |
| Brakes (Sysco) | 2 | Cloud (selector) ✅ verified |
| Marfast | 3 | Cloud (rendered price) |
| Magna Foodservice | 3 | Cloud (rendered price) |
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

**If the self-hosted runner is offline**, Booker's last known price carries forward.
The index stays *correct*, just staler for that one seller. It does not go wrong.

---

## 3. Installing the self-hosted runner (for Booker)

Needed only for Booker. **Complete §0.2 first.**

**Machine:** anything always-on, on a normal office/home internet connection — an old
laptop, a mini-PC, a Raspberry Pi 4/5 (~£60). It must NOT be on a VPN that exits via
a datacenter, or Booker will block it again.

```bash
# 1. On GitHub: Settings -> Actions -> Runners -> New self-hosted runner
#    Follow the download/configure commands it shows you.

# 2. When asked for labels, accept the defaults (must include "self-hosted").

# 3. Install as a service so it survives reboots -- do NOT just run ./run.sh
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status      # should say "active (running)"

# 4. Python 3.12+ must be on the machine
python3 --version
```

**Verify:** run the *Test adapters* workflow with `runner` = `self-hosted`. Booker
should return prices instead of 403.

**Maintenance:** the runner auto-updates. If the machine is rebuilt or replaced,
repeat the above. If the runner is offline more than a day or two, you'll get issues.

---

## 4. If you never install a runner

Booker can be entered by hand — the prices are public and take a minute to read.

*Actions → **Add Booker prices** → Run workflow* → type the four collection prices →
Run. It records them, rebuilds and commits. Re-running replaces that day's Booker
rows, so a typo is fixed by submitting again.

The other four sellers keep collecting automatically regardless.

---

## 5. Reading the output

- **`dashboard_static.html`** — open in any browser. Works with JavaScript disabled
  and in embedded viewers. Chart, per-SKU price list by seller, and price-change
  tables (today + trailing 7 days, showing who moved).
- **`index.html`** — interactive version (£/unit ↔ £/tonne toggle, tap a point for
  the SKU breakdown). Needs a normal browser.
- **`data/observations.csv`** — the raw record, one row per SKU per day.
- **`data/series.json`** — computed series, breakdown and changes.

---

## 6. When something breaks

**A `collection-failure` issue appears.** Read which job failed.

| Symptom | Likely cause | Fix |
|---|---|---|
| `collect-booker` failed | Runner offline / machine off | Check the machine; `sudo ./svc.sh status` |
| One seller `✗ no labelled price` | They redesigned their page | Run *Test adapters* with diagnostics; update that adapter's selectors |
| A seller returns 403 / "Access Denied" | They started blocking datacenter IPs | Move that seller to the self-hosted runner (`--only`), or collect manually |
| Prices look wrong but jobs are green | Adapter reading the *wrong* price element | See §7 — this has happened twice |

**Diagnosing a broken adapter:** *Actions → Test adapters → Run workflow*, put the
seller's name in the `diagnose` box. It prints every price-like element on the page
with its CSS path and surrounding label, so the correct selector can be written from
evidence rather than guesswork.

---

## 7. The one failure mode to watch for

**A green run is not necessarily a correct run.** Twice, adapters returned a
perfectly valid, properly-labelled price that was simply the *wrong* price:

- **Marfast** renders two prices under an identical CSS class — delivery (£34.29)
  and collection (£32.79). The obvious `meta[itemprop=price]` returns the delivery
  one.
- **Magna** publishes £28.99 in its JSON-LD while displaying £27.99 on the page —
  stale structured data.

Both now read the *displayed* price (`prefer_rendered`). **Every few weeks, spot-check
two or three SKUs against the live sites.** Guard rails catch nonsense (implausible
values, >20% jumps are held for review) but they cannot catch a plausible wrong number.

---

## 8. Design rules — do not remove these

They exist because of real incidents.

1. **A price is only accepted from a labelled source** (JSON-LD `offers.price`, a
   JSON API field, or a known price selector) — **never** a bare `£` regex over the
   page. A regex fallback once recorded a delivery-threshold figure from a blocked
   page as a product price, and it sat in the index for days.
2. **Fail loudly.** No labelled price means *no data written*, plus a visible error.
   An earlier scraper returned nothing for days while the dashboard looked healthy.
3. **Carry-forward, not gap-filling.** A seller that doesn't report keeps its last
   price so the index moves only on real changes.
4. **Per-seller averaging before cross-seller averaging**, so a shop listing four
   SKUs doesn't outvote one listing a single SKU.

Full reasoning in `ARCHITECTURE.md`.

---

## 9. Adding a seller or SKU

1. Add it to `config/targets.json` (seller, oil, format, product, URL).
2. Add an adapter class in `scripts/adapters.py` if the seller is new (copy the
   closest existing one; most sites are JSON-LD or a selector).
3. Run *Test adapters* to confirm it reads the right price.
4. Cross-check against the live site before trusting it.

---

## 10. Cost

£0. GitHub Actions is free for this volume (~2 minutes/day). The only optional cost
is a small always-on machine for the Booker runner.
