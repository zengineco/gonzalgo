"""Metamath rows for the index: what each database rests on.

Incomplete proofs are the direct analogue of Lean's `sorry`. In Metamath a `$p`
whose proof contains a bare `?` is unfinished, and any theorem citing it inherits
that. Detected here rather than assumed absent.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gonzalgo import metamath  # noqa: E402

SCRATCH = Path(
    r"C:\Users\Admin\AppData\Local\Temp\claude"
    r"\C--Users-Admin-OneDrive-Desktop-Pro-Categories-Application-Prompt"
    r"\26bbb6ed-7be4-4b9c-9e0f-17f4def461f4\scratchpad"
)

DBS = [
    ("set.mm", "ZFC set theory, classical first-order logic"),
    ("iset.mm", "Intuitionistic set theory"),
    ("nf.mm", "Quine's New Foundations"),
    ("ql.mm", "Quantum logic"),
    ("hol.mm", "Higher-order logic"),
]

#: Optional axioms whose reach is worth reporting separately, by database.
OPTIONAL = {
    "set.mm": ("choice", ["ax-ac", "ax-ac2"]),
    "iset.mm": (None, []),
    "nf.mm": (None, []),
    "ql.mm": (None, []),
    "hol.mm": (None, []),
}


def incomplete_labels(path: Path) -> set[str]:
    """Labels whose own proof is unfinished (contains a bare `?`)."""
    out: set[str] = set()
    it = metamath.tokens(path)
    for t in it:
        if t in ("${", "$}") or t.startswith("$"):
            if t.startswith("$") and t not in ("${", "$}"):
                for u in it:
                    if u == "$.":
                        break
            continue
        label, key = t, next(it, "")
        if key == "$p":
            for u in it:
                if u == "$=":
                    break
            body = []
            for u in it:
                if u == "$.":
                    break
                body.append(u)
            if "?" in body:
                out.add(label)
        elif key in ("$a", "$e", "$f"):
            for u in it:
                if u == "$.":
                    break
    return out


rows = []
for name, foundation in DBS:
    p = SCRATCH / name
    if not p.exists():
        print(f"  {name}: not present, skipped")
        continue
    amp = metamath.amplification(p)
    db = metamath.parse(p)
    clos = metamath.closures(db)
    thms = db.theorems

    bad = incomplete_labels(p)
    # a theorem inherits incompleteness if it cites an unfinished label
    reach = set(bad)
    changed = True
    while changed:
        changed = False
        for t in thms:
            if t in reach:
                continue
            if any(r in reach for r in db.refs.get(t, ())):
                reach.add(t)
                changed = True

    label, axs = OPTIONAL[name]
    opt_reach = 0
    if axs:
        opt_reach = sum(1 for t in thms if any(a in clos[t] for a in axs))

    entries = sum(s.entry_points for s in amp.stats)
    rows.append({
        "library": name,
        "system": "Metamath",
        "foundation": foundation,
        "theorems": amp.theorems,
        "axioms_used": amp.axioms_used,
        "entry_points": entries,
        "entries_per_theorem": round(entries / amp.theorems, 4) if amp.theorems else None,
        "amplification": round(amp.overall, 1),
        "unfinished_theorems": len(reach & set(thms)),
        "optional_axiom": label,
        "optional_reach": opt_reach,
        "optional_reach_pct": round(100 * opt_reach / amp.theorems, 2) if amp.theorems and axs else None,
    })
    r = rows[-1]
    print(f"  {name:<9} thms {r['theorems']:>7,}  axioms {r['axioms_used']:>5}  "
          f"ent/thm {r['entries_per_theorem']:>7}  amp {r['amplification']:>7}x  "
          f"unfinished {r['unfinished_theorems']:>4}")

out = Path(__file__).parent / "index_metamath.json"
out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
print(f"\n  wrote {out.name}")
