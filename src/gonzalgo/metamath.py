"""Reading Metamath databases, and measuring axiom spend in them.

Included so the same measurements run on a second foundation by the same code
rather than by analogy. `set.mm` is ZFC over classical first-order logic,
`iset.mm` is intuitionistic, `nf.mm` is Quine's New Foundations; Lean's Mathlib
is dependent type theory. A comparison between them means something only if one
program produces all the numbers.

LOGICAL AXIOMS ARE FOUND BY TYPECODE, NOT BY NAME. A `$a` statement whose
typecode is the assertion symbol (`|-`) is a logical axiom; `$a` statements with
syntax typecodes (`wff`, `class`, `setvar`) are grammar productions and are not.
The `ax-` naming convention differs between databases and would miscount two of
the three.

A `.mm` file is required to define labels before use, so the file order is a
topological order and one forward pass computes exact closures. No fixpoint is
needed, which is the main structural difference from the Lean side.
"""

from __future__ import annotations

import io
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

ASSERTION = "|-"


def tokens(path: Path) -> Iterator[str]:
    """Whitespace-separated tokens, with `$( ... $)` comments removed."""
    depth = 0
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            for tok in line.split():
                if tok == "$(":
                    depth += 1
                elif tok == "$)":
                    depth = max(0, depth - 1)
                elif depth == 0:
                    yield tok


@dataclass
class Database:
    order: list[str]
    kind: dict[str, str]
    refs: dict[str, list[str]]
    typecode: dict[str, str]

    @property
    def theorems(self) -> list[str]:
        return [l for l in self.order if self.kind[l] == "p"]

    @property
    def logical_axioms(self) -> set[str]:
        return {l for l in self.order
                if self.kind[l] == "a" and self.typecode.get(l) == ASSERTION}


def parse(path: Path) -> Database:
    order: list[str] = []
    kind: dict[str, str] = {}
    refs: dict[str, list[str]] = {}
    tc: dict[str, str] = {}
    it = tokens(path)
    for t in it:
        if t in ("${", "$}"):
            continue
        if t.startswith("$"):
            for u in it:
                if u == "$.":
                    break
            continue
        label, key = t, next(it, "")
        if key in ("$f", "$e"):
            for u in it:
                if u == "$.":
                    break
            kind[label] = key[1]
        elif key == "$a":
            first = None
            for u in it:
                if u == "$.":
                    break
                if first is None:
                    first = u
            kind[label] = "a"
            tc[label] = first or ""
            order.append(label)
        elif key == "$p":
            for u in it:
                if u == "$=":
                    break
            body = []
            for u in it:
                if u == "$.":
                    break
                body.append(u)
            if "(" in body and ")" in body:
                i, j = body.index("("), body.index(")")
                used = body[i + 1:j]        # compressed proof: label table
            else:
                used = [u for u in body if u != "?"]
            kind[label] = "p"
            refs[label] = used
            order.append(label)
        else:
            for u in it:
                if u == "$.":
                    break
    return Database(order, kind, refs, tc)


def closures(db: Database) -> dict[str, frozenset[str]]:
    """Axiom closure of every statement, in one forward pass.

    Results are interned: distinct labels overwhelmingly share closures, and
    without interning a database the size of set.mm holds tens of thousands of
    equal frozensets.
    """
    logical = db.logical_axioms
    out: dict[str, frozenset[str]] = {}
    intern: dict[frozenset[str], frozenset[str]] = {}
    empty: frozenset[str] = frozenset()
    for label in db.order:
        if db.kind[label] == "a":
            s = frozenset((label,)) if label in logical else empty
        else:
            acc: set[str] = set()
            for r in db.refs.get(label, ()):
                c = out.get(r)
                if c:
                    acc |= c
            s = frozenset(acc) if acc else empty
        out[label] = intern.setdefault(s, s)
    return out


@dataclass
class AxiomStat:
    name: str
    dependents: int
    entry_points: int

    @property
    def amplification(self) -> float:
        return self.dependents / self.entry_points if self.entry_points else float("inf")


@dataclass
class Amplification:
    """Axiom spend in one database.

    `reach` is the fraction of theorems depending on an axiom, and is invariant
    under inlining and factoring. `amplification` is dependents per entry point,
    and is NOT: rerouting every use through one gateway lemma, or inlining that
    lemma, changes it without changing what the library proves. Reach therefore
    bears comparison between libraries and amplification describes a single
    library's factorisation. Report accordingly.
    """

    name: str
    theorems: int
    axioms_declared: int
    axioms_used: int
    stats: list[AxiomStat]

    @property
    def median_entries(self) -> float:
        e = sorted(s.entry_points for s in self.stats)
        return statistics.median(e) if e else 0.0

    @property
    def overall(self) -> float:
        d = sum(s.dependents for s in self.stats)
        e = sum(s.entry_points for s in self.stats)
        return d / e if e else 0.0

    def reach(self, axioms: list[str]) -> float:
        by = {s.name: s for s in self.stats}
        return max((by[a].dependents for a in axioms if a in by), default=0) / self.theorems

    def top(self, n: int = 12) -> list[AxiomStat]:
        return sorted(self.stats, key=lambda s: -s.dependents)[:n]


def amplification(path: Path) -> Amplification:
    db = parse(path)
    clos = closures(db)
    thms = db.theorems
    logical = db.logical_axioms
    stats = []
    for a in logical:
        dep = sum(1 for t in thms if a in clos[t])
        if not dep:
            continue
        ent = sum(1 for t in thms if a in db.refs.get(t, ()))
        if ent:
            stats.append(AxiomStat(a, dep, ent))
    return Amplification(
        name=path.name,
        theorems=len(thms),
        axioms_declared=len(logical),
        axioms_used=len(stats),
        stats=stats,
    )
