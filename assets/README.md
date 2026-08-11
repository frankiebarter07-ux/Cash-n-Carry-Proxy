# Brand assets

## 1. The logo — in place ✅

| File | What it is | Used for | Status |
|---|---|---|---|
| `olleco-logo.png` | horizontal mark, transparent | the header on both dashboards | ✅ in place |
| `olleco-square.jpg` | square mark | the browser-tab icon | ✅ in place |

To replace either, overwrite the file keeping the same name — nothing else changes.

### One version is enough

The page is **light only**, so the standard mark sits directly on white with no
lockup and no reversed version needed. The `olleco-logo-white.png` slot described in
earlier revisions is gone along with the dark theme.

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
