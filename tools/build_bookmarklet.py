#!/usr/bin/env python3
"""Turn tools/price-capture.js into a one-line javascript: bookmarklet.

Strips full-line // comments and blank lines, then joins with spaces. The source is
written so no string literal spans multiple lines, so this line-join is safe.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "price-capture.js")
OUT = os.path.join(ROOT, "tools", "bookmarklet.txt")

lines = []
for ln in open(SRC, encoding="utf-8").read().split("\n"):
    s = ln.strip()
    if not s or s.startswith("//"):
        continue
    lines.append(s)
code = "javascript:" + " ".join(lines)
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(code + "\n")
print(f"Wrote {OUT} ({len(code)} chars)")
