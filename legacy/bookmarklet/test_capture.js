// Offline regression test for the price-capture bookmarklet.
// Runs tools/bookmarklet.txt against a mock JJ-style rapeseed listing in a headless
// DOM and checks it keeps 20L product names + pack prices while dropping per-litre
// figures, promo badges and wrong sizes.
//
//   npm install jsdom      (one-time)
//   node tools/test_capture.js
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const HTML = `<!doctype html><html><body><div class="results">
  <div class="tile"><a href="/offers" class="tile-title">Mix &amp; Save - ANY COMBINATION</a>
    <a href="/product/OIL055" class="product-name">Pride Rapeseed Oil Drum 1x20L</a>
    <span>£1.70 per litre</span><span>Collection: £33.99</span><span>Delivery: £35.99</span></div>
  <div class="tile"><a href="/product/OIL068" class="product-name">KTC Chef's Choice Rapeseed Oil Drum 1x20L</a>
    <span>£1.67 per litre</span><span>Collection: £33.49</span><span>Delivery: £35.49</span></div>
  <div class="tile"><a href="/product/OIL999" class="product-name">JJ Extended Life Rapeseed Oil Drum 1x10L</a>
    <span>£1.90 per litre</span><span>Collection: £18.99</span></div>
  <div class="tile"><a href="/product/OIL116" class="product-name">JJ Extended Life Rapeseed Oil BIB 1x20L</a>
    <span>£1.62 per litre</span><span>Collection: £32.49</span></div>
</div></body></html>`;

const code = fs.readFileSync(path.join(__dirname, "bookmarklet.txt"), "utf8").replace(/^javascript:/, "");
const dom = new JSDOM(HTML, { url: "https://www.jjfoodservice.com/search?sizeOrCut=1x20l", runScripts: "outside-only" });
dom.window.eval(code);
const out = (dom.window.document.querySelector("#__pxcap textarea") || {}).value || "";
console.log(out + "\n");

const must = ["Pride Rapeseed Oil Drum 1x20L | £33.99", "KTC Chef's Choice Rapeseed Oil Drum 1x20L | £33.49", "JJ Extended Life Rapeseed Oil BIB 1x20L | £32.49"];
const mustNot = ["£1.70", "£1.67", "1x10L", "£18.99", "Mix & Save"];
let ok = true;
must.forEach(function (s) { if (out.indexOf(s) < 0) { ok = false; console.error("MISSING:", s); } });
mustNot.forEach(function (s) { if (out.indexOf(s) >= 0) { ok = false; console.error("SHOULD NOT APPEAR:", s); } });
console.log(ok ? "PASS" : "FAIL");
process.exit(ok ? 0 : 1);
