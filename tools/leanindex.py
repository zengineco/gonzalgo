"""Lean rows for the index: what each package rests on.

Attribution is by DEFINING MODULE, never by declaration name. A Lean name
carries no package information -- `Int.mem_box` is Mathlib and `Nat.decLe` is
core -- so a name-prefix heuristic produces confident nonsense. The fifth column
of the dump exists for exactly this reason.
"""
from __future__ import annotations

import collections
import io
import json
import sys
from array import array
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DUMP = Path(r"C:\Users\Admin\lean-work\opaquedisc\mathlib_split.tsv")

TARGETS = {
    "sorryAx": "unfinished",
    "Lean.ofReduceBool": "compiler",
    "Lean.ofReduceNat": "compiler",
    "Lean.trustCompiler": "compiler",
    "Classical.choice": "choice",
}

LABEL = {
    "Init": "Lean core (Init)",
    "Lean": "Lean core (Lean)",
    "Std": "Std",
    "Batteries": "Batteries",
    "Mathlib": "Mathlib",
    "Aesop": "Aesop",
    "Qq": "Qq",
    "Plausible": "Plausible",
    "ProofWidgets": "ProofWidgets",
    "Cli": "Cli",
    "ImportGraph": "ImportGraph",
    "LeanSearchClient": "LeanSearchClient",
}

ids: dict[str, int] = {}
def idx(n: str) -> int:
    i = ids.get(n)
    if i is None:
        i = ids[n] = len(ids)
    return i

src, dst = array("i"), array("i")
kinds: list[str] = []
pkg_of: list[str] = []

def grow(u: int) -> None:
    while len(kinds) <= u:
        kinds.append("?")
        pkg_of.append("?")

print("  reading dump ...")
rows = 0
for line in io.open(DUMP, encoding="utf-8", errors="replace"):
    p = line.rstrip("\n").split("\t")
    if len(p) < 2:
        continue
    rows += 1
    u = idx(p[1])
    grow(u)
    kinds[u] = p[0]
    if len(p) > 4 and p[4]:
        pkg_of[u] = p[4].split(".")[0]
    for col in (2, 3):
        if len(p) > col and p[col]:
            for d in p[col].split():
                v = idx(d)
                grow(v)
                src.append(u)
                dst.append(v)

n = len(ids)
print(f"  {rows:,} declarations, {n:,} nodes, {len(src):,} edges")

s = np.frombuffer(src, dtype=np.int32)
d = np.frombuffer(dst, dtype=np.int32)
order = np.argsort(d, kind="stable")
rsrc, rdst = s[order], d[order]
starts = np.searchsorted(rdst, np.arange(n + 1))
del s, d, order, rdst

def reach(target: str) -> np.ndarray:
    seen = np.zeros(n, dtype=bool)
    if target not in ids:
        return seen
    root = ids[target]
    seen[root] = True
    frontier = [root]
    while frontier:
        nxt = []
        for x in frontier:
            for k in range(starts[x], starts[x + 1]):
                u = rsrc[k]
                if not seen[u]:
                    seen[u] = True
                    nxt.append(u)
        frontier = nxt
    return seen

masks = {t: reach(t) for t in TARGETS}
print("  reachability computed")

theorem = np.array([k == "T" for k in kinds])
pkgs = collections.Counter(pkg_of[i] for i in range(n) if theorem[i] and pkg_of[i] != "?")

rows_out = []
for pkg, nthm in pkgs.most_common():
    if pkg not in LABEL or nthm < 20:
        continue
    sel = np.array([theorem[i] and pkg_of[i] == pkg for i in range(n)])
    def cnt(*ts):
        m = np.zeros(n, dtype=bool)
        for t in ts:
            m |= masks[t]
        return int((sel & m).sum())
    unfinished = cnt("sorryAx")
    compiler = cnt("Lean.ofReduceBool", "Lean.ofReduceNat", "Lean.trustCompiler")
    choice = cnt("Classical.choice")
    rows_out.append({
        "library": LABEL[pkg],
        "system": "Lean 4",
        "foundation": "Dependent type theory",
        "theorems": nthm,
        "unfinished_theorems": unfinished,
        "compiler_trusting_theorems": compiler,
        "optional_axiom": "choice",
        "optional_reach": choice,
        "optional_reach_pct": round(100 * choice / nthm, 2) if nthm else None,
    })
    r = rows_out[-1]
    print(f"  {r['library']:<20} thms {nthm:>8,}  unfinished {unfinished:>5,}  "
          f"compiler {compiler:>5,}  choice {r['optional_reach_pct']:>6}%")

out = Path(__file__).parent / "index_lean.json"
out.write_text(json.dumps(rows_out, indent=2), encoding="utf-8")
print(f"\n  wrote {out.name}")
