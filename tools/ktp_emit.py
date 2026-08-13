"""Emit a Kernel Trust Profile from Lean's own `#print axioms` output.

    lake env lean Axioms.lean > axioms.txt
    python tools/ktp_emit.py axioms.txt --name MyProject --system "Lean 4" \
        --system-version 4.33.0 --revision $(git rev-parse HEAD) > kernel-trust.json

A second implementation, on purpose. Rule R6 of the specification says a format
only one program can produce is a file format rather than a standard, and until
this existed the only emitter was `gonzalgo profile`, which needs a declaration
graph, ~650 MB of dump and a Python install.

This needs none of that. It reads what Lean already prints:

    'Nat.add_comm' depends on axioms: [propext, Quot.sound]
    'foo' does not depend on any axioms

so any project that can run Lean can emit a profile, which is the point.

What it cannot do, and says so rather than guessing: `#print axioms` reports a
declaration's axioms without separating those reached through the theorem's
STATEMENT from those reached only through its PROOF. Rule R3 requires that
distinction where a dependency is reported, and rule R2 says absence is not
zero — so `via` is emitted as null and the reader knows it was not measured.
Computing it needs the graph, which is what the other implementation is for.

Generate the input with a file like:

    import MyProject
    open Lean in
    run_cmd do
      let env ← Lean.getEnv
      for (n, ci) in env.constants.toList do
        if ci.isThm then Lean.logInfo m!"#print axioms {n}"

or simply a file of `#print axioms X` lines, one per declaration you care about.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from datetime import date

# 'name' depends on axioms: [a, b, c]      /      'name' does not depend on any axioms
LINE = re.compile(
    r"'(?P<name>[^']+)'\s+(?:depends on axioms:\s*\[(?P<axioms>[^\]]*)\]"
    r"|does not depend on any axioms)")

UNFINISHED = {"sorryAx"}
COMPILER_TRUSTED = {"Lean.ofReduceBool", "Lean.ofReduceNat", "Lean.trustCompiler"}
# Present in every Lean development; reporting them as remarkable is noise.
FOUNDATIONAL = {"propext", "Quot.sound"}


def classify(axiom: str) -> str:
    if axiom in UNFINISHED or axiom in COMPILER_TRUSTED:
        return "escape-hatch"
    if axiom in FOUNDATIONAL:
        return "foundational"
    return "optional"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="file of #print axioms output, or - for stdin")
    ap.add_argument("--name", required=True)
    ap.add_argument("--system", default="Lean 4")
    ap.add_argument("--system-version", default=None)
    ap.add_argument("--revision", default=None)
    ap.add_argument("--foundation", default="dependent type theory")
    ap.add_argument("--url", default=None)
    args = ap.parse_args()

    text = sys.stdin.read() if args.input == "-" else \
        open(args.input, encoding="utf-8", errors="replace").read()

    seen: dict[str, set[str]] = {}
    for m in LINE.finditer(text):
        ax = m.group("axioms")
        seen[m.group("name")] = {
            a.strip() for a in (ax or "").split(",") if a.strip()}

    if not seen:
        sys.exit("  no `#print axioms` lines found — wrong input file?")

    total = len(seen)
    reach = collections.Counter()
    for axioms in seen.values():
        for a in axioms:
            reach[a] += 1

    assumptions = [
        {
            "name": a,
            "kind": classify(a),
            # Entry points need the graph: #print axioms reports what a
            # declaration reaches, never which declaration cited it directly.
            "entry_points": None,
            "reach": {"theorems": n, "fraction": round(n / total, 4)},
            # R3 wants statement and proof kept apart. This input cannot
            # separate them, and R2 says do not write a value that was not
            # measured.
            "via": None,
        }
        for a, n in sorted(reach.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    profile = {
        "ktp_version": "0.1",
        "generated_at": date.today().isoformat(),
        "generated_by": {
            "tool": "ktp_emit.py",
            "version": "0.1",
            "url": "https://f-keys.com/gonzalgo/kernel-trust/",
        },
        "subject": {
            "name": args.name,
            "system": args.system,
            "system_version": args.system_version,
            "revision": args.revision,
            "foundation": args.foundation,
            "url": args.url,
        },
        "counts": {"declarations": None, "theorems": total},
        "unfinished": {
            "theorems_reaching": sum(
                1 for ax in seen.values() if ax & UNFINISHED),
            "axioms": sorted(UNFINISHED),
        },
        "compiler_trusted": {
            "theorems_reaching": sum(
                1 for ax in seen.values() if ax & COMPILER_TRUSTED),
            "axioms": sorted(COMPILER_TRUSTED),
        },
        "assumptions": assumptions,
    }
    json.dump(profile, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
