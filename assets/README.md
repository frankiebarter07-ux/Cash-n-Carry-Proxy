# Brand assets — drop the real files here

The dashboard is wired for Olleco branding but ships **without the logo**, because
the machine that built it has no access to olleco.co.uk. Until the files below
exist, the header falls back to the word **OLLECO** set in the brand colour — the
page is not broken, it is just unbranded.

## 1. The logo

Copy these two files from the Olleco brand pack into this folder, named exactly:

| File | Which version | Used on |
|---|---|---|
| `olleco-logo-white.png` | the reversed / white-out mark | the dark theme (the default) |
| `olleco-logo.png` | the standard full-colour mark | the light theme |

If the brand pack only has one version, copy the same file to both names — the mark
may sit awkwardly on one background, but nothing breaks.

- **PNG or SVG both work.** If you use SVG, keep the same filenames with `.svg` and
  change the two `src` attributes in `index.html`.
- Aim for roughly **150–400 px wide** and a transparent background. The header
  renders it at 26 px tall, so anything smaller will look soft on a retina screen.
- Commit the files to the repository. The publish workflow copies this whole folder
  to the live site, so they appear automatically on the next deploy.

## 2. The brand colour

Open `index.html` and find the block marked `OLLECO BRAND`. Replace the placeholder
in **both** palettes:

```css
--brand:#3faa53;   /* dark theme  — replace with the brand pack value */
--brand:#1f7a3d;   /* light theme — a darker shade for white backgrounds */
```

Every accent on the page derives from `--brand`: the rule under the header, the
selected buttons, the section headings and the wordmark. One edit rebrands the
whole dashboard.

**The two values in there now are placeholders**, chosen to sit correctly against
this palette. They are not Olleco's specified colours and should not be treated as
such. Take the exact hex from the brand pack.

The up/down colours are deliberately **not** brand colours — they are the market
convention (green up, red down) and should stay legible rather than on-brand.
