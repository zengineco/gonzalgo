"""Reduce a Split dump to the small measurement worth keeping forever.

    python tools/fingerprint.py DUMP.tsv --label v4.33.0 -o measurements/v4.33.0.json

A dump is ~650 MB and cannot live in a repository. The measurement taken from
it is a few hundred bytes and is the thing that becomes a time series: counts by
kind, the module count, and the full axiom roster.

The axiom roster is stored in full rather than as a count. A release that swaps
one axiom for another leaves the count unchanged, and that is exactly the event
this file exists to catch.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

KIND = {"D": "definitions", "T": "theorems", "O": "other", "A": "axioms"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--label", required=True, help="e.g. v4.33.0")
    ap.add_argument("--toolchain", default="", help="the lean-toolchain measured")
    ap.add_argument("--revision", default="", help="the library commit measured")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    kinds = collections.Counter()
    modules: set[str] = set()
    axioms: set[str] = set()
    rows = malformed = has_module = 0
    digest = hashlib.blake2b(digest_size=16)

    with open(args.dump, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").rstrip("\r").split("\t")
            if len(p) < 4:
                malformed += 1
                continue
            rows += 1
            kinds[p[0]] += 1
            if p[0] == "A":
                axioms.add(p[1])
            if len(p) >= 5:
                has_module = 1
                modules.add(p[4])
            # Order-independent: a dump whose rows are emitted in a different
            # order is the same measurement, so the hash must not care.
            digest.update(hashlib.blake2b(
                "\t".join(p[:4]).encode("utf-8", "replace"),
                digest_size=8).digest())

    if not rows:
        raise SystemExit(f"  {args.dump}: no parseable rows — wrong file?")

    payload = {
        "label": args.label,
        "toolchain": args.toolchain,
        "revision": args.revision,
        "declarations": rows,
        **{KIND[k]: kinds.get(k, 0) for k in ("T", "D", "O", "A")},
        "modules": len(modules) if has_module else None,
        "axiom_roster": sorted(axioms),
        "malformed_rows": malformed,
        "graph_digest": digest.hexdigest(),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"  {args.label}: {rows:,} declarations, "
          f"{payload['theorems']:,} theorems, {len(axioms)} axioms")
    print(f"  axiom roster: {', '.join(sorted(axioms))}")
    print(f"  wrote {out}")


if __name__ == "__main__":
    main()
