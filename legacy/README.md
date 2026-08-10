# Legacy — superseded, kept for reference only

Nothing in this folder is part of the running system. **Do not wire any of it back
in.** Each item is here because it was tried, found wanting, and replaced — the
reasons are recorded so the same ground isn't covered twice.

## Earlier scrapers

- `scrape.py` / `scrape_auth.py` — replaced by `scripts/adapters.py`. Both had a
  bare-`£` fallback that recorded a stray number from a blocked page as if it were a
  product price, and both could fail silently for days. `adapters.py` enforces
  labelled-source-only and fails loudly. This is Rule 1 and Rule 2 in
  `ARCHITECTURE.md` §2, and both rules exist because of these two files.
- `auth_sites.json` — login/scrape config from when trade logins looked necessary.
  **No credentials are used anywhere now**; every price tracked is public.
- `products.json` — superseded by `config/targets.json`.

## `add_observation.py`

A one-price-at-a-time CLI, superseded by `scripts/manual_prices.py` (which is wired
to the *Add Booker prices* workflow, validates input, and replaces a day's rows on
re-submission rather than duplicating them).

Note its examples reference `sunflower` and `Bestway` — neither exists in the index
any more, so running it as documented would fail or write a row the processor
ignores. Use the workflow instead.

## `bookmarklet/`

A browser bookmarklet that read prices from a page in your own session, so it could
reach sites that block cloud runners. It worked, but was rejected for good reasons:
it needs a human to visit each page, doesn't run reliably in mobile Safari, and a
`javascript:` bookmark is an awkward thing to ask a company to install and trust.

Its README still describes JJ, Brakes and Booker as needing manual capture. That is
now wrong: **JJ and Brakes collect automatically**, and Booker needs the self-hosted
runner (`HANDOVER.md` §3), not a bookmarklet.

The problem it was built for — reading a site that blocks datacenter IPs — is solved
properly by running the collector from a normal connection.
