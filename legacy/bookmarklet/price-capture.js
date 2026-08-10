// Price-capture bookmarklet (readable source).
// Run it on a seller's product or category page in your own browser. It reads the
// visible prices (JSON-LD first, then a DOM fallback) and shows them in a copy box
// so you can paste them back into the tracker. Uses YOUR browser session, so it works
// on login-gated / bot-protected sites that the CI scraper can't reach.
// Build the one-liner with: python3 tools/build_bookmarklet.py
(function () {
  var SRC = location.hostname.replace(/^www\./, "");
  var HREF = location.href;
  var found = [];
  var seen = {};
  // Only collect this pack size. Change WANT to e.g. "12.5kg" or "5L" to reuse.
  var WANT = "20L";
  var wn = (WANT.match(/[0-9.]+/) || ["20"])[0];
  var wu = WANT.replace(/[0-9.\s]/g, "").toLowerCase();
  var sizeRe = wu === "kg"
    ? new RegExp("(?:^|[^0-9])" + wn.replace(".", "\\.") + "\\s?kg\\b", "i")
    : new RegExp("(?:^|[^0-9])" + wn + "\\s?(?:l|lt|ltr|litre|litres)\\b", "i");
  function add(name, price) {
    name = (name || "").replace(/\s+/g, " ").trim();
    if (!sizeRe.test(name)) return;                    // wrong pack size -> skip
    price = parseFloat(String(price).replace(/[^0-9.]/g, ""));
    if (!name || !price || price < 1 || price > 2000) return;
    var key = name.toLowerCase() + "|" + price.toFixed(2);
    if (seen[key]) return;
    seen[key] = 1;
    found.push({ name: name.slice(0, 90), price: price.toFixed(2) });
  }
  document.querySelectorAll('script[type="application/ld+json"]').forEach(function (s) {
    try {
      (function walk(n) {
        if (!n || typeof n !== "object") return;
        if (Array.isArray(n)) return n.forEach(walk);
        if (/product/i.test(n["@type"] || "")) {
          var o = n.offers; o = Array.isArray(o) ? o[0] : o;
          if (o && o.price) add(n.name, o.price);
        }
        if (n.itemListElement) n.itemListElement.forEach(function (e) { walk(e.item || e); });
        for (var k in n) if (n[k] && typeof n[k] === "object") walk(n[k]);
      })(JSON.parse(s.textContent));
    } catch (e) {}
  });
  if (found.length < 2) {
    var BAD = /mix\s*&\s*save|any combination|add to|basket|clubcard|multibuy|offer|^\s*save\b/i;
    var PERL = /per\s*li|per\s*ltr|\/ltr|per\s*kg|\/kg/i;
    document.querySelectorAll("body *").forEach(function (el) {
      if (el.children.length) return;
      var txt = el.textContent || "";
      if (PERL.test(txt)) return;
      var prices = txt.match(/£\s?[0-9]{1,4}(?:\.[0-9]{2})?/g);
      if (!prices) return;
      var name = "", tile = el;
      for (var i = 0; i < 7 && tile; i++) {
        var cands = tile.querySelectorAll ? tile.querySelectorAll('a[href*="product"],a[href*="Product"],h1,h2,h3,h4,[class*=name],[class*=title],[class*=desc]') : [];
        for (var j = 0; j < cands.length; j++) {
          var t = (cands[j].textContent || "").replace(/\s+/g, " ").trim();
          if (t.length > 8 && !BAD.test(t)) { name = t; break; }
        }
        if (name) break;
        tile = tile.parentElement;
      }
      if (!name) return;
      prices.forEach(function (p) {
        var v = parseFloat(p.replace(/[^0-9.]/g, ""));
        if (v >= 5) add(name, v);
      });
    });
  }
  var today = new Date().toISOString().slice(0, 10);
  var lines = found.map(function (f) { return f.name + " | £" + f.price; });
  var text = "Source: " + SRC + "\nURL: " + HREF + "\nDate: " + today + "\n\n" + lines.join("\n");
  var old = document.getElementById("__pxcap"); if (old) old.remove();
  var box = document.createElement("div");
  box.id = "__pxcap";
  box.setAttribute("style", "position:fixed;inset:0;z-index:2147483647;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;font-family:-apple-system,system-ui,sans-serif");
  box.innerHTML = '<div style="background:#fff;color:#111;max-width:560px;width:92%;border-radius:12px;padding:16px;box-shadow:0 12px 44px rgba(0,0,0,.45)"><div style="font-weight:600;margin-bottom:8px">Captured PRICE_N price(s) from SRC_NAME</div><textarea readonly style="width:100%;height:190px;font:12px/1.45 monospace;border:1px solid #ccc;border-radius:8px;padding:8px;box-sizing:border-box"></textarea><div style="display:flex;gap:8px;margin-top:10px;justify-content:flex-end"><button id="__pxcopy" style="padding:9px 15px;border:0;border-radius:8px;background:#2d6cdf;color:#fff;font-size:14px">Copy</button><button id="__pxclose" style="padding:9px 15px;border:1px solid #ccc;border-radius:8px;background:#fff;font-size:14px">Close</button></div></div>';
  document.body.appendChild(box);
  box.querySelector("div>div").firstChild.textContent = "Captured " + found.length + " " + WANT + " price(s) from " + SRC;
  var ta = box.querySelector("textarea"); ta.value = text;
  box.querySelector("#__pxclose").onclick = function () { box.remove(); };
  box.querySelector("#__pxcopy").onclick = function () {
    ta.focus(); ta.select(); ta.setSelectionRange(0, 99999);
    try { navigator.clipboard.writeText(text); } catch (e) { try { document.execCommand("copy"); } catch (e2) {} }
    this.textContent = "Copied ✓";
  };
})();
