"""Command line for gonzalgo.

    gonzalgo lean-files [DIR]        write the Lean extractors to run
    gonzalgo check DUMP              verify a dump actually contains proof terms
    gonzalgo amplify DUMP [-a AXIOM] entry points, dependents, reach
    gonzalgo eligible DUMP           statement-vs-proof ceiling on removal
    gonzalgo why DUMP DECL...        shortest path to an axiom, edges labelled
    gonzalgo audit SITES DUMP        sites -> declarations -> cleanable
    gonzalgo mm FILE...              amplification in Metamath databases

Every subcommand that reads a Lean dump runs `check` first, because a dump
missing its proof terms produces confidently wrong numbers rather than obviously
wrong ones.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import graph, lean, metamath, lean_files
from .lean import DumpError


def _load(path: Path, *, quiet: bool = False):
    stats = lean.check_dump(path)
    if not quiet:
        print(f"  {path.name}: {stats['declarations']:,} declarations, "
              f"{stats['theorems']:,} theorems, "
              f"{stats['theorems_with_proof']:,} carrying proof terms")
    g = lean.load(path)
    if not quiet:
        print(f"  graph: {len(g):,} nodes, {g.edge_count:,} edges\n")
    return g


def cmd_lean_files(args) -> int:
    dest = Path(args.dir)
    dest.mkdir(parents=True, exist_ok=True)
    for src in lean_files.paths():
        shutil.copy2(src, dest / src.name)
        print(f"  wrote {dest / src.name}")
    print("\n  In a Lake project that imports Mathlib:")
    print("    lake env lean Split.lean       # -> mathlib_split.tsv")
    print("    lake env lean Substitute.lean  # -> sites2.tsv")
    print("    lake env lean Rewrite.lean     # kernel-check the substitution")
    return 0


def cmd_check(args) -> int:
    stats = lean.check_dump(Path(args.dump))
    for k, v in stats.items():
        print(f"  {k:<22}{v:>12,}")
    print("\n  OK: proof terms are present.")
    return 0


def cmd_amplify(args) -> int:
    path = Path(args.dump)
    g = _load(path)
    axiom = args.axiom
    dep = g.dependents(axiom)
    thms = [i for i, k in g.kind.items() if k == "T"]
    n_dep = sum(1 for i in thms if dep[i])
    entries = g.entry_points(axiom, among="T", via=graph.PROOF)
    mentions = g.entry_points(axiom, among="T", via=graph.STATEMENT)
    amp = n_dep / len(entries) if entries else float("inf")
    print(f"  axiom            {axiom}")
    print(f"  theorems         {len(thms):>12,}")
    print(f"  dependents       {n_dep:>12,}   reach {100*n_dep/len(thms):.1f}%")
    print(f"  entry points     {len(entries):>12,}   {len(entries)/len(thms):.3e} per theorem")
    print(f"  amplification    {amp:>12,.0f}x")
    print(f"  cited in stmts   {len(mentions):>12,}   theorems ABOUT the axiom,")
    print( "                                 not counted as spending it")
    print("\n  Reach is invariant under inlining and factoring; amplification is")
    print("  not. Compare libraries on reach.")
    if args.list:
        for e in sorted(entries)[:args.list]:
            print(f"    {e}")
    return 0


def cmd_eligible(args) -> int:
    path = Path(args.dump)
    g = _load(path)
    e = lean.eligibility(path, g, args.axiom)
    print(f"  theorems                                  {e.theorems:>10,}")
    print(f"  statement dep, proof dep                  {e.stmt_and_proof:>10,}"
          f"  {100*e.stmt_and_proof/e.theorems:5.1f}%")
    print(f"  statement CHOICE-FREE, proof dep          {e.proof_only:>10,}"
          f"  {100*e.proof_only/e.theorems:5.1f}%   <- eligible")
    print(f"  statement dep, proof free                 {e.stmt_only:>10,}"
          f"  {100*e.stmt_only/e.theorems:5.1f}%")
    print(f"  neither                                   {e.neither:>10,}"
          f"  {100*e.neither/e.theorems:5.1f}%")
    print(f"\n  ceiling on removable classical dependence: {100*e.ceiling:.1f}%")
    print("  A ceiling, not an estimate: many eligible theorems need classical")
    print("  logic even where the statement is constructive.")
    return 0


def cmd_why(args) -> int:
    path = Path(args.dump)
    g = _load(path)
    # A missing TARGET must not be reported as "no path". "This theorem does not
    # depend on that" and "you typed a name that does not exist" are opposite
    # answers, and conflating them is exactly the silent-wrong-answer this tool
    # exists to prevent.
    if args.axiom not in g.ids:
        print(f"\n  ERROR: no declaration named {args.axiom!r} in this dump.")
        near = [n for n in g.ids if n.endswith("." + args.axiom.split(".")[-1])][:6]
        if near:
            print("  Did you mean:")
            for n in near:
                print(f"    {n}")
        print()
        return 2
    for decl in args.decl:
        print(f"\n  {decl}")
        if decl not in g.ids:
            print(f"    ERROR: no declaration named {decl!r} in this dump")
            continue
        p = g.path_to(decl, args.axiom)
        if p is None:
            print(f"    does not depend on {args.axiom}")
            continue
        for i, (node, label) in enumerate(p):
            tag = "" if i == 0 else f"--{label}--> "
            print(f"    {'  ' * min(i, 6)}{tag}{node}")
    print()
    return 0


def cmd_index(args) -> int:
    """Print the bundled Kernel Index.

    The only command that works the moment the package is installed — no Lean,
    no dump, no network. Someone evaluating whether this is worth their time can
    see real output in one line instead of building a project first.
    """
    import json
    p = Path(__file__).parent / "data" / "kernel-index.json"
    if not p.exists():
        print("  index not bundled in this install")
        print("  https://f-keys.com/gonzalgo/kernel-index/")
        return 1
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data["rows"]
    print(f"  THE KERNEL INDEX  ({data['version']})   what formal libraries rest on")
    print(f"  {'library':<20}{'system':<10}{'theorems':>10}{'unfinished':>12}"
          f"{'compiler':>10}{'choice':>9}")
    print("  " + "-" * 71)
    for r in rows:
        pct = r.get("optional_reach_pct")
        comp = r.get("compiler_trusting_theorems")
        print(f"  {r['library'][:19]:<20}{r['system']:<10}{r['theorems']:>10,}"
              f"{r.get('unfinished_theorems', 0):>12,}"
              f"{('-' if comp is None else format(comp, ',')):>10}"
              f"{('-' if pct is None else str(pct) + '%'):>9}")
    tot = sum(r["theorems"] for r in rows)
    unf = sum(r.get("unfinished_theorems", 0) for r in rows)
    print(f"\n  {len(rows)} libraries, {tot:,} theorems, {unf} resting on an "
          f"unfinished proof.")
    print(f"  {data['url'] if 'url' in data else 'https://f-keys.com/gonzalgo/kernel-index/'}")
    return 0


def cmd_trust(args) -> int:
    """What is this project actually trusting, and how far does it spread?

    `#print axioms` answers this one theorem at a time. The question a project
    has is the whole-library one: is anything here unfinished, and is anything
    resting on the compiler rather than the kernel — and if so, what else has
    quietly inherited it.
    """
    path = Path(args.dump)
    g = _load(path)
    thms = [i for i, k in g.kind.items() if k == "T"]
    print(f"  {'axiom':<22}{'declared':>9}{'direct':>8}{'theorems':>10}   note")
    flagged = []
    for name, note in lean.ESCAPE_HATCHES.items():
        if name not in g.ids:
            print(f"  {name:<22}{'absent':>9}{'-':>8}{'-':>10}   not in this environment")
            continue
        direct = len(g.entry_points(name, via=graph.PROOF)) + \
                 len(g.entry_points(name, via=graph.STATEMENT))
        reach = g.dependents(name)
        n = sum(1 for i in thms if reach[i])
        print(f"  {name:<22}{'yes':>9}{direct:>8,}{n:>10,}   {note}")
        if direct and name not in lean.UNREMARKABLE:
            flagged.append((name, direct, n))
    print()
    # A trust axiom that no THEOREM reaches is not a finding. Lean's environment
    # necessarily contains the primitives `native_decide` is built from; what
    # matters is whether any mathematical result rests on them.
    worry = [f for f in flagged
             if f[0] in ("sorryAx", "Lean.ofReduceBool", "Lean.ofReduceNat",
                         "Lean.trustCompiler") and f[2] > 0]
    if not worry:
        print("  CLEAN: no theorem here rests on an unfinished proof or on the")
        print("  compiler. Trust axioms may be declared - Lean's environment always")
        print("  declares them - but no result reaches one.")
    else:
        for name, direct, n in worry:
            print(f"  {name}: {direct:,} declarations use it directly, "
                  f"{n:,} theorems inherit it.")
        print("\n  `gonzalgo why DUMP <theorem> -a <axiom>` shows the route for any one"
              " of them.")

    if args.fail_on_trust:
        # exit non-zero so this can gate a build. A clean library can then PROVE
        # it is clean on every commit, rather than assuming it.
        if worry:
            print("\n  FAILING: --fail-on-trust was requested and results are affected.")
            return 1
        print("\n  --fail-on-trust: passed.")
    return 0


def cmd_impact(args) -> int:
    """`why` run backwards: if I change this, what breaks and how badly?"""
    path = Path(args.dump)
    g = _load(path)
    for target in args.decl:
        print(f"\n  {target}")
        if target not in g.ids:
            print(f"    ERROR: no declaration named {target!r} in this dump")
            continue
        stmt, proof = g.direct_dependents(target)
        reach = g.dependents(target)
        total = int(reach.sum()) - 1          # the target reaches itself
        thms = sum(1 for i, k in g.kind.items() if k == "T" and reach[i])
        print(f"    reached transitively   {total:>8,}   ({thms:,} of them theorems)")
        print(f"    ── direct ──")
        print(f"    in a STATEMENT         {len(stmt):>8,}   API surface: changing the")
        print(f"                                      type changes their meaning")
        print(f"    in a PROOF only        {len(proof):>8,}   insulated: a type-preserving")
        print(f"                                      change costs a recompile")
        if total:
            blast = total / max(len(stmt) + len(proof), 1)
            print(f"    amplification          {blast:>8,.0f}x   inherited per direct user")
        n = args.limit
        for label, names in (("STATEMENT", stmt), ("PROOF", proof)):
            if names and n:
                print(f"\n    direct via {label}:")
                for x in sorted(names)[:n]:
                    print(f"      {x[:88]}")
                if len(names) > n:
                    print(f"      ... and {len(names) - n:,} more")
    print()
    return 0


def cmd_audit(args) -> int:
    dump = Path(args.dump)
    g = _load(dump)
    a = lean.audit(Path(args.sites), dump, g, args.axiom)
    print(f"  declarations scanned              {a.verdicts:>8,}")
    print(f"\n  SITES (real instance witness)     {a.sites:>8,}")
    print(f"  DECLARATIONS with >= 1 site       {a.declarations:>8,}")
    print(f"  CLEANABLE (choice-free after)     {a.cleanable:>8,}")
    print(f"  blocked by other choice use       {a.blocked:>8,}")
    print("\n  Cleanable is an upper bound on what a patch achieves: it says the")
    print("  instance exists, not that the proof still type-checks once swapped")
    print("  in. Rewrite.lean settles that with the kernel.")
    if args.out:
        Path(args.out).write_text("\n".join(a.cleanable_names) + "\n", encoding="utf-8")
        print(f"\n  wrote {args.out} ({a.cleanable:,} names)")
    return 0


def cmd_mm(args) -> int:
    for f in args.files:
        p = Path(f)
        if not p.exists():
            print(f"\n  {f}: not found, skipped")
            continue
        a = metamath.amplification(p)
        print(f"\n  {a.name}")
        print(f"    theorems                  {a.theorems:>9,}")
        print(f"    logical axioms (|-)       {a.axioms_declared:>9,}   used {a.axioms_used}")
        if not a.theorems or not a.stats:
            # peano.mm is an axiomatisation with no derived theorems. Reporting
            # 0.0x would read as "no amplification"; the truth is that the
            # quantity is undefined, which is a different claim.
            print("    amplification             undefined - no derived theorems")
            continue
        entries = sum(s.entry_points for s in a.stats)
        print(f"    median entries per axiom  {a.median_entries:>9.1f}")
        print(f"    entries per theorem       {entries / a.theorems:>9.4f}   "
              f"(size-independent)")
        print(f"    overall amplification     {a.overall:>9.1f}x  "
              f"(scales with library size)")
        top = a.top(5)
        if top:
            print("    heaviest: " + "; ".join(
                f"{s.name} {s.dependents:,}dep/{s.entry_points}ent" for s in top))
    print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gonzalgo",
        description="Measure where a formal library spends its axioms.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("lean-files", help="write the Lean extractors to run")
    s.add_argument("dir", nargs="?", default=".")
    s.set_defaults(func=cmd_lean_files)

    s = sub.add_parser("check", help="verify a dump contains proof terms")
    s.add_argument("dump")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("amplify", help="entry points, dependents, reach")
    s.add_argument("dump")
    s.add_argument("-a", "--axiom", default=lean.AXIOM)
    s.add_argument("--list", type=int, default=0, metavar="N",
                   help="also print up to N entry-point names")
    s.set_defaults(func=cmd_amplify)

    s = sub.add_parser("eligible", help="statement-vs-proof ceiling on removal")
    s.add_argument("dump")
    s.add_argument("-a", "--axiom", default=lean.AXIOM)
    s.set_defaults(func=cmd_eligible)

    s = sub.add_parser("why", help="shortest path from a declaration to an axiom")
    s.add_argument("dump")
    s.add_argument("decl", nargs="+")
    s.add_argument("-a", "--axiom", default=lean.AXIOM)
    s.set_defaults(func=cmd_why)

    s = sub.add_parser("index", help="the Kernel Index — works with no files")
    s.set_defaults(func=cmd_index)

    s = sub.add_parser("trust", help="unfinished proofs and compiler-trusting results")
    s.add_argument("dump")
    s.add_argument("--fail-on-trust", action="store_true",
                   help="exit 1 if any theorem rests on an unfinished proof or on "
                        "the compiler, so this can gate a build")
    s.set_defaults(func=cmd_trust)

    s = sub.add_parser("impact", help="if I change this, what breaks?")
    s.add_argument("dump")
    s.add_argument("decl", nargs="+")
    s.add_argument("-n", "--limit", type=int, default=10, metavar="N",
                   help="show up to N direct dependents of each kind (0 for none)")
    s.set_defaults(func=cmd_impact)

    s = sub.add_parser("audit", help="sites -> declarations -> cleanable")
    s.add_argument("sites")
    s.add_argument("dump")
    s.add_argument("-a", "--axiom", default=lean.AXIOM)
    s.add_argument("-o", "--out", help="write cleanable declaration names here")
    s.set_defaults(func=cmd_audit)

    s = sub.add_parser("mm", help="amplification in Metamath databases")
    s.add_argument("files", nargs="+")
    s.set_defaults(func=cmd_mm)
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except DumpError as e:
        print(f"\nERROR: {e}\n", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"\nERROR: {e}\n", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
