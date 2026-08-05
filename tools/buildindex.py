"""Generate the Kernel Index page and its machine-readable companion.

The page is the artifact; the JSON is the reason anyone cites it. A table a human
can read and a machine cannot is half a publication.
"""
from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "fkeys" / "gonzalgo" / "kernel-index"
OUT.mkdir(parents=True, exist_ok=True)

lean = json.loads((HERE / "index_lean.json").read_text(encoding="utf-8"))
mm = json.loads((HERE / "index_metamath.json").read_text(encoding="utf-8"))
today = date.today().isoformat()

rows = lean + mm
payload = {
    "name": "The Kernel Index",
    "description": (
        "What formal mathematical libraries rest on: theorems depending on an "
        "unfinished proof, on the compiler rather than the kernel, and on an "
        "optional axiom. Measured by one program across two proof systems and "
        "six foundations."
    ),
    "version": today,
    "license": "https://creativecommons.org/licenses/by/4.0/",
    "producedBy": {
        "software": "gonzalgo",
        "url": "https://pypi.org/project/gonzalgo/",
        "paper": "https://doi.org/10.5281/zenodo.21769846",
    },
    "measured": {
        "Lean 4": "4.32.1 with Mathlib",
        "Metamath": "set.mm, iset.mm, nf.mm, ql.mm, hol.mm",
    },
    "rows": rows,
}
(OUT / "kernel-index.json").write_text(
    json.dumps(payload, indent=2), encoding="utf-8")

# ---- CSV, because half the people who want this will want a spreadsheet ----
cols = ["library", "system", "foundation", "theorems", "unfinished_theorems",
        "compiler_trusting_theorems", "optional_axiom", "optional_reach",
        "optional_reach_pct", "axioms_used", "entry_points",
        "entries_per_theorem", "amplification"]
# csv module, not string joining: a foundation like "ZFC set theory, classical
# first-order logic" contains a comma, and hand-joining silently shifts every
# column after it. A machine-readable file that is quietly wrong is worse than
# none at all.
import csv  # noqa: E402

with io.open(OUT / "kernel-index.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow(["" if r.get(c) is None else r.get(c, "") for c in cols])


def cell(r, key, fmt="{:,}"):
    v = r.get(key)
    if v is None or v == "":
        return "&mdash;"
    return fmt.format(v) if isinstance(v, (int, float)) else str(v)


def tr(r):
    unf = r.get("unfinished_theorems")
    comp = r.get("compiler_trusting_theorems")
    unf_s = ("<strong>%s</strong>" % f"{unf:,}") if unf else "0"
    comp_s = ("<strong>%s</strong>" % f"{comp:,}") if comp else ("0" if comp == 0 else "&mdash;")
    pct = r.get("optional_reach_pct")
    pct_s = f"{pct}%" if pct is not None else "&mdash;"
    return (
        f"<tr><td>{r['library']}</td><td>{r['system']}</td>"
        f"<td class='found'>{r['foundation']}</td>"
        f"<td class='num'>{cell(r,'theorems')}</td>"
        f"<td class='num'>{unf_s}</td><td class='num'>{comp_s}</td>"
        f"<td class='num'>{pct_s}</td></tr>"
    )


table = "\n".join(tr(r) for r in rows)

jsonld = json.dumps({
    "@context": "https://schema.org",
    "@type": "Dataset",
    "name": "The Kernel Index",
    "description": payload["description"],
    "url": "https://f-keys.com/gonzalgo/kernel-index/",
    "version": today,
    "license": "https://creativecommons.org/licenses/by/4.0/",
    "keywords": ["formal verification", "Lean 4", "Mathlib", "Metamath",
                 "proof assistant", "axiom", "sorry", "native_decide",
                 "provenance", "trusted base"],
    "creator": {"@type": "Person", "name": "Vincent Gonzalez",
                "identifier": "https://orcid.org/0009-0005-3640-014X"},
    "isBasedOn": "https://doi.org/10.5281/zenodo.21769846",
    "distribution": [
        {"@type": "DataDownload", "encodingFormat": "application/json",
         "contentUrl": "https://f-keys.com/gonzalgo/kernel-index/kernel-index.json"},
        {"@type": "DataDownload", "encodingFormat": "text/csv",
         "contentUrl": "https://f-keys.com/gonzalgo/kernel-index/kernel-index.csv"},
    ],
}, indent=2)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="index, follow, max-snippet:-1">
<link rel="canonical" href="https://f-keys.com/gonzalgo/kernel-index/">
<title>The Kernel Index &mdash; what formal mathematical libraries rest on</title>
<meta name="description" content="A measured table of what formal libraries rest on: theorems depending on an unfinished proof, on the compiler rather than the kernel, or on an optional axiom. Lean 4 and Metamath, six foundations, one program.">
<meta name="llms-txt" content="https://f-keys.com/llms.txt">
<meta name="ai" content="allow">
<meta property="og:type" content="website">
<meta property="og:url" content="https://f-keys.com/gonzalgo/kernel-index/">
<meta property="og:title" content="The Kernel Index">
<meta property="og:description" content="What formal mathematical libraries rest on. Measured, not assumed.">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=VT323&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<script type="application/ld+json">
{jsonld}
</script>
<style>
:root {{ --bg:#0a0e0a; --panel:#111911; --border:#1f351f; --green:#39ff14; --text:#c3dcc3; --dim:#8fae8f; --cyan:#00ffcc; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:'Share Tech Mono',monospace; line-height:1.65; }}
body::before {{ content:''; position:fixed; inset:0; background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.07) 2px,rgba(0,0,0,0.07) 4px); pointer-events:none; z-index:9000; }}
nav {{ position:fixed; top:0; left:0; right:0; z-index:10000; background:rgba(10,14,10,.95); border-bottom:1px solid var(--border); padding:0 2rem; height:60px; display:flex; align-items:center; justify-content:space-between; }}
.logo {{ font-family:'VT323',monospace; font-weight:400; font-size:28px; color:var(--green); letter-spacing:4px; text-decoration:none; }}
nav a {{ color:var(--dim); text-decoration:none; }} nav a:hover {{ color:var(--green); }}
main {{ max-width:1080px; margin:0 auto; padding:7rem 1.2rem 4rem; }}
h1 {{ font-family:'VT323',monospace; font-weight:400; font-size:clamp(38px,7vw,68px); color:var(--green); letter-spacing:4px; line-height:1; }}
.kicker {{ font-family:'VT323',monospace; font-weight:400; font-size:clamp(18px,3vw,26px); color:var(--cyan); letter-spacing:2px; margin:.5rem 0 1.5rem; }}
h2 {{ font-family:'VT323',monospace; font-weight:400; font-size:1.7rem; color:var(--green); margin:2.5rem 0 .8rem; letter-spacing:2px; }}
p {{ margin-bottom:1rem; }} a {{ color:var(--green); }}
.wrap {{ overflow-x:auto; border:1px solid var(--border); background:var(--panel); margin:1.5rem 0; }}
table {{ width:100%; border-collapse:collapse; font-size:.88rem; min-width:820px; }}
th {{ color:var(--green); text-align:left; padding:.7rem .6rem; border-bottom:1px solid var(--border); white-space:nowrap; }}
td {{ padding:.55rem .6rem; border-bottom:1px solid #142414; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
td.found {{ color:var(--dim); }}
tr:hover td {{ background:#0d120d; }}
strong {{ color:#ff8080; }}
.note {{ color:var(--dim); font-size:.9rem; }}
pre {{ background:#0d120d; border:1px solid var(--border); padding:1rem; overflow-x:auto; font-size:.85rem; margin:1rem 0; }}
code {{ color:var(--cyan); }}
footer {{ border-top:1px solid var(--border); margin-top:3.5rem; padding:2rem 0; color:var(--dim); font-size:.85rem; }}
</style>
</head>
<body>
<nav>
  <a href="/" class="logo">F-KEYS</a>
  <div style="display:flex;gap:1.5rem;font-size:.9rem;">
    <a href="/gonzalgo/">gonzalgo</a>
    <a href="https://github.com/zengineco/gonzalgo">GitHub</a>
  </div>
</nav>
<main>

<h1>THE KERNEL INDEX</h1>
<p class="kicker">what formal libraries actually rest on</p>

<p>
Each library here was measured directly. The two middle columns are the ones to
read: how many theorems rest on a proof that was never finished, and how many
were settled by running compiled code rather than by the kernel.
</p>
<p class="note">
Measured with <a href="/gonzalgo/">gonzalgo</a> &middot; Lean 4.32.1 with Mathlib
&middot; Metamath <code>set.mm</code>, <code>iset.mm</code>, <code>nf.mm</code>,
<code>ql.mm</code>, <code>hol.mm</code> &middot; last measured {today}
</p>

<div class="wrap">
<table>
<thead><tr>
  <th>library</th><th>system</th><th>foundation</th>
  <th style="text-align:right">theorems</th>
  <th style="text-align:right">unfinished</th>
  <th style="text-align:right">compiler-trusted</th>
  <th style="text-align:right">optional axiom</th>
</tr></thead>
<tbody>
{table}
</tbody>
</table>
</div>

<p class="note">
<strong style="color:#ff8080">Red</strong> marks a non-zero count &mdash; theorems
resting on an unfinished proof, or on the compiler. <em>unfinished</em> counts
theorems reaching a <code>sorry</code> (Lean) or a <code>?</code>-bearing proof
(Metamath) anywhere upstream, not only those that state one.
<em>optional axiom</em> is the share of theorems depending on
<code>Classical.choice</code> in Lean and on full choice in <code>set.mm</code>;
the other databases declare no choice axiom.
</p>

<h2>Get the data</h2>
<p>
<a href="kernel-index.json">kernel-index.json</a> &middot;
<a href="kernel-index.csv">kernel-index.csv</a> &middot; CC-BY-4.0
</p>

<h2>Reproduce it</h2>
<pre>pip install gonzalgo
gonzalgo trust mathlib_split.tsv      # the Lean rows
gonzalgo mm set.mm iset.mm nf.mm ql.mm hol.mm   # the Metamath rows</pre>
<p class="note">
Every figure comes from the proof system's own bookkeeping &mdash; Lean's
<code>collectAxioms</code> and Metamath's proof structure. The extractors ship
with the tool, so you can re-derive any row here yourself.
</p>

<h2>Why it exists</h2>
<p>
&ldquo;This library rests on nothing but the kernel&rdquo; is something people
have had to take on faith, because checking it at library scale wasn't
practical. The numbers above are that check. A zero in the middle columns means
someone ran it and it came back empty.
</p>

<footer>
  <p>
    Cite: Gonzalez, V. (2026). <em>Where Formal Libraries Spend Their Axioms</em>.
    Zenodo. <a href="https://doi.org/10.5281/zenodo.21769846">10.5281/zenodo.21769846</a>
  </p>
  <p style="margin-top:.8rem;">
    The Kernel Index is maintained at
    <a href="https://f-keys.com/gonzalgo/kernel-index/">f-keys.com/gonzalgo/kernel-index</a>
    &mdash; the home of <code>kernel &gt; sorry</code>.
  </p>
  <p style="margin-top:1.5rem;">&copy; 2026 F-Keys</p>
</footer>
</main>
</body>
</html>
"""

(OUT / "index.html").write_text(html, encoding="utf-8")
print(f"  wrote {OUT / 'index.html'}")
print(f"  wrote kernel-index.json  ({len(rows)} rows)")
print(f"  wrote kernel-index.csv")
