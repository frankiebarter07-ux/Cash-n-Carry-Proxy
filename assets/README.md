# Brand assets

## 1. The logo — in place ✅

| File | What it is | Used for |
|---|---|---|
| `olleco-logo.png` | horizontal mark, 260×107, transparent | the header on both dashboards |
| `olleco-square.jpg` | square mark, 400×400, white background | the browser-tab icon |

Both were supplied by the owner on 2026-08-11. To replace either, overwrite the file
keeping the same name — nothing else needs changing.

The mark is dark teal, so on the dark theme it sits on a **white lockup** — a rounded
white panel behind it. That is ordinary brand practice where background contrast is
insufficient, and it means the standard mark serves both themes with no reversed
version needed. On the light theme the lockup is removed.

If a reversed (white-out) version is ever preferred on dark, add it and swap the
`src` in `index.html`, then remove the `background`/`padding` rule on `.brand img`.

## 2. The brand colours — done

Applied in `index.html` and `scripts/render_static.py`:

| Hex | Name | Where it is used |
|---|---|---|
| `#00433F` | Cyprus | the dark ground (taken down in value), and the accent on white |
| `#CBD300` | Rio Grande | the header rule in both themes, and the accent on dark |
| `#FFFFFF` | White | panels and type on the light theme, and the logo lockup |

Contrast checked against WCAG: body text 15.3:1 on dark, 11.2:1 on light, weakest
tone 4.58:1.

Up/down are deliberately **not** brand colours. They are the market convention
(green up, red down), held clear of the lime in hue so a price rise cannot read as a
brand highlight.

## 3. The typeface — Open Sans

Loaded from Google Fonts in both dashboards. It is **the only external dependency
in the whole system**; if the CDN is blocked, the fallback stack renders and nothing
else is affected.

To remove that dependency — worth doing if the company's network filters CDNs, or
if you simply want the site self-contained:

1. Download Open Sans from <https://fonts.google.com/specimen/Open+Sans> and put the
   `.woff2` files in `assets/fonts/`.
2. Replace the `<link>` tags with an `@font-face` block pointing at them.
3. Add `assets/fonts/` to the copy step in `.github/workflows/deploy-pages.yml`.

Open Sans is licensed under the SIL Open Font License, so embedding and self-hosting
are both permitted. **If the brand pack specifies a different face**, check its
licence before putting it on the site: most commercial fonts (Gotham, Brandon,
Avenir and similar) require a separate webfont licence, and this site is public.
