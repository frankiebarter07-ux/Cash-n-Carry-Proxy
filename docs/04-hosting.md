# 4. Where this is hosted

**Nothing needs doing today.** The dashboard is live and republishes itself. This
document exists so that whoever inherits it knows what the arrangement is, what it
costs, and when it would be worth changing.

## What is running now

| | |
|---|---|
| **Dashboard** | GitHub Pages — `https://<owner>.github.io/Cash-n-Carry-Proxy/` |
| **Collection** | GitHub Actions, 06:00 UTC daily |
| **Storage** | the repository itself — CSV and JSON, no database |
| **Email** | SMTP, from whichever mailbox the secrets point at |
| **Cost** | **£0** |

Published by `.github/workflows/deploy-pages.yml` after every successful collection,
so the URL is never stale. The site is assembled from a **fixed file list**, so
adding a file to the repository can never accidentally publish it.

Both pages make **no external requests at all** — no fonts, no CDN, no analytics.
They render identically on a locked-down corporate network and work offline from a
saved copy. Worth preserving; it is the main reason this cannot quietly break.

## The one thing to understand

**GitHub Pages cannot publish from a private repository on the free plan.** That is
why this repository is public — it was a deliberate trade, not an oversight.

Public means: every price observation, the config, the docs, the full commit
history and the report thread are world-readable. **There are no credentials in the
repository** — SMTP details live in Actions secrets, which are encrypted and never
exposed to forks — so publishing leaks no secret, only the data.

It also means the self-hosted Booker runner is off the table (`03-booker-collection.md`).

## When to change it, and to what

Only three situations justify moving:

### 1. The data should not be public

Then the free plan is not enough. Two ways out:

- **GitHub Team** (~£3.40/user/month) — repo private, Pages still publishes. The
  site remains publicly reachable by URL; only the source closes. **This also
  unblocks the Booker runner**, so it solves two problems at once, and is what to
  ask for if you ask for anything.
- **Cloudflare Pages + Cloudflare Access** — free for up to 50 named users, repo
  private, and the site itself is login-gated. Genuinely private, at the cost of a
  second vendor account. Point it at the repository and set the build output to the
  same files `deploy-pages.yml` publishes.

Note that Pages sites cannot be password-protected on any plan below Enterprise
Cloud. "Private repo" and "private website" are different things.

### 2. Someone wants a proper domain

`prices.olleco.co.uk` instead of a `github.io` address. Add a `CNAME` file and a DNS
record — GitHub documents it, and it works on the free plan. Cosmetic, and it makes
the link easier to circulate internally.

### 3. It outgrows a CSV

Not soon. It is 15 rows a day. At a few years of history, or if you add many more
sellers, move the observations to Postgres and keep everything else. `ARCHITECTURE.md`
§8 sketches this.

## What not to do

- **Do not move it to a server that needs maintaining.** The reason this survives an
  unattended year is that there is nothing to patch, restart or renew. A VM would
  add all three.
- **Do not add a CDN, web font or analytics script.** Zero external requests is a
  feature.
- **Do not put subscriber emails in the repository.** It is public, and git history
  is permanent. `HANDOVER.md` §4b explains where they go instead.

## If Pages ever stops updating

1. **Actions → Publish dashboard** — is the latest run green?
2. If it never ran: the trigger only fires on changes to `index.html`,
   `dashboard_static.html`, `data/series.*`, `assets/**` or the workflow itself.
3. If it failed at *deploy-pages*: check **Settings → Pages → Source** is still
   **GitHub Actions**. This resets if the repository is transferred
   (`01-transfer-ownership.md`).
4. Run it manually to confirm the fix.
