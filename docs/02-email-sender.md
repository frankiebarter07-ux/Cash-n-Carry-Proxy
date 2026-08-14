# 2. Change where the reports are sent from

**This is a security item, not housekeeping.** The reports currently leave from a
personal email account belonging to someone who no longer works on this. That means:

- the app password sitting in this repository's secrets belongs to a private
  individual's mailbox
- the reports stop the moment that password is revoked, the account is secured, or
  the person changes their settings — and nobody will be told why
- Olleco is sending business correspondence from an address it does not control

Budget 20 minutes. You need someone who can add repository secrets, and either an
IT contact or five minutes to create a free account.

---

## How sending works here

The daily job runs `scripts/send_report.py`, which speaks plain SMTP using six
values. Change those values and the sender changes. **There is nothing to edit in
the code** — no provider is hard-coded.

| Secret | What it is |
|---|---|
| `SMTP_HOST` | the mail server |
| `SMTP_PORT` | `587` for STARTTLS (default), `465` for implicit TLS |
| `SMTP_USER` | the login |
| `SMTP_PASSWORD` | an app password or API key — **never** a person's login password |
| `REPORT_FROM` | the address recipients see |
| `REPORT_TO` | comma-separated recipients |

Set them at **Settings → Secrets and variables → Actions**.

---

## Option A — Microsoft 365 shared mailbox (recommended)

Olleco already runs Microsoft 365, so this costs nothing extra: **shared mailboxes
carry no licence fee.** It sends from a real `@olleco.co.uk` address, so
deliverability is correct and nothing lands in Junk. It is owned by the company, and
IT already knows how to manage it.

1. Ask IT for a shared mailbox, e.g. `oilindex@olleco.co.uk`
2. Ask them to **enable SMTP AUTH** on that mailbox — Microsoft disables it by
   default, and this is the whole ask
3. Set the secrets:

| Secret | Value |
|---|---|
| `SMTP_HOST` | `smtp.office365.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `oilindex@olleco.co.uk` |
| `SMTP_PASSWORD` | the app password IT provides |
| `REPORT_FROM` | `oilindex@olleco.co.uk` |

The same mailbox then also receives subscription requests — see `HANDOVER.md` §4b.

## Option B — Brevo (free, no IT needed)

Use this if IT is slow. Free tier is 300 emails/day; this system sends a handful a
month.

1. Create an account at **brevo.com**
2. **Transactional → Settings → Configuration → SMTP relay** →
   *Generate a new SMTP key*. Copy the **login** and the **key** — the key is shown
   once. It must be an **SMTP key**, not an API key (API keys start `xkeysib-`).
3. **Senders, Domains & Dedicated IPs → Senders → Add a sender**, and click the
   confirmation link Brevo emails you. Brevo rejects unverified senders.
4. **Turn off *Authorised IPs*** in the same Settings area. On by default for new
   accounts, it only accepts connections from IPs you list — and GitHub's runners
   get a different IP every run, so no list can ever work. The symptom is
   `525 5.7.1 Unauthorized IP address`.
5. Set the secrets:

| Secret | Value |
|---|---|
| `SMTP_HOST` | `smtp-relay.brevo.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | the SMTP login (`…@smtp-brevo.com`) |
| `SMTP_PASSWORD` | the SMTP key |
| `REPORT_FROM` | the verified sender address |

To send from `@olleco.co.uk` rather than a personal address you must verify the
domain with DNS records — which needs IT anyway. If you are asking IT for DNS
records, Option A is less work and a better result.

---

## Test it before trusting it

**Actions → Test email → Run workflow.** Put your own address in `to` so a trial
cannot surprise the distribution list.

The workflow **fails** if it cannot send, and names the missing setting. A green run
means a message genuinely left. Check the log for:

```
Emailed 1 recipient(s): …
```

## When it fails

| Message | Cause |
|---|---|
| `Cannot send: missing …` | a secret is unset. `REPORT_TO` alone is only the recipient list — sending also needs a mailbox to send *through* |
| `525 Unauthorized IP address` | Brevo IP authorisation is on — step 4 above |
| `535 Authentication failed` | wrong key, an API key instead of an SMTP key, or a space pasted into `SMTP_PASSWORD` |
| `553` / `Sender address rejected` | `REPORT_FROM` is not a verified sender |
| Sends fine, arrives in Junk | sender domain does not match the recipient's — Option A fixes this |

## Afterwards

- [ ] `SMTP_*` and `REPORT_FROM` point at a company mailbox
- [ ] No personal account referenced in any secret
- [ ] The old personal app password **revoked at the provider** — removing the
      GitHub secret does not invalidate it
- [ ] *Test email* run green, message received
