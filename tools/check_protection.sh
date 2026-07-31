#!/usr/bin/env bash
# Identify which bot-protection / WAF (if any) each seller site runs.
# Run this from your OWN machine -- it needs normal internet access.
#
#   bash tools/check_protection.sh
#
# Reads the response headers and cookies and matches them against known
# fingerprints. Nothing is scraped; it only makes one HEAD/GET per site.

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

SITES=(
  "https://www.jjfoodservice.com/"
  "https://www.brake.co.uk/"
  "https://www.booker.co.uk/"
  "https://marfast.co.uk/"
  "https://www.magnafoodservice.co.uk/"
)

identify() {
  local h="$1"
  local hits=""
  grep -qiE '^server:.*cloudflare|^cf-ray:'            <<<"$h" && hits+="Cloudflare "
  grep -qiE 'cf_clearance|__cf_bm'                      <<<"$h" && hits+="Cloudflare-BotMgmt "
  grep -qiE '^server:.*akamai|ak_bmsc|bm_sv|^x-akamai'  <<<"$h" && hits+="Akamai "
  grep -qiE 'datadome'                                  <<<"$h" && hits+="DataDome "
  grep -qiE 'incap_ses|visid_incap|^x-iinfo'            <<<"$h" && hits+="Imperva/Incapsula "
  grep -qiE '_px[a-z]*=|^x-px'                          <<<"$h" && hits+="PerimeterX/HUMAN "
  grep -qiE '^x-sucuri'                                 <<<"$h" && hits+="Sucuri "
  grep -qiE '^server:.*(awselb|cloudfront)|^x-amz-cf'   <<<"$h" && hits+="AWS-CloudFront "
  grep -qiE '^x-shopify|^server:.*shopify'              <<<"$h" && hits+="Shopify "
  grep -qiE '^x-powered-by:.*wordpress|wp-content'      <<<"$h" && hits+="WordPress/Woo "
  [ -z "$hits" ] && hits="(no known WAF signature)"
  echo "$hits"
}

for url in "${SITES[@]}"; do
  host=$(sed -E 's#https?://([^/]+).*#\1#' <<<"$url")
  echo "=============================================================="
  echo "  $host"
  echo "=============================================================="
  hdr=$(curl -sS -A "$UA" -L --max-time 25 -o /tmp/body.$$ -D - "$url" 2>&1)
  code=$(grep -m1 -oE 'HTTP/[0-9.]+ [0-9]{3}' <<<"$hdr" | tail -1)

  echo "  status      : ${code:-no response}"
  echo "  server      : $(grep -i '^server:' <<<"$hdr" | tail -1 | tr -d '\r' | cut -c1-60)"
  echo "  protection  : $(identify "$hdr")"

  # A JS-challenge page is small and says "just a moment" / "checking your browser"
  if grep -qiE 'just a moment|checking your browser|enable javascript and cookies|attention required' /tmp/body.$$ 2>/dev/null; then
    echo "  !! CHALLENGE PAGE returned (interstitial, not real content)"
  fi
  # Does the raw HTML already contain a price? (i.e. no JS needed)
  if grep -qE '£[0-9]+\.[0-9]{2}' /tmp/body.$$ 2>/dev/null; then
    echo "  prices in raw HTML: YES (server-rendered -- easy)"
  else
    echo "  prices in raw HTML: no (JS-rendered, or gated/homepage)"
  fi
  # JSON-LD present?
  if grep -qi 'application/ld+json' /tmp/body.$$ 2>/dev/null; then
    echo "  JSON-LD present   : YES (preferred parse target)"
  fi
  rm -f /tmp/body.$$
  echo
  sleep 2
done

echo "Tip: run again against a PRODUCT url (not the homepage) to see whether that"
echo "page server-renders its price. And use DevTools > Network > Fetch/XHR on the"
echo "live page to spot an internal JSON API -- that beats scraping HTML entirely."
