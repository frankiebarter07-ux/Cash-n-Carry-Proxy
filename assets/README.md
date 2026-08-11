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

## 2. The brand colour — done

The official palette is already applied, in `index.html` and `scripts/render_static.py`:

| Hex | Name | Where it is used |
|---|---|---|
| `#00433F` | Cyprus | the dark ground (taken down in value), and the accent on white |
| `#CBD300` | Rio Grande | the header rule in both themes, and the accent on dark |
| `#FFFFFF` | White | panels and type on the light theme |

Contrast was checked against WCAG: body text is 15.3:1 on dark and 11.2:1 on light,
and the weakest tone on the page is 4.58:1. Nothing needs adjusting.

The up/down colours are deliberately **not** brand colours. They are the market
convention (green up, red down), held well clear of the lime in hue so a price rise
can never be mistaken for a brand highlight.
