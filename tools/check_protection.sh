#!/usr/bin/env bash
# Check every tracked product URL: is it reachable, is it bot-protected, and is the
# price present in the raw HTML (or JSON-LD)?
#
# Run from your OWN machine (needs normal internet):
#     bash tools/check_protection.sh
#
# Reads the 15 SKUs from config/targets.json. One request per URL, 2s apart.
# Nothing is stored -- this only reports what each site returns.

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGETS="$ROOT/config/targets.json"

command -v python3 >/dev/null || { echo "python3 required"; exit 1; }

identify() {
  local h="$1" hits=""
  grep -qiE '^server:.*cloudflare|^cf-ray:'           <<<"$h" && hits+="Cloudflare "
  grep -qiE 'cf_clearance|__cf_bm'                     <<<"$h" && hits+="CF-BotMgmt "
  grep -qiE '^server:.*akamai|ak_bmsc|bm_sv|^x-akamai' <<<"$h" && hits+="Akamai "
  grep -qiE 'datadome'                                 <<<"$h" && hits+="DataDome "
  grep -qiE 'incap_ses|visid_incap|^x-iinfo'           <<<"$h" && hits+="Imperva "
  grep -qiE '_px[a-z]*=|^x-px'                         <<<"$h" && hits+="PerimeterX "
  grep -qiE '^x-sucuri'                                <<<"$h" && hits+="Sucuri "
  grep -qiE '^x-shopify|^server:.*shopify'             <<<"$h" && hits+="Shopify "
  grep -qiE 'wp-content|^link:.*wp-json'               <<<"$h" && hits+="WordPress/Woo "
  [ -z "$hits" ] && hits="none detected"
  echo "$hits"
}

# seller<TAB>oil/format<TAB>url
python3 - "$TARGETS" <<'PY' > /tmp/_targets.tsv
import json,sys
d=json.load(open(sys.argv[1]))
for s,v in d["sellers"].items():
    for k in v["skus"]:
        print(f"{s}\t{k['oil']}/{k['format']}\t{k['url']}")
PY

pass=0; fail=0
while IFS=$'\t' read -r seller sku url; do
  body=$(mktemp)
  hdr=$(curl -sS -A "$UA" -L --max-time 30 -o "$body" -D - "$url" 2>&1)
  code=$(grep -m1 -oE 'HTTP/[0-9.]+ [0-9]{3}' <<<"$hdr" | tail -1 | awk '{print $2}')

  echo "----------------------------------------------------------------"
  echo "$seller  [$sku]"
  echo "  url        : ${url:0:78}"
  echo "  status     : ${code:-NO RESPONSE}"
  echo "  protection : $(identify "$hdr")"

  if grep -qiE 'just a moment|checking your browser|attention required|enable javascript and cookies' "$body" 2>/dev/null; then
    echo "  !! CHALLENGE PAGE (interstitial, not real content)"
  fi
  if grep -qE '£ ?[0-9]+\.[0-9]{2}' "$body" 2>/dev/null; then
    echo "  PRICE IN HTML: YES -> $(grep -oE '£ ?[0-9]+\.[0-9]{2}' "$body" | sort -u | head -4 | tr '\n' ' ')"
    pass=$((pass+1))
  else
    echo "  PRICE IN HTML: no (JS-rendered, gated, or blocked)"
    fail=$((fail+1))
  fi
  grep -qi 'application/ld+json' "$body" 2>/dev/null && echo "  JSON-LD    : present (preferred parse target)"
  grep -qiE 'add to (basket|cart)|sign in|log in to (see|view)' "$body" 2>/dev/null \
    && echo "  page hints : $(grep -oiE 'log in to (see|view) price|sign in|add to basket' "$body" | sort -u | head -2 | tr '\n' ' ')"

  rm -f "$body"
  sleep 2
done < /tmp/_targets.tsv

echo "================================================================"
echo "  $pass of $((pass+fail)) product pages exposed a price in raw HTML"
echo "================================================================"
echo "Next: for any that failed, open the page in Chrome > DevTools > Network >"
echo "Fetch/XHR and look for a JSON request carrying the price -- that endpoint is"
echo "far more stable than scraping HTML."
rm -f /tmp/_targets.tsv
