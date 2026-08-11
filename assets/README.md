# Brand assets

## 1. The logo — in place ✅

| File | What it is | Used for |
|---|---|---|
| `olleco-logo.png` | horizontal mark, 260×107, transparent | the header on both dashboards, and the browser-tab icon |

Supplied by the owner on 2026-08-11. To replace it, overwrite the file keeping the
same name — nothing else needs changing.

**PNG only, by preference.** The square JPEG version was dropped: JPEG cannot hold
transparency, so its white background is baked in and shows as a white block on any
coloured ground.

The tab icon is the same wide mark, which browsers scale to fit a square — legible
but small. If a sharper tab icon is wanted later, add a **square** PNG with
transparent padding as `assets/olleco-icon.png` and point the `<link rel="icon">` at
it in `index.html` and `scripts/render_static.py`.

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

## 3. The typeface — Arial

Both dashboards are set in **Arial**, a brand face, with Helvetica as the fallback.

Nothing is downloaded, which means **neither page makes a single external request**.
They render identically on a locked-down corporate network, work offline from a
saved copy, and there is no CDN that can break them — worth more here than a more
distinctive face, given nobody will be maintaining this day to day.

An earlier build used Open Sans from Google Fonts. That has been removed: with Arial
first in the stack the webfont would never have rendered anyway, so the request was
pure cost. If the brand pack turns out to specify Open Sans for digital work, put it
back by adding the `<link>` tags and putting `"Open Sans"` ahead of Arial in `--face`
in `index.html`, and in the `body` rule in `scripts/render_static.py`.

**If the brand pack names a different face**, check its licence before using it here:
most commercial fonts need a separate webfont licence, and this site is public.
