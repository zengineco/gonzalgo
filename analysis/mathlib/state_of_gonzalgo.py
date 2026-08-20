"""Measure where gonzalgo actually stands. Every figure from a live API.

Adoption, reach and competition are the questions being asked, and each has a
checkable answer. Anything this script cannot reach is reported as unknown
rather than estimated.
"""
from __future__ import annotations

import json, sys, urllib.error, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "f-keys-audit/1.0 (mailto:vince@f-keys.com)",
      "Accept": "application/json"}


def get(u, tmo=45):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers=UA), timeout=tmo).read().decode())


def safe(label, fn):
    try:
        return fn()
    except urllib.error.HTTPError as e:
        print(f"  {label}: HTTP {e.code}")
    except Exception as e:
        print(f"  {label}: {type(e).__name__} {e}")
    return None


print("=" * 74)
print("PyPI")
d = safe("pypi", lambda: get("https://pypi.org/pypi/gonzalgo/json"))
if d:
    i = d["info"]
    print(f"  version {i['version']}   releases: {len(d['releases'])}")
    print(f"  requires-python {i.get('requires_python')}   "
          f"license {i.get('license') or (i.get('classifiers') and 'see classifiers')}")
s = safe("pypistats", lambda: get(
    "https://pypistats.org/api/packages/gonzalgo/recent"))
if s:
    print(f"  downloads  day {s['data']['last_day']:,}   "
          f"week {s['data']['last_week']:,}   month {s['data']['last_month']:,}")
o = safe("pypistats-overall", lambda: get(
    "https://pypistats.org/api/packages/gonzalgo/overall"))
if o:
    tot = sum(r["downloads"] for r in o["data"])
    mirr = sum(r["downloads"] for r in o["data"] if r["category"] == "with_mirrors")
    print(f"  overall rows {len(o['data'])}, total {tot:,} "
          f"(with_mirrors {mirr:,})")

print("\n" + "=" * 74)
print("GitHub")
for repo in ("zengineco/gonzalgo", "leanprover-community/axiom-audit",
             "leanprover-community/mathlib4"):
    r = safe(repo, lambda: get(f"https://api.github.com/repos/{repo}"))
    if r:
        print(f"  {repo}")
        print(f"     stars {r['stargazers_count']}  forks {r['forks_count']}  "
              f"watchers {r['subscribers_count']}  issues {r['open_issues_count']}")
        print(f"     created {r['created_at'][:10]}  pushed {r['pushed_at'][:10]}")
        print(f"     desc: {(r.get('description') or '')[:80]}")

print("\n" + "=" * 74)
print("Zenodo attention on his records")
for doi, label in (("21769846", "axioms paper"),
                   ("21853489", "attribution paper"),
                   ("21883963", "dominator note"),
                   ("21884471", "eligibility note")):
    r = safe(label, lambda: get(f"https://zenodo.org/api/records/{doi}"))
    if r:
        st = r.get("stats", {})
        print(f"  {label:<20} views {st.get('version_views', st.get('views', '?'))}"
              f"  downloads {st.get('version_downloads', st.get('downloads', '?'))}")

print("\n" + "=" * 74)
print("Citation indexes — is any of it picked up?")
for doi in ("10.5281/zenodo.21769846", "10.5281/zenodo.21853489"):
    r = safe(f"openalex {doi}", lambda: get(
        f"https://api.openalex.org/works/doi:{doi}"))
    if r:
        print(f"  OpenAlex has {doi}: cited_by {r.get('cited_by_count')}  "
              f"type {r.get('type')}")
    else:
        print(f"  OpenAlex: no record for {doi}")
r = safe("openalex-author", lambda: get(
    "https://api.openalex.org/authors?filter=orcid:0009-0005-3640-014X"))
if r is not None:
    print(f"  OpenAlex author entries for his ORCID: {r.get('meta', {}).get('count')}")
    for a in (r.get("results") or [])[:3]:
        print(f"     {a.get('id')}  works {a.get('works_count')}  "
              f"cited {a.get('cited_by_count')}")

r = safe("semanticscholar", lambda: get(
    "https://api.semanticscholar.org/graph/v1/paper/DOI:10.5281/zenodo.21769846"
    "?fields=title,citationCount,externalIds"))
if r:
    print(f"  Semantic Scholar: {r.get('title','')[:50]} "
          f"cited {r.get('citationCount')}")
else:
    print("  Semantic Scholar: no record")

print("\n" + "=" * 74)
print("Lean ecosystem presence")
r = safe("reservoir", lambda: get(
    "https://reservoir.lean-lang.org/api/v1/packages/zengineco/gonzalgo"))
if r:
    print(f"  Reservoir: listed — {json.dumps(r)[:160]}")
else:
    print("  Reservoir: not resolving (bug was filed earlier)")
