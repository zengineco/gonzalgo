"""How big is the Classical.propDecidable chokepoint across Mathlib?

Reverse reachability, not per-node search: build the reverse graph once and
BFS outward from each target. That answers "which declarations reach X" in one
sweep instead of 790,000 searches.

Names are interned to ints; 30M edges as a flat array is ~120 MB, which fits,
whereas the same edges as Python strings does not.

The statement/proof split follows the paper's definitions:
  A(t) = closure over statement AND proof edges  (what collectAxioms follows)
  S(t) = union of A(c) over constants c in t's TYPE
  eligible = t reaches the target, and no constant in its type does
"""
from __future__ import annotations

import array
import sys
from collections import deque
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DUMP = Path(os.environ.get("MATHLIB_DUMP")
            or Path(__file__).resolve().parents[1] / "data" / "mathlib_graph.tsv")

TARGETS = ["Classical.propDecidable", "lt_or_eq_of_le",
           "Classical.byContradiction", "Classical.em", "Classical.choice"]

print(f"reading {DUMP}  ({DUMP.stat().st_size/1024/1024:.0f} MB)")

ids: dict[str, int] = {}
kind: list[str] = []


def sid(n: str) -> int:
    i = ids.get(n)
    if i is None:
        i = len(ids)
        ids[n] = i
        kind.append("?")
    return i


# flat CSR-style storage: heads index into a shared target array
s_start, s_edges = [0], array.array("i")
p_start, p_edges = [0], array.array("i")
order: list[int] = []

n_lines = 0
with DUMP.open("r", encoding="utf-8", errors="replace") as f:
    for line in f:
        if line.startswith("#"):
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 4:
            continue
        k, name, sd, pd = parts[0], parts[1], parts[2], parts[3]
        i = sid(name)
        kind[i] = k
        order.append(i)
        for d in sd.split():
            s_edges.append(sid(d))
        s_start.append(len(s_edges))
        for d in pd.split():
            p_edges.append(sid(d))
        p_start.append(len(p_edges))
        n_lines += 1
        if n_lines % 100000 == 0:
            print(f"  {n_lines:,} rows, {len(ids):,} names, "
                  f"{len(s_edges)+len(p_edges):,} edges")

N = len(ids)
print(f"\n{n_lines:,} declarations, {N:,} distinct names, "
      f"{len(s_edges):,} statement edges, {len(p_edges):,} proof edges")

# row index for a declaration id (a name may be referenced but never defined)
row = {d: r for r, d in enumerate(order)}

# reverse graph over the UNION of statement and proof edges
print("building reverse graph...")
indeg = array.array("i", [0]) * 0
rev_count = array.array("i", [0]) * 0
rev_count = array.array("i", bytes(4 * N))
for r, d in enumerate(order):
    for j in range(s_start[r], s_start[r + 1]):
        rev_count[s_edges[j]] += 1
    for j in range(p_start[r], p_start[r + 1]):
        rev_count[p_edges[j]] += 1
rev_start = array.array("i", bytes(4 * (N + 1)))
acc = 0
for i in range(N):
    rev_start[i] = acc
    acc += rev_count[i]
rev_start[N] = acc
rev_edges = array.array("i", bytes(4 * acc))
fill = array.array("i", rev_start[:N])
for r, d in enumerate(order):
    for j in range(s_start[r], s_start[r + 1]):
        t = s_edges[j]
        rev_edges[fill[t]] = d
        fill[t] += 1
    for j in range(p_start[r], p_start[r + 1]):
        t = p_edges[j]
        rev_edges[fill[t]] = d
        fill[t] += 1
print(f"  {acc:,} reverse edges")


def reaches(target: str) -> bytearray:
    """Every declaration whose closure contains `target`."""
    seen = bytearray(N)
    t = ids.get(target)
    if t is None:
        return seen
    q = deque([t])
    seen[t] = 1
    while q:
        c = q.popleft()
        for j in range(rev_start[c], rev_start[c + 1]):
            p = rev_edges[j]
            if not seen[p]:
                seen[p] = 1
                q.append(p)
    return seen


THM = {"T"}
print()
results = {}
for tgt in TARGETS:
    if tgt not in ids:
        print(f"  {tgt}: not present in the dump")
        continue
    seen = reaches(tgt)
    tid = ids[tgt]
    allc = sum(1 for d in order if seen[d] and d != tid)
    thm = sum(1 for d in order if seen[d] and d != tid and kind[d] in THM)
    results[tgt] = seen
    print(f"  {tgt}")
    print(f"      all declarations: {allc:,}      theorems: {thm:,}")

# statement-bound vs eligible, for the chokepoint
tgt = "Classical.propDecidable"
if tgt in results:
    seen = results[tgt]
    tid = ids[tgt]
    bound = elig = 0
    for r, d in enumerate(order):
        if not seen[d] or d == tid or kind[d] not in THM:
            continue
        st = False
        for j in range(s_start[r], s_start[r + 1]):
            c = s_edges[j]
            if c == tid or seen[c]:
                st = True
                break
        if st:
            bound += 1
        else:
            elig += 1
    print(f"\n{tgt}, theorems only:")
    print(f"  statement-bound : {bound:,}")
    print(f"  eligible        : {elig:,}")
    tot = bound + elig
    if tot:
        print(f"  eligible share  : {100*elig/tot:.1f}%")

# how much of the chokepoint runs through the order lemma the trace named
a, b = results.get("Classical.propDecidable"), results.get("lt_or_eq_of_le")
if a and b:
    both = sum(1 for d in order if a[d] and b[d] and kind[d] in THM)
    only_a = sum(1 for d in order if a[d] and not b[d] and kind[d] in THM)
    print(f"\ntheorems reaching propDecidable:")
    print(f"  also reaching lt_or_eq_of_le : {both:,}")
    print(f"  not through it               : {only_a:,}")
