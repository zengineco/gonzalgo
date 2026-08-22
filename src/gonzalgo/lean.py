"""Reading Lean 4 environment dumps, and the analyses built on them.

A dump is produced by `Split.lean` (shipped in this package, see
`gonzalgo.lean_files`) and is a TSV with one row per declaration:

    KIND <tab> NAME <tab> statement-deps <tab> proof-deps

KIND is A (axiom), T (theorem), D (definition) or O (anything else).

THE `allowOpaque` HAZARD. Lean's `ConstantInfo.value?` returns `none` for
THEOREMS unless called as `value? (allowOpaque := true)`, and that behaviour has
changed across releases. An extractor written the obvious way therefore records
no proof terms at all: every theorem's value column comes back empty, the tool
silently measures statements, and reports them as proofs. Nothing about the
output looks wrong. `check_dump` exists to catch exactly this, and callers
should run it before trusting any number.
"""

from __future__ import annotations

import gzip
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .graph import Graph

AXIOM = "Classical.choice"

#: Instances the elaborator reaches for when constructive search fails. Their
#: arities differ, so anything that locates them must go by head symbol.
FALLBACKS = frozenset({
    "Classical.propDecidable", "Classical.dec", "Classical.decEq",
    "Classical.decPred", "Classical.decRel",
})

#: Escape hatches worth auditing, and why each one matters. These are not
#: interchangeable and a report that lumps them together is useless.
#:
#: `sorryAx` means a proof is unfinished. Lean warns about the `sorry` you just
#: typed; it does not tell you that a theorem three hundred files downstream
#: silently inherits one. That is a graph question, and this is a graph.
#:
#: `Lean.ofReduceBool` and `Lean.ofReduceNat` are what `native_decide` emits:
#: the result was obtained by compiling and running code, and believing the
#: answer. That trusts the compiler and the runtime, not the kernel, and real
#: soundness bugs have been found there. Mathlib restricts it by policy.
#:
#: `Lean.trustCompiler` is the same species, asserted directly.
#:
#: The three classical axioms are listed for completeness. Every Mathlib theorem
#: rests on `propext` and `Quot.sound`, so their presence is uninformative;
#: `Classical.choice` is informative but its removal is a stated non-goal of
#: Lean core, which the report says rather than implying a defect.
ESCAPE_HATCHES: dict[str, str] = {
    "sorryAx": "UNFINISHED PROOF - this result is not proved at all",
    "Lean.ofReduceBool": "native_decide - trusts the compiler, not the kernel",
    "Lean.ofReduceNat": "native_decide - trusts the compiler, not the kernel",
    "Lean.trustCompiler": "trusts the compiler, not the kernel",
    "Classical.choice": "classical - removal is a stated non-goal of Lean core",
    "propext": "standard - every Mathlib theorem rests on this",
    "Quot.sound": "standard - every Mathlib theorem rests on this",
}

#: Presence of these says nothing; excluded from the headline count.
UNREMARKABLE = frozenset({"propext", "Quot.sound"})


def _open(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return io.open(path, encoding="utf-8", errors="replace")


def rows(path: Path) -> Iterator[list[str]]:
    # `with`, because this is a generator: a caller that stops early would
    # otherwise leave the dump open until the frame is collected, which on
    # Windows blocks the next write to the same path.
    with _open(path) as handle:
        for line in handle:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2:
                yield p


def load(path: Path) -> Graph:
    """Read a `Split.lean` dump into a graph."""
    g = Graph()
    for p in rows(path):
        g.add(
            p[1],
            kind=p[0],
            statement=p[2].split() if len(p) > 2 and p[2] else (),
            proof=p[3].split() if len(p) > 3 and p[3] else (),
        )
    return g


class DumpError(RuntimeError):
    pass


def check_dump(path: Path) -> dict[str, int]:
    """Guard against a dump that silently contains no proof terms.

    Raises rather than warning. A dump with no theorem values does not produce
    slightly worse numbers, it produces confidently wrong ones — every
    statement-versus-proof figure collapses and the library looks cleaner than
    it is. This cost the original study a complete round of results, caught only
    because a 2x2 classification returned exactly zero in both off-diagonal
    cells. An exact zero over half a million cases is a bug or an identity; it
    is never a statistic.
    """
    stats = {"declarations": 0, "theorems": 0, "theorems_with_proof": 0}
    for p in rows(path):
        stats["declarations"] += 1
        if p[0] == "T":
            stats["theorems"] += 1
            if len(p) > 3 and p[3].strip():
                stats["theorems_with_proof"] += 1
    if stats["theorems"] and not stats["theorems_with_proof"]:
        raise DumpError(
            f"{path.name}: {stats['theorems']:,} theorems, none carrying a proof "
            "term. The extractor called `ConstantInfo.value?` without "
            "`(allowOpaque := true)`, so every proof is invisible and any "
            "statement-versus-proof figure computed from this dump is wrong. "
            "Re-extract with Split.lean from this package."
        )
    return stats


# ---- statement versus proof ---------------------------------------------


@dataclass
class Eligibility:
    """How much classical dependence is even a candidate for removal.

    A theorem whose STATEMENT mentions something choice-dependent cannot be made
    choice-free however it is proved. Only theorems with a choice-free statement
    and a choice-dependent proof are eligible, and that count is a ceiling, not
    an estimate: many of them need classical *logic* even where the statement is
    constructive.
    """

    theorems: int = 0
    stmt_and_proof: int = 0
    stmt_only: int = 0
    proof_only: int = 0
    neither: int = 0

    @property
    def ceiling(self) -> float:
        return self.proof_only / self.theorems if self.theorems else 0.0


def eligibility(path: Path, graph: Graph, axiom: str = AXIOM) -> Eligibility:
    dep = graph.dependents(axiom)
    ids = graph.ids
    out = Eligibility()
    for p in rows(path):
        if p[0] != "T":
            continue
        out.theorems += 1
        td = p[2].split() if len(p) > 2 and p[2] else []
        pd = p[3].split() if len(p) > 3 and p[3] else []
        st = any(dep[ids[d]] for d in td if d in ids)
        pr = any(dep[ids[d]] for d in pd if d in ids)
        if st and pr:
            out.stmt_and_proof += 1
        elif st:
            out.stmt_only += 1
        elif pr:
            out.proof_only += 1
        else:
            out.neither += 1
    return out


# ---- substitutability verdicts -------------------------------------------


def real_witness(w: str) -> bool:
    """Is the proposed replacement a library instance, or an artifact?

    Two artifact classes are excluded, and together they are large enough that
    ignoring the distinction inflates the result by roughly half. A bare
    identifier is a `Decidable` hypothesis already in scope: the elaborator
    arguably should have used it, but there is no library instance to substitute
    and nothing to patch. A witness containing Lean's inaccessible-name marker is
    that same case with arguments applied, which a whitespace test alone lets
    through.
    """
    w = w.strip()
    if not w or "✝" in w:
        return False
    return " " in w or "." in w


@dataclass
class Audit:
    """Three quantities, weakest to strongest. Only the last is worth quoting."""

    verdicts: int = 0
    sites: int = 0            # substitutable positions with a real witness
    declarations: int = 0     # distinct declarations containing one
    cleanable: int = 0        # whose ONLY route to the axiom runs through one
    blocked: int = 0
    cleanable_names: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.cleanable_names is None:
            self.cleanable_names = []


def audit(sites_path: Path, dump_path: Path, graph: Graph,
          axiom: str = AXIOM) -> Audit:
    """Turn per-site verdicts into a per-declaration claim.

    A site says a choice-free instance exists at one position. That is necessary
    for removal and nowhere near sufficient: a proof may contain a substitutable
    case-split and still reach the axiom by several other routes, in which case
    fixing the site changes the site and nothing else. `cleanable` is the subset
    where every route runs through a substitutable position.
    """
    hits, seen = [], set()
    with _open(sites_path) as handle:
        for line in handle:
            r = line.rstrip("\n").split("\t")
            if len(r) < 5:
                continue
            seen.add(r[2])
            if r[0] == "REMOVABLE" and real_witness(r[4]):
                hits.append(r)
    hit_decls = {r[2] for r in hits}

    dep = graph.dependents(axiom)
    ids = graph.ids
    cleanable, blocked = set(), set()
    for p in rows(dump_path):
        if len(p) < 4 or p[1] not in hit_decls:
            continue
        others = [x for x in p[3].split() if x not in FALLBACKS]
        if any(dep[ids[x]] for x in others if x in ids):
            blocked.add(p[1])
        else:
            cleanable.add(p[1])

    return Audit(
        verdicts=len(seen),
        sites=len(hits),
        declarations=len(hit_decls),
        cleanable=len(cleanable),
        blocked=len(blocked),
        cleanable_names=sorted(cleanable),
    )
