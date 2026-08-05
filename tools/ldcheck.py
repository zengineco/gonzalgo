"""Validate the structured data actually parses before it ships.

Invalid JSON-LD does not warn, it is silently ignored, so the page would look
fine and be machine-unreadable.
"""
import io
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

path = sys.argv[1] if len(sys.argv) > 1 else "gonzalgo/index.html"
html = io.open(path, encoding="utf-8").read()

m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
if not m:
    print("  NO JSON-LD BLOCK FOUND")
    raise SystemExit(1)

data = json.loads(m.group(1))
# a document may be a single node or a @graph of them; both are valid JSON-LD
nodes = data["@graph"] if "@graph" in data else [data]
print("  JSON-LD parses. Nodes:")
for node in nodes:
    t = node["@type"]
    extra = ""
    if t == "FAQPage":
        extra = "  ({} questions)".format(len(node["mainEntity"]))
    print("    - {}{}".format(t, extra))

for tag in ("canonical", "og:title", "og:description", "twitter:card",
            "description", "llms-txt"):
    present = tag in html
    print("  {:<16}{}".format(tag, "present" if present else "MISSING"))
