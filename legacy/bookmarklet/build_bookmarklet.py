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
    # Strip inline // comments (safe here: no // appears inside any string/regex,
    # where slashes are written as \/ ). Then drop blank lines.
    s = ln.split("//")[0].strip()
    if not s:
        continue
    lines.append(s)
code = "javascript:" + " ".join(lines)
assert code.count("(") == code.count(")"), "unbalanced parens -- check for stray // in a string"
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(code + "\n")
print(f"Wrote {OUT} ({len(code)} chars)")
