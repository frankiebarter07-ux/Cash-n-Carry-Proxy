# Price-capture bookmarklet

A one-tap tool that reads the visible prices on a seller's page **in your own browser**
and shows them in a copy box. Because it runs in your session (your IP, your login), it
works on login-gated / bot-protected sites (JJ, Brakes, Booker…) that the CI scraper
can't reach.

- `price-capture.js` — readable source.
- `build_bookmarklet.py` — turns it into the one-line `javascript:` bookmarklet.
- `bookmarklet.txt` — the generated one-liner to install.

## Install on iPhone/iPad (Safari)

1. Copy the entire contents of `bookmarklet.txt` (starts with `javascript:`).
2. In Safari, bookmark **any** page (tap Share → Add Bookmark → Save).
3. Bookmarks → Edit → open that bookmark → **replace its address** with the copied
   `javascript:…` text → Done. Rename it "Grab prices".

## Install on desktop

Drag a link whose `href` is the `bookmarklet.txt` contents onto your bookmarks bar, or
create a new bookmark and paste the text as the URL.

## Use

1. Open a seller's product or **category** page (a category page grabs many SKUs at once).
2. Tap the **Grab prices** bookmark.
3. A box lists everything it found (`Product | £price`). Tap **Copy**.
4. Paste it back to the tracker — the rapeseed/soybean 20L lines get added and the chart
   rebuilds. (The capture includes the source site, URL and date.)

Notes: on catering sites each tile often shows both a collection and a delivery price, so
you may see two lines per product — the collection (lower) one is what we use. Review the
box before copying.
