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

### 0.2 Public dashboard **or** automated Booker — you cannot have both
This is a real fork in the road, so decide it deliberately.

To serve the dashboard at a URL, GitHub Pages needs the repository to be **public**
(Pages cannot publish from a private repo on the Free plan). But GitHub's own
guidance is explicit:

> Only use self-hosted runners with private repositories. Forks of a public
> repository can run dangerous code on your self-hosted runner machine.

That runner would sit **inside the company network**. So:

| If you want… | Then… |
|---|---|
| A public dashboard URL | Repo public, Pages on. **Do not attach the self-hosted runner.** Collect Booker by hand (§4), or let it lapse and run a four-seller index. |
| Automated Booker collection | Repo stays private, runner attached (§3). View the index via `SUMMARY.md` and the committed dashboards instead of a URL. |

**The chosen path is the public dashboard** (§4a). Booker therefore stays on manual
entry. If the company later prefers automated Booker over a public URL, make the repo
private again *before* registering any runner.

Before publishing, know what becomes public: every price observation, the config, the
docs and the full history. There are **no credentials in the repository** — SMTP
details live in Actions secrets, which are never exposed to forks — so publishing
leaks no secret, only the data itself.

### 0.3 Point alerts *and reports* at a company address
Two things now arrive by GitHub notification, so this step is what makes the whole
system reach a human:

- **Failures** — an issue labelled `collection-failure`, on any broken run.
- **Price reports** — a comment on the *📈 Cooking oil price reports* thread,
  whenever a seller moves a price, plus a Monday digest (§5).

Have a **monitored company account** watch this repository (*Watch → All Activity*).
Without it, both go unread and the index dies quietly — collecting perfectly, telling
nobody.

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

## 3. Installing the self-hosted runner (for Booker)

> ⚠️ **Only do this if the repository is PRIVATE.** See §0.2 — a self-hosted runner
> on a public repo can be made to run a stranger's code on that machine. If you have
> published the dashboard, skip this section entirely and use §4 instead.

Needed only for Booker. Budget 15 minutes, once.

**Why:** Booker returns *403 Access Denied* to GitHub's cloud runners because they use
datacenter IP addresses. The prices are public — the problem is only *where the
request comes from*. Running that one step from an ordinary office connection fixes
it. Nothing else about the system changes: same repo, same workflows, same logs.

**Machine:** any always-on Windows PC on the normal office connection. It wakes for a
minute or two each morning and is otherwise idle. It must **not** sit behind a VPN
that exits via a datacenter, or Booker will block it again for the same reason.

```powershell
# 1. On GitHub: Settings -> Actions -> Runners -> New self-hosted runner -> Windows
#    Copy the registration token (it expires after one hour).

# 2. Start -> "PowerShell" -> right-click -> Run as administrator, then:
cd path\to\Cash-n-Carry-Proxy
.\tools\setup-windows-runner.ps1 -Token AXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**3. Switch the Booker job on.** *Settings → Secrets and variables → Actions →
Variables → New repository variable*, named `BOOKER_RUNNER`, value `true`.

Until that variable is set, the Booker job is **skipped** and the index publishes the
other four sellers. This is deliberate and it is not a nicety: a job whose runner
label matches nothing does not fail, it *queues* — for up to 24 hours — and because
the publishing job waits on it, the whole index would stop updating every day. A
skipped job satisfies that wait instantly. So never point the Booker job at
`self-hosted` without a runner actually registered.

The script installs Git and Python if missing, downloads the current runner,
registers it, and installs it as a Windows service set to start on boot — so it
survives power cuts and Windows Update reboots. Read its header before running: it
also explains how to remove it later.

**Verify without waiting for the morning:** *Actions → Test adapters → Run workflow*,
set `runner` to `self-hosted`. The four Booker SKUs should return prices via
`embedded-json:collectOE` instead of *Access Denied*.

**If Booker still 403s from that PC**, its connection is being filtered too. Confirm
by trying a different network (a phone hotspot is the quickest test). This is
unlikely on an ordinary office line.

**Security — worth understanding before you attach it.** A self-hosted runner
executes whatever code the repository's workflows contain. That is safe here because
the repository is private and only your team can change it. Two rules follow:

- **Do not make the repository public** while the runner is attached.
- **Do not attach this runner to a repository that accepts outside pull requests** —
  a stranger's pull request could otherwise run code on that machine.

**Maintenance:** the runner updates itself. If the PC is replaced, run the script
again on the new one. If it goes offline, the daily job still publishes the other
four sellers, and Booker drops out of the index after 7 days (§2) rather than
sitting frozen.

**On another operating system?** The same applies with `./config.sh` and
`sudo ./svc.sh install && sudo ./svc.sh start` instead of the PowerShell script, and
`runs-on: self-hosted` already matches any platform. One change is required: in
`.github/workflows/daily-prices.yml`, the Booker step calls `python` rather than
`python3` because Windows has no `python3`; both work on macOS and Linux after
`setup-python`, so it needs no edit.

---

## 4. If you never install a runner

Booker can be entered by hand — the prices are public and take a minute to read.

*Actions → **Add Booker prices** → Run workflow* → type the four collection prices →
Run. It records them, rebuilds and commits. Re-running replaces that day's Booker
rows, so a typo is fixed by submitting again.

The other four sellers keep collecting automatically regardless.

---

## 4a. Publishing the dashboard, and emailing the report

### Publish the dashboard to a URL (once, ~5 minutes)

1. **Make the repository public** — *Settings → General → Danger Zone → Change
   visibility*. Read §0.2 first; this rules out the self-hosted runner.
2. *Settings → Pages → Build and deployment → **Source: GitHub Actions***.
3. *Actions → **Publish dashboard** → Run workflow*.

The URL appears in the run summary and under *Settings → Pages*, and looks like
`https://<owner>.github.io/Cash-n-Carry-Proxy/`. It republishes automatically after
every daily collection, so it is never stale.

What is published is a fixed list — `index.html`, `dashboard_static.html`, and the
series plus observations data. Nothing else, so adding a file to the repo can never
accidentally put it on the site.

> Anyone with the link can read it. Pages sites cannot be password-protected on any
> plan below Enterprise Cloud. If that becomes unacceptable, host the same `site/`
> folder on Cloudflare Pages behind Cloudflare Access instead — free for up to 50
> named users — and make the repository private again.

### Email the report to people without GitHub (once, ~10 minutes)

Watchers already get GitHub notifications. For anyone else — a buyer, a procurement
manager — add these as **repository secrets** (*Settings → Secrets and variables →
Actions → Secrets*):

| Secret | What it is |
|---|---|
| `SMTP_HOST` | e.g. `smtp.office365.com`, `smtp.gmail.com`, `smtp.resend.com` |
| `SMTP_PORT` | `587` for STARTTLS (default), `465` for implicit TLS |
| `SMTP_USER` | the mailbox or API username |
| `SMTP_PASSWORD` | an **app password** or API key — never someone's login password |
| `REPORT_FROM` | address to send from (defaults to `SMTP_USER`) |
| `REPORT_TO` | comma-separated recipients |

**Use a shared company mailbox, not a personal account.** A personal mailbox stops
working the day that person leaves, which is exactly the failure this handover exists
to prevent.

Until these are set, the email step prints "not configured" and the run stays green —
so nothing breaks if the company never wants email. Once set, a *failed* send fails
the run loudly, because a report that quietly never arrives is worse than none.

To test without waiting for a price to move:

```bash
python3 scripts/render_summary.py --report-out r.md --report-html r.html --force-report
SMTP_HOST=… SMTP_USER=… SMTP_PASSWORD=… REPORT_TO=you@company.com \
  python3 scripts/send_report.py --html r.html --text r.md --dry-run
```

Drop `--dry-run` to actually send one to yourself.

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
