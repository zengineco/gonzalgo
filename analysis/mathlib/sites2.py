"""Sites, properly collapsed, plus a partition that adds up.

Two fixes over the first pass.

CHAINS. Absorbing a child only when it weighed within 1 of its parent left the
three DHashMap nodes (4,899 / 4,896 / 4,892) as three sites when severing any
one frees the same theorems. Collapse on a ratio instead, and name the chain by
its most readable member rather than by whichever `_private ... _proof_1_1`
auxiliary happens to sit nearest the axiom.

PARTITION. Summing dominator subtrees double-counts, because subtrees nest:
the first pass reported 607,408 against 324,510 theorems that actually reach
choice. Subtree size answers "how many rest on this alone" and legitimately
nests. For "where does the dependence sit", each theorem is instead charged
once, to its immediate dominator -- the last gate before it.
"""
from __future__ import annotations

import json, sys, time
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SP = Path(__file__).resolve().parent
exec(open(SP / "dominators.py", encoding="utf-8").read().split("CHECK = {")[0])
# provides: sub, idom, names, kind, rpo, post, ROOT, N, ids

THM = ord("T")
kids = defaultdict(list)
for n in rpo:
    if n != ROOT and idom[n] >= 0 and idom[n] != n:
        kids[idom[n]].append(n)


def readable(nm: str) -> int:
    """Lower is better as a chain representative."""
    bad = 0
    if nm.startswith("_private"):
        bad += 100
    if "._proof_" in nm or "._simp_" in nm or "._eq_" in nm:
        bad += 50
    if ".match_" in nm or "._f" in nm:
        bad += 40
    return bad * 1000 + len(nm)


# ---- collapse chains on a ratio ------------------------------------------
RATIO = 0.97
member_of = {}
chains = []
for n in rpo:                      # root-to-leaf order
    if n == ROOT or sub[n] == 0 or n in member_of:
        continue
    chain = [n]
    cur = n
    while True:
        heavy = [c for c in kids[cur] if sub[c] >= RATIO * sub[cur]]
        if len(heavy) != 1:
            break
        cur = heavy[0]
        chain.append(cur)
    for m in chain:
        member_of[m] = n
    rep = min(chain, key=lambda m: readable(names[m]))
    chains.append((sub[n], rep, chain))

chains.sort(reverse=True)
print(f"\n{len([1 for n in rpo if sub[n] > 0]):,} constants with a non-empty "
      f"subtree -> {len(chains):,} sites after collapsing")


def area(nm: str) -> str:
    for pre, lab in [
        ("Classical.", "classical logic"), ("Std.DHashMap", "Std: hash maps"),
        ("Std.", "Std: other"), ("String.", "strings"), ("List.", "lists"),
        ("Array.", "arrays"), ("CategoryTheory.", "category theory"),
        ("Set.", "sets"), ("Filter.", "filters"), ("Finset.", "finsets"),
        ("MeasureTheory.", "measure theory"), ("Polynomial.", "polynomials"),
        ("Nat.", "Nat"), ("Int.", "Int"), ("Multiset.", "multisets"),
    ]:
        if nm.startswith(pre):
            return lab
    for key, lab in [("Set.image", "sets"), ("Functor", "category theory"),
                     ("String", "strings"), ("List", "lists")]:
        if key in nm:
            return lab
    h = nm.split(".", 1)[0]
    return h if h and h[0].isupper() else "order / root namespace"


print("\nTOP SITES  (theorems that rest on the site ALONE; subtrees nest)")
print(f"{'theorems':>9}  {'kind':<4} {'area':<22} name   [chain length]")
for s, rep, chain in chains[:26]:
    print(f"{s:>9,}  {chr(kind[rep]):<4} {area(names[rep])[:22]:<22} "
          f"{names[rep][:52]}   [{len(chain)}]")

# ---- true partition: charge each theorem to its immediate dominator ------
charge = Counter()
n_thm = 0
for n in rpo:
    if n == ROOT or kind[n] != THM:
        continue
    n_thm += 1
    d = idom[n]
    if d >= 0 and d != n:
        charge[member_of.get(d, d)] += 1

print(f"\n\nPARTITION  each of the {n_thm:,} classical theorems charged once, "
      f"to its immediate dominator")
by_area = Counter()
for node, c in charge.items():
    by_area[area(names[node])] += c
tot = sum(by_area.values())
print(f"  (charged: {tot:,})")
for a, v in by_area.most_common(18):
    print(f"  {v:>9,}  {100*v/tot:>5.1f}%  {a}")

print("\nsingle constants that are the LAST GATE for the most theorems")
for node, c in charge.most_common(20):
    print(f"  {c:>8,}  {chr(kind[node]):<3} {names[node][:66]}")

(SP / "sites2.json").write_text(json.dumps(
    [{"name": names[r], "kind": chr(kind[r]), "area": area(names[r]),
      "alone": s, "chain": [names[m] for m in ch]}
     for s, r, ch in chains[:1500]], indent=1), encoding="utf-8")
print(f"\nwrote sites2.json")
