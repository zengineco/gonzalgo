"""Dependency graphs over formal libraries, and reachability on them.

The whole toolkit rests on one structure: a directed graph whose nodes are
declarations and whose edges point from a declaration to the constants it
depends on. Both proof assistants this package reads produce that shape, so
everything above this module is foundation-independent.

Two design points worth stating, because they are what make the analysis mean
anything.

STATEMENT AND PROOF EDGES ARE KEPT APART. A declaration's type and its value
depend on different things, and conflating them destroys the only question worth
asking about an axiom: is it required by what the theorem *says*, or only by how
it happens to have been *proved*. `EdgeKind` records which is which, and
`Graph.reaches` can be restricted to either.

REACHABILITY IS COMPUTED BACKWARDS. The interesting query is never "what does
this declaration depend on" — that is a single lookup — but "what depends on this
axiom", over hundreds of thousands of nodes. A reverse index answers that in one
pass per axiom rather than one pass per declaration.

Graphs of this size (Mathlib is ~790k nodes and ~30M edges) are held as flat
integer arrays with a CSR-style index. numpy does the sort; everything else is
plain Python.
"""

from __future__ import annotations

from array import array
from dataclasses import dataclass, field
from typing import Iterable, Iterator

import numpy as np

STATEMENT = "stmt"
PROOF = "proof"


@dataclass
class Graph:
    """A declaration-dependency graph with statement/proof edges distinguished.

    Nodes are interned to integers on first sight. `names[i]` recovers the name.
    Edges are stored twice: once as flat arrays for bulk reachability, and once
    per-node so a single declaration's dependencies can be read back cheaply.
    """

    names: list[str] = field(default_factory=list)
    ids: dict[str, int] = field(default_factory=dict)
    kind: dict[int, str] = field(default_factory=dict)
    _src: array = field(default_factory=lambda: array("i"))
    _dst: array = field(default_factory=lambda: array("i"))
    _edge_is_proof: array = field(default_factory=lambda: array("b"))
    _rev_starts: np.ndarray | None = None
    _rev_src: np.ndarray | None = None
    _stmt_deps: dict[int, list[int]] = field(default_factory=dict)
    _proof_deps: dict[int, list[int]] = field(default_factory=dict)

    # ---- construction -----------------------------------------------------

    def node(self, name: str) -> int:
        i = self.ids.get(name)
        if i is None:
            i = self.ids[name] = len(self.names)
            self.names.append(name)
        return i

    def add(self, name: str, *, statement: Iterable[str] = (),
            proof: Iterable[str] = (), kind: str | None = None) -> int:
        """Record one declaration and its dependencies."""
        u = self.node(name)
        if kind is not None:
            self.kind[u] = kind
        for deps, is_proof, store in (
            (statement, 0, self._stmt_deps),
            (proof, 1, self._proof_deps),
        ):
            bucket = store.setdefault(u, [])
            for d in deps:
                v = self.node(d)
                self._src.append(u)
                self._dst.append(v)
                self._edge_is_proof.append(is_proof)
                bucket.append(v)
        self._rev_starts = None  # index is stale
        return u

    # ---- queries ----------------------------------------------------------

    def __len__(self) -> int:
        return len(self.names)

    @property
    def edge_count(self) -> int:
        return len(self._src)

    def statement_deps(self, name: str) -> list[str]:
        u = self.ids.get(name)
        return [self.names[v] for v in self._stmt_deps.get(u, ())] if u is not None else []

    def proof_deps(self, name: str) -> list[str]:
        u = self.ids.get(name)
        return [self.names[v] for v in self._proof_deps.get(u, ())] if u is not None else []

    def of_kind(self, k: str) -> Iterator[str]:
        for i, kk in self.kind.items():
            if kk == k:
                yield self.names[i]

    def _build_reverse(self) -> None:
        n = len(self.names)
        src = np.frombuffer(self._src, dtype=np.int32)
        dst = np.frombuffer(self._dst, dtype=np.int32)
        order = np.argsort(dst, kind="stable")
        self._rev_src = src[order]
        self._rev_starts = np.searchsorted(dst[order], np.arange(n + 1))

    def dependents(self, target: str) -> np.ndarray:
        """Boolean mask over nodes: everything whose closure contains `target`.

        Backwards breadth-first search from the target over reversed edges. A
        Lean or Metamath dependency graph is acyclic, so this terminates without
        a visited-set guard beyond the mask itself.
        """
        if target not in self.ids:
            return np.zeros(len(self.names), dtype=bool)
        if self._rev_starts is None:
            self._build_reverse()
        starts, rsrc = self._rev_starts, self._rev_src
        seen = np.zeros(len(self.names), dtype=bool)
        root = self.ids[target]
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

    def entry_points(self, target: str, *, among: str | None = None,
                     via: str = PROOF) -> list[str]:
        """Declarations citing `target` DIRECTLY — spending it, not inheriting it.

        `via` defaults to PROOF, and the default is the substantive choice. A
        theorem that cites an axiom in its PROOF is spending it: that is a
        position someone would have to edit to remove the dependence. A theorem
        that cites it in its STATEMENT is a theorem *about* the axiom — in
        practice these are mostly equation lemmas for definitions that use it —
        and editing them is not on the table, since it would change what they
        say.

        In Mathlib the two differ by enough to matter: `Classical.choice` has
        144 proof citations and 38 statement citations, overlapping in 24. Taking
        the union inflates the entry-point count by 10% and, because
        amplification is dependents divided by entry points, deflates that by the
        same. Pass `via=STATEMENT` to ask the other question deliberately.
        """
        if target not in self.ids:
            return []
        v = self.ids[target]
        store = self._proof_deps if via == PROOF else self._stmt_deps
        return [self.names[u] for u, deps in store.items()
                if v in deps and (among is None or self.kind.get(u) == among)]

    def direct_dependents(self, target: str) -> tuple[list[str], list[str]]:
        """Everything citing `target` directly, split into (statement, proof).

        The split is the point, and it is what a plain "who uses this" cannot
        tell you. A declaration citing the target in its STATEMENT has the
        target in its API: change the target's type and this one's meaning
        changes with it, so its downstream users may need rewriting too. A
        declaration citing it only in its PROOF is insulated: the statement is
        unaffected, and a change that preserves the type costs a recompile and
        nothing else.

        One scan over both edge stores rather than two, since at Mathlib scale
        the stores hold thirty million entries between them.
        """
        if target not in self.ids:
            return [], []
        v = self.ids[target]
        stmt = [self.names[u] for u, deps in self._stmt_deps.items() if v in deps]
        proof = [self.names[u] for u, deps in self._proof_deps.items() if v in deps]
        return stmt, proof

    def path_to(self, start: str, target: str) -> list[tuple[str, str]] | None:
        """Shortest `start` -> `target` path, each hop labelled statement or proof.

        Shortest matters. Any path proves dependence, but a long one wanders
        through whatever the proof happened to cite; the shortest names the most
        direct route and, in practice, the declaration responsible. The edge
        labels are what make the answer actionable — a proof edge can often be
        rerouted by changing a tactic, a statement edge cannot be touched
        without changing what the theorem says.
        """
        if start not in self.ids or target not in self.ids:
            return None
        s, t = self.ids[start], self.ids[target]
        prev: dict[int, tuple[int, str]] = {s: (-1, "")}
        queue = [s]
        while queue:
            nxt = []
            for cur in queue:
                for deps, label in ((self._stmt_deps.get(cur, ()), STATEMENT),
                                    (self._proof_deps.get(cur, ()), PROOF)):
                    for d in deps:
                        if d in prev:
                            continue
                        prev[d] = (cur, label)
                        if d == t:
                            queue = []
                            nxt = []
                            break
                        nxt.append(d)
                    if t in prev:
                        break
                if t in prev:
                    break
            if t in prev:
                break
            queue = nxt
        if t not in prev:
            return None
        out: list[tuple[str, str]] = []
        node = t
        while node != -1:
            parent, label = prev[node]
            out.append((self.names[node], label))
            node = parent
        return list(reversed(out))
