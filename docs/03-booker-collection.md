# 3. Collecting Booker

Four of the fifteen tracked SKUs are Booker's. They are **not** being collected
automatically, and this is the one deliberate gap in the system.

## Why it does not collect itself

Booker returns `HTTP 403 Access Denied` to GitHub's runners because those run on
**datacenter IP addresses**, which bot filters distrust by default. This was tested
rather than assumed: 11 different endpoints were probed — including `robots.txt`,
which has no JavaScript and no login — and all 11 were blocked. The filtering is on
the IP, not on the path or the parser.

Two things follow:

- **No code change can fix it.** `scripts/booker_probe.py` re-runs that test any
  time you want to check.
- **The parsing is already solved.** Booker embeds its pricing as JSON in the
  product page, and `price_from_booker_embedded()` in `scripts/adapters.py` reads
  the collection price from it, with unit tests. Give it a readable page and it
  works immediately.

## What happens meanwhile

Booker's last known price carries forward for **7 days**, then it lapses out of the
average and the dashboard says so. The index becomes an honest four-seller index
rather than a five-seller one with a frozen member. **Nothing breaks if you do
nothing.**

---

# Option A — Enter the prices by hand (works today)

No setup, no machine, no security decision. Someone reads four public web pages and
types four numbers, as often as they care to.

1. **Actions → Add Booker prices → Run workflow**
2. Type the four collection prices
3. **Run**

It records them, rebuilds the index and commits. Re-running replaces that day's
Booker rows, so a typo is fixed by submitting again.

The four pages are listed in `config/targets.json` under `Booker`.

**Realistic advice:** if nobody will reliably do this, do not pretend otherwise.
A four-seller index that is honest beats a five-seller one propped up by a number
somebody typed a fortnight ago.

---

# Option B — A self-hosted runner (full automation)

A machine on Olleco's own internet connection registers with GitHub and runs the
Booker step. Its requests then leave from an ordinary UK business IP, and Booker
serves the real page.

## ⚠️ Read this first — it is a security decision

**GitHub's guidance: only use self-hosted runners with private repositories.**

A self-hosted runner executes whatever the repository's workflows contain, on that
machine, inside your network. If the repository is **public**, anyone can open a
pull request that modifies a workflow — and a stranger's code then runs on a PC
inside the Olleco network. The runner is also not ephemeral by default, so anything
left behind persists.

**This repository is currently public**, because that is what GitHub Pages requires
on the free plan (see `04-hosting.md`).

So you must choose:

| You want | Then |
|---|---|
| The public dashboard URL | Stay public. **Do not attach a runner.** Use Option A. |
| Automated Booker | Make the repository private first, then follow the steps below. You lose the public URL unless the org is on GitHub Team. |
| **Both** | Put the org on **GitHub Team** (~£3.40/user/month). Pages publishes from private repos on paid plans, so you get the URL *and* a private repo that is safe to attach a runner to. |

The third row is the one worth asking for. It removes the trade-off entirely.

## Steps (only once the repository is private)

**You need:** an always-on Windows PC on the normal office connection — not behind
a VPN that exits via a datacenter, or Booker blocks it again for the same reason.

### 1. Get a registration token

Repository → **Settings → Actions → Runners → New self-hosted runner → Windows**.
Copy the token shown under *Configure*. It expires after one hour.

### 2. Run the installer

On that PC: **Start → PowerShell → right-click → Run as administrator**

```powershell
cd path\to\Cash-n-Carry-Proxy
.\tools\setup-windows-runner.ps1 -Token AXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

The script installs Git and Python if missing, downloads the current runner,
registers it, and installs it as a Windows service set to start on boot — so it
survives power cuts and Windows Update reboots. Its header explains how to remove it
later.

### 3. Switch the Booker job on

**Settings → Secrets and variables → Actions → Variables → New repository
variable**, named `BOOKER_RUNNER`, value `true`.

**This step is not optional.** Until the variable is set, the Booker job is
*skipped* — deliberately. A job pointed at a runner label that matches nothing does
not fail, it **queues for up to 24 hours**, and because the publishing job waits on
it the entire index would stop updating every day. A skipped job satisfies that wait
instantly.

### 4. Verify without waiting for the morning

**Actions → Test adapters → Run workflow**, set `runner` to `self-hosted`. The four
Booker SKUs should return prices via `embedded-json:collectOE` instead of
*Access Denied*.

### If Booker still 403s from that PC

Its connection is being filtered too. Confirm by trying a different network — a
phone hotspot is the quickest test. This is unlikely on an ordinary office line.

## Hardening, if you must run this on a public repo

Not recommended, but defensible with all three of:

1. Register the runner with **`--ephemeral`** so it is destroyed after every job
2. Put the machine on a **guest VLAN with outbound internet only** — the collector
   needs nothing from the internal network, so a compromise gets someone a
   throwaway box
3. **Settings → Actions → General → Fork pull request workflows → Require approval
   for all outside collaborators**

With all three the residual risk is a stranger burning CPU on an isolated PC. That
is a judgement for whoever owns Olleco's security, not for the person who wrote
this.

## Maintenance

The runner updates itself. If the PC is replaced, run the script again. If it goes
offline, the other four sellers still collect and Booker lapses after 7 days.
