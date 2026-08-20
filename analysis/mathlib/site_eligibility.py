"""Which load-bearing sites could even in principle be made choice-free?

A site's dominator subtree says how many theorems rest on it alone. It says
nothing about whether the site itself is fixable. Apply the papers' own test to
the site: its STATEMENT (type) is choice-free but its PROOF (body) is not.

This is a ceiling, not a claim of removability, and the clearest witness is in
the output below: `Classical.propDecidable : Decidable a` has a choice-free
type and cannot possibly be made constructive, because deciding an arbitrary
proposition IS the classical assumption. Eligibility bounds the candidates; it
does not certify them.

The dominator run merged statement and proof edges into one list, so this reads
the dump again keeping them apart.
"""
from __future__ import annotations

import array, json, sys
from collections import deque
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SP = Path(__file__).resolve().parent
DUMP = Path(os.environ.get("MATHLIB_DUMP")
            or Path(__file__).resolve().parents[1] / "data" / "mathlib_graph.tsv")
CHOICE = "Classical.choice"

ids: dict[str, int] = {}
kind = bytearray()


def sid(n: str) -> int:
    i = ids.get(n)
    if i is None:
        i = len(ids)
        ids[n] = i
        kind.append(63)
    return i


s_start, s_edges = [0], array.array("i")
p_start, p_edges = [0], array.array("i")
order = array.array("i")
print(f"reading {DUMP.stat().st_size/1024/1024:.0f} MB")
with DUMP.open("r", encoding="utf-8", errors="replace") as f:
    for line in f:
        if line.startswith("#"):
            continue
        p = line.rstrip("\n").split("\t")
        if len(p) < 4:
            continue
        i = sid(p[1])
        kind[i] = ord(p[0])
        order.append(i)
        for d in p[2].split():
            s_edges.append(sid(d))
        s_start.append(len(s_edges))
        for d in p[3].split():
            p_edges.append(sid(d))
        p_start.append(len(p_edges))

N = len(ids)
names = [None] * N
for k, v in ids.items():
    names[v] = k
row = array.array("i", bytes(4 * N))
for i in range(N):
    row[i] = -1
for r in range(len(order)):
    row[order[r]] = r
print(f"{len(order):,} declarations, {N:,} names")

# reverse graph over the union, then one BFS out from choice
cnt = array.array("i", bytes(4 * N))
for r in range(len(order)):
    for j in range(s_start[r], s_start[r + 1]):
        cnt[s_edges[j]] += 1
    for j in range(p_start[r], p_start[r + 1]):
        cnt[p_edges[j]] += 1
rs = array.array("i", bytes(4 * (N + 1)))
acc = 0
for i in range(N):
    rs[i] = acc
    acc += cnt[i]
rs[N] = acc
re_ = array.array("i", bytes(4 * acc))
fill = array.array("i", rs[:N])
for r in range(len(order)):
    n = order[r]
    for j in range(s_start[r], s_start[r + 1]):
        t = s_edges[j]
        re_[fill[t]] = n
        fill[t] += 1
    for j in range(p_start[r], p_start[r + 1]):
        t = p_edges[j]
        re_[fill[t]] = n
        fill[t] += 1

reach = bytearray(N)
root = ids[CHOICE]
reach[root] = 1
q = deque([root])
while q:
    c = q.popleft()
    for j in range(rs[c], rs[c + 1]):
        m = re_[j]
        if not reach[m]:
            reach[m] = 1
            q.append(m)
print(f"reach {CHOICE}: {sum(reach):,}")


def stmt_bound(n: int) -> bool:
    r = row[n]
    if r < 0:
        return False
    for j in range(s_start[r], s_start[r + 1]):
        if reach[s_edges[j]]:
            return True
    return False


sites = json.loads((SP / "sites2.json").read_text(encoding="utf-8"))
print(f"\n{len(sites)} sites loaded\n")

print(f"{'theorems':>9}  {'kind':<4} {'status':<16} {'area':<20} name")
elig_w = bound_w = 0
rows = []
for s in sites:
    n = ids.get(s["name"])
    if n is None:
        continue
    b = stmt_bound(n)
    s["statement_bound"] = b
    rows.append(s)
    if b:
        bound_w += s["alone"]
    else:
        elig_w += s["alone"]

for s in rows[:28]:
    st = "statement-bound" if s["statement_bound"] else "ELIGIBLE"
    print(f"{s['alone']:>9,}  {s['kind']:<4} {st:<16} {s['area'][:20]:<20} "
          f"{s['name'][:48]}")

ne = sum(1 for s in rows if not s["statement_bound"])
print(f"\nof the {len(rows)} sites: {ne} eligible, {len(rows)-ne} statement-bound")
print(f"  (subtree weights nest, so these sums are upper bounds, not a partition)")

print("\nlargest ELIGIBLE sites outside classical logic")
c = 0
for s in rows:
    if s["statement_bound"] or s["name"].startswith("Classical."):
        continue
    print(f"  {s['alone']:>7,}  {s['kind']}  {s['area'][:18]:<18} {s['name'][:56]}")
    c += 1
    if c >= 20:
        break

print("\nlargest STATEMENT-BOUND sites  (dependence is in what they say)")
c = 0
for s in rows:
    if not s["statement_bound"]:
        continue
    print(f"  {s['alone']:>7,}  {s['kind']}  {s['area'][:18]:<18} {s['name'][:56]}")
    c += 1
    if c >= 12:
        break

(SP / "site_eligibility.json").write_text(json.dumps(rows, indent=1),
                                          encoding="utf-8")
print("\nwrote site_eligibility.json")
