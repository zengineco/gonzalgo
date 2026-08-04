"""Measure where a formal library spends its axioms.

`#print axioms` answers one theorem at a time, and only whether rather than why.
This package answers the global and comparative questions: where an axiom is
spent as opposed to inherited, how far that spending reaches, how much of it
could be avoided, and — for a given declaration — which step introduced it.

    from pathlib import Path
    from gonzalgo import lean

    dump = Path("mathlib_split.tsv")
    lean.check_dump(dump)              # raises if proof terms are missing
    g = lean.load(dump)
    print(g.path_to("Int.mem_box", lean.AXIOM))

Metamath databases are read by `gonzalgo.metamath` with the same measurements,
so two foundations are compared by one program rather than by analogy.
"""

from . import graph, lean, lean_files, metamath
from .graph import Graph, PROOF, STATEMENT
from .lean import AXIOM, Audit, DumpError, Eligibility

__version__ = "0.2.0"
__all__ = [
    "graph", "lean", "lean_files", "metamath",
    "Graph", "PROOF", "STATEMENT",
    "AXIOM", "Audit", "DumpError", "Eligibility",
    "__version__",
]
