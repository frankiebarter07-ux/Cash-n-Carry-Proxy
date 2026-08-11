# Brand assets

## 1. The logo — one file needed

Save the Olleco mark here as exactly:

```
assets/olleco-logo.png
```

Until it exists the header shows the word **olleco** set in the brand colours. The
page is not broken, just unbranded.

**Only one file is required.** The standard dark-teal mark works on both themes: on
the dark ground it is placed on a white lockup (a rounded white panel behind the
mark), which is ordinary brand practice and avoids needing a reversed version.

- PNG or SVG. For SVG, name it `olleco-logo.svg` and change the two `src`
  attributes — one in `index.html`, one in `scripts/render_static.py`.
- Roughly **300–600 px wide**, transparent background. It renders at 26 px tall, so
  anything smaller looks soft on a retina screen.
- Commit it. The publish workflow copies this folder to the live site, so it appears
  on the next deploy.

**Uploading from a phone or iPad:** save the image, then on GitHub go to the
`assets` folder → *Add file* → *Upload files* → drop it in → *Commit changes*. Make
sure the committed filename is exactly `olleco-logo.png` — GitHub keeps whatever
name the file already had.

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
