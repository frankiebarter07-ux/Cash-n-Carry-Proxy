# 1. Transfer ownership to Olleco

**Do this first. Nothing else in this folder matters if it is skipped.**

The repository currently sits on an individual's personal GitHub account
(`frankiebarter07-ux`). That account owns the code, the schedule, the published
dashboard and the secrets. When that person's access ends, Olleco loses all of it,
and there is no way to recover it without them.

Budget 20 minutes. You need someone who can create repositories in the Olleco
GitHub organisation.

---

## Before you start

If Olleco has no GitHub organisation, create one first: **github.com/organizations/plan**
→ choose **Free** (enough for everything here) → name it e.g. `olleco`.

Decide who will own this afterwards. It should be a team or a named role, not a
person — the whole point of this document is that individuals leave.

---

## Step 1 — Transfer the repository

1. The current owner opens the repo → **Settings**
2. Scroll to the bottom, **Danger Zone** → **Transfer ownership**
3. Type the repository name to confirm, and enter the Olleco organisation as the
   new owner
4. An organisation admin accepts the transfer

The repository, its history, issues and Actions workflows all move together.

## Step 2 — Re-add the secrets

**Secrets do not transfer.** They are deliberately left behind, and the daily job
will fail silently on email until they are restored.

Go to **Settings → Secrets and variables → Actions** on the *new* repository and
add:

| Secret | Where the value comes from |
|---|---|
| `SMTP_HOST` | your email provider — see `02-email-sender.md` |
| `SMTP_PORT` | usually `587` |
| `SMTP_USER` | provider login |
| `SMTP_PASSWORD` | provider key |
| `REPORT_FROM` | the verified sending address |
| `REPORT_TO` | comma-separated recipients |

If a `BOOKER_RUNNER` variable was set, re-add it under the **Variables** tab.

Treat the transfer as the moment to move off any personal email account —
`02-email-sender.md` covers it.

## Step 3 — Re-enable GitHub Pages

Pages settings do not survive a transfer either.

1. **Settings → Pages → Build and deployment → Source: GitHub Actions**
2. **Actions → Publish dashboard → Run workflow**

⚠️ **The URL changes.** It becomes
`https://<org-name>.github.io/Cash-n-Carry-Proxy/`. Anyone holding the old link
needs the new one. Do the transfer *before* circulating the address widely.

## Step 4 — Give people access

**Settings → Collaborators and teams.** Grant a team rather than individuals:

| Role | Who | Can |
|---|---|---|
| **Admin** | 1–2 people | change settings, secrets, visibility |
| **Write** | whoever maintains it | edit adapters, enter Booker prices by hand |
| **Read** | everyone else | view the data and the dashboard |

## Step 5 — Make sure alerts reach a human

This is the step most often missed, and without it the system dies quietly:
collecting perfectly, telling nobody.

A **monitored company account** — a shared mailbox or a team account, not a
person — must **Watch → All Activity** on the repository. Two things arrive that
way:

- **Failure alerts** — an issue labelled `collection-failure` on any broken run
- **Price reports** — comments on the *📈 Cooking oil price reports* thread

## Step 6 — Check it still runs

**Actions → Daily oil prices → Run workflow.** It should finish green and commit
an updated `data/observations.csv`. If it fails, `HANDOVER.md` §6 has the triage
table.

---

## Afterwards

- [ ] Repository owned by the Olleco organisation
- [ ] Secrets re-added, and no longer pointing at a personal mailbox
- [ ] Pages re-enabled, new URL circulated
- [ ] Team access granted by role
- [ ] A monitored account is watching the repository
- [ ] A manual run completed green
