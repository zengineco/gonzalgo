"""Access to the Lean sources shipped with this package.

These are the extractors and checkers that produce the data everything else
reads. They are shipped as files rather than embedded strings so they can be
dropped straight into a Lake project and run.

    Extract.lean     declaration graph (superseded by Split.lean)
    Split.lean       declaration graph, statement and proof deps separated
    Substitute.lean  per-site substitutability verdicts
    Rewrite.lean     rewrite proof terms and kernel-check the result
    OmegaFix.lean    patched omega frontend, for demonstration only

`OmegaFix.lean` is a modified copy of Lean's own source; see the notice at the
top of that file and the NOTICE file in this distribution.
"""

from __future__ import annotations

from pathlib import Path

DIR = Path(__file__).parent / "lean_files"

NAMES = ("Extract.lean", "Split.lean", "Substitute.lean",
         "Rewrite.lean", "OmegaFix.lean")


def paths() -> list[Path]:
    return [DIR / n for n in NAMES if (DIR / n).exists()]


def path(name: str) -> Path:
    p = DIR / name
    if not p.exists():
        raise FileNotFoundError(f"{name} is not shipped; have {list(NAMES)}")
    return p


def read(name: str) -> str:
    return path(name).read_text(encoding="utf-8")
