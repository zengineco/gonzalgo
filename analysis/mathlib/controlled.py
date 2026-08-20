#!/usr/bin/env python3
"""Generate and score the controlled tactic cells.

    python controlled.py --check     # re-score the recorded results
    python controlled.py --gen       # regenerate the Lean file from the cells

Replaces `gen_controlled.py` and `analyze_controlled.py`, both lost to a
temporary directory. The cells and their results survived in `analysis/data`,
so the experiment stays auditable; this restores the ability to re-score it and
to regenerate the Lean source from the cell list.

The design, recovered from the data: one cell per (class, index, tactic). A
class fixes a goal shape -- `le_nat`, `lt_int`, `eq_nat` and so on -- and each
goal is posed to every tactic in the panel. `kind` marks whether the relation is
an order or an equality, which is the comparison the experiment exists to make:
`norm_num` is classical on order goals and not on equality goals, while `decide`
and `simp` are classical on neither.

Scoring is a set membership test on the reported axioms, so it cannot drift:
a cell is classical exactly when `Classical.choice` is in its axiom list.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
CELLS = DATA / "controlled_cells.json"
RESULTS = DATA / "controlled_results.json"


def load(path: Path):
    if not path.exists():
        sys.exit(f"missing {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def classical(cell) -> bool:
    return "Classical.choice" in (cell.get("axioms") or [])


def check() -> int:
    cells, results = load(CELLS), load(RESULTS)
    print(f"{len(cells)} cells, {len(results)} results")

    by_name = {c["name"]: c for c in cells}
    missing = [r["name"] for r in results if r["name"] not in by_name]
    unrun = [c["name"] for c in cells
             if c["name"] not in {r["name"] for r in results}]
    if missing:
        print(f"  results with no cell: {len(missing)}")
    if unrun:
        print(f"  cells with no result: {len(unrun)}")

    # tactic x kind -> classical rate
    tab = defaultdict(lambda: [0, 0])
    for r in results:
        k = (r["tactic"], r["kind"])
        tab[k][1] += 1
        if classical(r):
            tab[k][0] += 1

    tactics = sorted({t for t, _ in tab})
    kinds = sorted({k for _, k in tab})
    print(f"\n{'tactic':<14}" + "".join(f"{k:>14}" for k in kinds))
    print("-" * (14 + 14 * len(kinds)))
    for t in tactics:
        row = f"{t:<14}"
        for k in kinds:
            c, n = tab.get((t, k), (0, 0))
            row += f"{(f'{c}/{n}' if n else '—'):>14}"
        print(row)

    print("\nclassical on order goals but not on equality goals:")
    hits = []
    for t in tactics:
        o = tab.get((t, "order"), (0, 0))
        e = tab.get((t, "equality"), (0, 0))
        if o[1] and e[1] and o[0] == o[1] and e[0] == 0:
            hits.append(t)
            print(f"  {t}   order {o[0]}/{o[1]}   equality {e[0]}/{e[1]}")
    if not hits:
        print("  none")
    return 0 if not (missing or unrun) else 1


def gen() -> int:
    """Emit the Lean file from the cell list, so the experiment can be re-run."""
    cells = load(CELLS)
    out = [
        "/-  Controlled tactic cells, regenerated from analysis/data/"
        "controlled_cells.json.",
        "    One theorem per (goal, tactic); `#eval` reports the axioms of each.  -/",
        "import Mathlib", "", "open Lean", "",
    ]
    for c in cells:
        out.append(f"theorem {c['name']} : {c['goal']} := by {c['tactic']}")
    out += ["", "def cls (n : Name) : CoreM String := do",
            "  let l := (← collectAxioms n).toList.map toString",
            '  return if l.contains "Classical.choice" then "CLASSICAL" '
            'else "choice-free"', "",
            "#eval show CoreM Unit from do"]
    for c in cells:
        out.append(f'  IO.println s!"{{← cls `{c["name"]}}}  {c["name"]}"')
    path = HERE / "Controlled_regen.lean"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {path}  ({len(cells)} cells)")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="re-score the recorded results")
    ap.add_argument("--gen", action="store_true",
                    help="regenerate the Lean source from the cells")
    a = ap.parse_args()
    if a.gen:
        sys.exit(gen())
    sys.exit(check())


if __name__ == "__main__":
    main()
