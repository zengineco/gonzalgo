"""Rank every constant in Mathlib by how many theorems rest on it ALONE.

The per-candidate severing runs were computing dominators the slow way. In the
reversed dependency graph rooted at Classical.choice, a constant c dominates n
exactly when every path from n to choice passes through c -- so severing c frees
precisely c's dominator subtree. One dominator tree therefore answers for all
766,564 constants what six separate reachability runs answered for six.

Algorithm: Cooper, Harvey and Kennedy, "A Simple, Fast Dominance Algorithm"
(2001). Iterative, so no Lengauer-Tarjan machinery, and it converges in a few
passes on a graph this shallow.

Validated against the severing runs before any new number is read off it:
propDecidable 91,858 / byContradiction 23,550 / lt_or_eq_of_le 2,018 /
eq_or_lt_of_le 1,221 / LE.le.lt_or_eq 583 / em 476.
"""
from __future__ import annotations

import array, sys, time
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DUMP = Path(os.environ.get("MATHLIB_DUMP")
            or Path(__file__).resolve().parents[1] / "data" / "mathlib_graph.tsv")
ROOT_NAME = "Classical.choice"

t0 = time.time()
ids: dict[str, int] = {}
kind = bytearray()


def sid(n: str) -> int:
    i = ids.get(n)
    if i is None:
        i = len(ids)
        ids[n] = i
        kind.append(63)          # '?'
    return i


# forward CSR: dep_start[r]..dep_start[r+1] are the deps of order[r]
dep_start, dep_edges, order = [0], array.array("i"), array.array("i")
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
            dep_edges.append(sid(d))
        for d in p[3].split():
            dep_edges.append(sid(d))
        dep_start.append(len(dep_edges))

N = len(ids)
ROOT = ids[ROOT_NAME]
names = [None] * N
for k, v in ids.items():
    names[v] = k

# row index for a declaration; names referenced but never defined have none
row = array.array("i", bytes(4 * N))
for i in range(N):
    row[i] = -1
for r in range(len(order)):
    row[order[r]] = r
print(f"{len(order):,} declarations, {N:,} names, {len(dep_edges):,} edges  "
      f"[{time.time()-t0:.0f}s]")


def deps(n: int):
    r = row[n]
    if r < 0:
        return ()
    return dep_edges[dep_start[r]:dep_start[r + 1]]


# reverse CSR: dependents. Needed for the DFS that orders the tree build.
cnt = array.array("i", bytes(4 * N))
for r in range(len(order)):
    for j in range(dep_start[r], dep_start[r + 1]):
        cnt[dep_edges[j]] += 1
rstart = array.array("i", bytes(4 * (N + 1)))
acc = 0
for i in range(N):
    rstart[i] = acc
    acc += cnt[i]
rstart[N] = acc
redges = array.array("i", bytes(4 * acc))
fill = array.array("i", rstart[:N])
for r in range(len(order)):
    n = order[r]
    for j in range(dep_start[r], dep_start[r + 1]):
        t = dep_edges[j]
        redges[fill[t]] = n
        fill[t] += 1
print(f"reverse graph: {acc:,} edges  [{time.time()-t0:.0f}s]")

# ---- postorder of the reversed graph from ROOT ---------------------------
post = array.array("i")
seen = bytearray(N)
stack = [(ROOT, rstart[ROOT])]
seen[ROOT] = 1
while stack:
    n, ptr = stack[-1]
    if ptr < rstart[n + 1]:
        stack[-1] = (n, ptr + 1)
        m = redges[ptr]
        if not seen[m]:
            seen[m] = 1
            stack.append((m, rstart[m]))
    else:
        post.append(n)
        stack.pop()

rpo = list(reversed(post))
pon = array.array("i", bytes(4 * N))          # position in reverse postorder
for i in range(N):
    pon[i] = -1
for i, n in enumerate(rpo):
    pon[n] = i
print(f"reachable from {ROOT_NAME}: {len(rpo):,}  [{time.time()-t0:.0f}s]")

# ---- Cooper-Harvey-Kennedy ------------------------------------------------
idom = array.array("i", bytes(4 * N))
for i in range(N):
    idom[i] = -1
idom[ROOT] = ROOT


def intersect(a: int, b: int) -> int:
    while a != b:
        while pon[a] > pon[b]:
            a = idom[a]
        while pon[b] > pon[a]:
            b = idom[b]
    return a


rounds = 0
changed = True
while changed:
    changed = False
    rounds += 1
    for n in rpo:
        if n == ROOT:
            continue
        new = -1
        # predecessors in the REVERSED graph are the node's own dependencies
        for p in deps(n):
            if pon[p] < 0 or idom[p] < 0:
                continue
            new = p if new < 0 else intersect(p, new)
        if new >= 0 and idom[n] != new:
            idom[n] = new
            changed = True
    print(f"  pass {rounds} [{time.time()-t0:.0f}s]")

# ---- subtree theorem counts ----------------------------------------------
THM = ord("T")
sub = array.array("i", bytes(4 * N))
for n in rpo:
    if kind[n] == THM:
        sub[n] += 1
for n in post:                      # children before parents
    if n == ROOT:
        continue
    d = idom[n]
    if d >= 0 and d != n:
        sub[d] += sub[n]

print(f"\ndominator tree built in {rounds} passes  [{time.time()-t0:.0f}s]")

CHECK = {"Classical.propDecidable": 91858, "Classical.byContradiction": 23550,
         "lt_or_eq_of_le": 2018, "eq_or_lt_of_le": 1221,
         "LE.le.lt_or_eq": 583, "Classical.em": 476}
print("\nvalidation against the severing runs")
ok = True
for nm, want in CHECK.items():
    got = sub[ids[nm]] if nm in ids else -1
    flag = "OK " if got == want else "MISMATCH"
    if got != want:
        ok = False
    print(f"  {flag}  {nm:<28} dominator={got:,}  severing={want:,}")

print("\ntop 40 constants by theorems that rest on them ALONE")
cand = [(sub[n], n) for n in rpo if n != ROOT and sub[n] > 0]
cand.sort(reverse=True)
print(f"{'theorems':>10}  {'kind':<5} name")
for s, n in cand[:40]:
    print(f"{s:>10,}  {chr(kind[n]):<5} {names[n]}")

import json
Path(__file__).with_name("dominators.json").write_text(json.dumps(
    [{"name": names[n], "kind": chr(kind[n]), "alone": s} for s, n in cand[:3000]],
    indent=1), encoding="utf-8")
print(f"\nwrote dominators.json (top 3000)   validation {'PASSED' if ok else 'FAILED'}")
sys.exit(0 if ok else 1)
