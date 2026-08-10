# Legacy — superseded, kept for reference only

Replaced by `scripts/adapters.py`. **Do not wire these back in.**

- `scrape.py` / `scrape_auth.py` — earlier scrapers. Both had a bare-£ fallback that
  recorded a stray number from a blocked page as a product price, and both could fail
  silently for days. `adapters.py` enforces labelled-source-only and fails loudly.
- `auth_sites.json` — login/scrape config from when we thought trade logins were
  needed. No credentials are used anywhere now; all prices are public.
- `products.json` — superseded by `config/targets.json`.
