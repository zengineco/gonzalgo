#!/usr/bin/env python3
"""Sever a constant's outgoing edges and recount who still reaches the axiom.

    python counterfactual.py                       # the six validation candidates
    python counterfactual.py lt_or_eq_of_le ...    # any constants you like

This is the independent check the dominator tree is validated against. It shares
no code with `dominators.py`: the tree is built once from the graph's structure,
while this recomputes reachability from scratch with a candidate's edges
removed. Agreement between two methods that do not share an implementation is
the whole point, so they stay separate.

The published figures, which the tree reproduces exactly:

    Classical.propDecidable   91,858
    Classical.byContradiction 23,550
    lt_or_eq_of_le             2,018
    eq_or_lt_of_le             1,221
    LE.le.lt_or_eq               583
    Classical.em                 476

Severing `c` means deleting `c`'s outgoing edges, so on the reverse graph it is
exactly "do not traverse out of `c`". The reverse graph is therefore built once
and each candidate costs one sweep, rather than one reverse graph per candidate,
which does not fit in memory at 30M edges.

PROVENANCE. The original of this script was lost to a temporary directory before
it was ever committed. This is a reimplementation against the same dump, written
to exit non-zero if it fails to reproduce the six numbers above -- a validation
that cannot fail validates nothing.
"""
from __future__ import annotations

import array
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# The dump that produced the published dominator figures was named
# mathlib_graph.tsv and is no longer on disk; set DUMP to point elsewhere.
DUMP = Path(os.environ.get("MATHLIB_SPLIT_DUMP") or os.environ.get("DUMP")
            or Path(__file__).resolve().parents[1] / "data"
            / "mathlib_split-v4.32.1.tsv")
AXIOM = "Classical.choice"

# Published counts, and how far each is allowed to move.
#
# The dump these were computed on had 530,348 theorems; the one now on disk has
# 532,605, so this is a check across a version boundary. Five of the six are
# small order lemmas whose subtrees are stable under that drift and must match
# exactly. `Classical.propDecidable` carries 92,000 theorems and its subtree
# scales with the library, so it is allowed 1% -- stated as a bound rather than
# left open, since a check that accommodates any answer checks nothing.
EXPECTED = {
    "Classical.propDecidable": (91858, 0.01),
    "Classical.byContradiction": (23550, 0.0),
    "lt_or_eq_of_le": (2018, 0.0),
    "eq_or_lt_of_le": (1221, 0.0),
    "LE.le.lt_or_eq": (583, 0.0),
    "Classical.em": (476, 0.0),
}


def load(dump: Path):
    """Read the dump and return (ids, kind, reverse-CSR).

    Columns are kind, name, statement dependencies, proof dependencies. The
    counterfactual follows the union of the two, matching what `collectAxioms`
    follows and what the dominator tree is built over.

    The reverse graph is stored CSR-style: `rstart[v]..rstart[v+1]` indexes
    `redge`, giving every `u` that depends on `v`.
    """
    ids: dict[str, int] = {}
    kind: list[str] = []

    def sid(n: str) -> int:
        i = ids.get(n)
        if i is None:
            i = len(ids)
            ids[n] = i
            kind.append("?")
        return i

    src = array.array("i")
    dst = array.array("i")
    rows = 0
    print(f"reading {dump.name} ({dump.stat().st_size / 1024 / 1024:.0f} MB)")
    with dump.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            k, name, sd, pd = parts[0], parts[1], parts[2], parts[3]
            i = sid(name)
            kind[i] = k
            for col in (sd, pd):
                for d in col.split():
                    src.append(i)
                    dst.append(sid(d))
            rows += 1
            if rows % 200000 == 0:
                print(f"  {rows:,} rows, {len(ids):,} names, {len(src):,} edges")
    n = len(ids)
    print(f"  {rows:,} rows, {n:,} names, {len(src):,} edges")

    print("  building reverse graph")
    counts = array.array("i", bytes(4 * (n + 1)))
    for v in dst:
        counts[v + 1] += 1
    for v in range(n):
        counts[v + 1] += counts[v]
    rstart = counts
    redge = array.array("i", bytes(4 * len(src)))
    fill = array.array("i", rstart[:n])
    for e in range(len(src)):
        v = dst[e]
        redge[fill[v]] = src[e]
        fill[v] += 1
    return ids, kind, rstart, redge


def reaching(n, rstart, redge, ax, severed=-1) -> bytearray:
    """Everything that reaches the axiom, with `severed`'s outgoing edges gone.

    On the reverse graph that is simply: never traverse out of `severed`.
    """
    seen = bytearray(n)
    seen[ax] = 1
    stack = [ax]
    while stack:
        v = stack.pop()
        if v == severed:
            continue
        for k in range(rstart[v], rstart[v + 1]):
            u = redge[k]
            if not seen[u]:
                seen[u] = 1
                stack.append(u)
    return seen


def main() -> None:
    if not DUMP.exists():
        sys.exit(f"dump not found: {DUMP}\n"
                 "regenerate with lean-work/opaquedisc/Dump.lean")
    ids, kind, rstart, redge = load(DUMP)
    n = len(ids)
    if AXIOM not in ids:
        sys.exit(f"{AXIOM} not in the dump")
    ax = ids[AXIOM]

    base = reaching(n, rstart, redge, ax)
    thm = [i for i in range(n) if kind[i] == "T"]
    base_thm = sum(1 for i in thm if base[i])
    print(f"\n{len(thm):,} theorems; {base_thm:,} reach {AXIOM}\n")

    names = sys.argv[1:] or list(EXPECTED)
    print(f"{'constant':<28}{'freed':>9}{'published':>11}")
    print("-" * 50)
    bad = []
    for nm in names:
        if nm not in ids:
            print(f"{nm:<28}{'ABSENT':>9}")
            continue
        after = reaching(n, rstart, redge, ax, severed=ids[nm])
        # Severing c models rebuilding c constructively, so c itself stops
        # reaching the axiom. The reverse traversal still marks it seen on
        # arrival, which would leave it counted as unfreed.
        after[ids[nm]] = 0
        freed = sum(1 for i in thm if base[i] and not after[i])
        spec = EXPECTED.get(nm)
        if spec is None:
            print(f"{nm:<28}{freed:>9,}{'—':>11}")
            continue
        exp, tol = spec
        slack = int(exp * tol)
        ok = abs(freed - exp) <= slack
        mark = "ok" if ok else "MISMATCH"
        if ok and freed != exp:
            mark = f"ok (drift {freed - exp:+,}, within {tol:.0%})"
        print(f"{nm:<28}{freed:>9,}{exp:>11,}  {mark}")
        if not ok:
            bad.append((nm, freed, exp, slack))

    if bad:
        print("\nVALIDATION FAILED")
        for nm, got, exp, slack in bad:
            print(f"  {nm}: got {got:,}, published {exp:,}, "
                  f"allowed ±{slack:,}")
        sys.exit(1)
    if any(nm in EXPECTED for nm in names):
        print("\nall checked candidates reproduce the published counts")


if __name__ == "__main__":
    main()
