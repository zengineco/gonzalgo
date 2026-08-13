"""Compare two Split dumps and write the version-over-version delta.

    python gonzalgo/_build/diff_dumps.py OLD.tsv NEW.tsv --old-label v4.32.1 --new-label v4.33.0

A Split dump is one row per declaration: kind, name, statement dependencies,
proof dependencies, module. Two dumps taken with the SAME extractor from two
library versions can be compared directly; two dumps from different extractors
cannot, and the labels are recorded so that mistake is visible rather than
silent.

Both files run to hundreds of megabytes, so neither is held in memory. Each is
streamed once into a map of name to (kind, module, hash of statement deps, hash
of proof deps) — the hashes make "did this declaration's dependencies change"
answerable without keeping the dependency lists themselves.

What comes out is one row per measured quantity, with both values and the
delta, plus the axiom roster from each side. A change in the axiom roster is the
single most consequential thing a version bump can do and it is reported first.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

KIND = {"D": "definition", "T": "theorem", "O": "other", "A": "axiom"}


def h(s: str) -> int:
    return int.from_bytes(hashlib.blake2b(s.encode("utf-8", "replace"),
                                          digest_size=8).digest(), "big")


def load(path: Path):
    """name -> (kind, module, stmt_hash, proof_hash). Streamed, never held whole.

    The module column is optional. The extractor shipped with the package writes
    four columns; the one in the measured project appends a fifth and says in its
    own comment that readers taking the first four are unaffected. Requiring five
    made a four-column dump parse as zero rows, and a differ reports that as the
    entire library having been deleted — so the count of unparseable rows is
    tracked and an empty parse is fatal rather than quiet."""
    decls: dict[str, tuple] = {}
    axioms: set[str] = set()
    malformed = 0
    has_module = True
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").rstrip("\r").split("\t")
            if len(p) < 4:
                malformed += 1
                continue
            kind, name, stmt, proof = p[0], p[1], p[2], p[3]
            if len(p) < 5:
                has_module = False
                module = None
            else:
                module = p[4]
            decls[name] = (kind, module, h(stmt), h(proof))
            if kind == "A":
                axioms.add(name)
    if not decls:
        raise SystemExit(f"  {path.name}: no parseable rows "
                         f"({malformed:,} malformed). Wrong file, or a dump "
                         f"from an extractor with a different column layout.")
    if malformed:
        print(f"    {malformed:,} malformed rows skipped in {path.name}")
    return decls, axioms, has_module


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--old-label", required=True)
    ap.add_argument("--new-label", required=True)
    ap.add_argument("-o", "--out", default=str(HERE / "data" / "version-delta-rows.json"))
    args = ap.parse_args()

    print(f"  reading {args.old_label} ...")
    old, old_ax, old_mod = load(Path(args.old))
    print(f"    {len(old):,} declarations, {len(old_ax)} axioms")
    print(f"  reading {args.new_label} ...")
    new, new_ax, new_mod = load(Path(args.new))
    print(f"    {len(new):,} declarations, {len(new_ax)} axioms")

    old_names, new_names = set(old), set(new)
    added, removed = new_names - old_names, old_names - new_names
    kept = old_names & new_names

    stmt_changed = {n for n in kept if old[n][2] != new[n][2]}
    proof_changed = {n for n in kept if old[n][3] != new[n][3]}
    # Only meaningful when both dumps carry the module column.
    both_have_modules = old_mod and new_mod
    moved = ({n for n in kept if old[n][1] != new[n][1]}
             if both_have_modules else set())
    # A declaration whose statement moved is a different theorem wearing the
    # same name; one whose proof moved is the same claim, reproved.
    proof_only = proof_changed - stmt_changed

    ko = collections.Counter(v[0] for v in old.values())
    kn = collections.Counter(v[0] for v in new.values())

    rows = []

    def row(quantity, o, n, note=""):
        rows.append({"quantity": quantity, args.old_label: o, args.new_label: n,
                     "delta": n - o,
                     "pct_change": (round(100 * (n - o) / o, 2) if o else None),
                     "note": note})

    row("declarations", len(old), len(new))
    for k in ("T", "D", "O", "A"):
        row(KIND[k] + "s", ko[k], kn[k])
    if both_have_modules:
        row("modules", len({v[1] for v in old.values()}),
            len({v[1] for v in new.values()}))
    else:
        print("    note: one dump has no module column; module rows omitted")

    rows.append({"quantity": "declarations added", args.old_label: None,
                 "delta": len(added), args.new_label: len(added),
                 "pct_change": None,
                 "note": "present in the new version only"})
    rows.append({"quantity": "declarations removed", args.old_label: len(removed),
                 args.new_label: None, "delta": -len(removed), "pct_change": None,
                 "note": "present in the old version only"})
    for label, s, note in (
        ("statements changed", stmt_changed,
         "same name, different statement dependencies — a different claim"),
        ("reproved only", proof_only,
         "same statement, different proof dependencies — same claim, new proof"),
    ) + ((("moved module", moved, "same name, relocated"),)
         if both_have_modules else ()):
        rows.append({"quantity": label, args.old_label: None,
                     args.new_label: None, "delta": len(s),
                     "pct_change": (round(100 * len(s) / len(kept), 2)
                                    if kept else None),
                     "note": note})

    payload = {
        "old_label": args.old_label, "new_label": args.new_label,
        "old_file": Path(args.old).name, "new_file": Path(args.new).name,
        "axioms": {
            args.old_label: sorted(old_ax), args.new_label: sorted(new_ax),
            "added": sorted(new_ax - old_ax), "removed": sorted(old_ax - new_ax),
        },
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                   encoding="utf-8")

    print()
    if new_ax - old_ax or old_ax - new_ax:
        print("  AXIOM ROSTER CHANGED")
        for a in sorted(new_ax - old_ax):
            print(f"    added   {a}")
        for a in sorted(old_ax - new_ax):
            print(f"    removed {a}")
    else:
        print(f"  axiom roster unchanged ({len(new_ax)} axioms)")
    print()
    w = max(len(args.old_label), len(args.new_label), 8)
    print(f"  {'quantity':<24}{args.old_label:>{w}}{args.new_label:>{w+2}}{'delta':>12}")
    for r in rows:
        o = r[args.old_label]
        n = r[args.new_label]
        print(f"  {r['quantity']:<24}{('' if o is None else f'{o:,}'):>{w}}"
              f"{('' if n is None else f'{n:,}'):>{w+2}}{r['delta']:>+12,}")
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
