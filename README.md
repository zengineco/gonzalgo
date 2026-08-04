```
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║    ██████╗  ██████╗ ███╗   ██╗███████╗ █████╗ ██╗      ██████╗     ║
║   ██╔════╝ ██╔═══██╗████╗  ██║╚══███╔╝██╔══██╗██║     ██╔════╝     ║
║   ██║  ███╗██║   ██║██╔██╗ ██║  ███╔╝ ███████║██║     ██║  ███╗    ║
║   ██║   ██║██║   ██║██║╚██╗██║ ███╔╝  ██╔══██║██║     ██║   ██║    ║
║   ╚██████╔╝╚██████╔╝██║ ╚████║███████╗██║  ██║███████╗╚██████╔╝    ║
║    ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚══════╝ ╚═════╝     ║
║                                                                    ║
║        where does a formal library spend its axioms?               ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
```

[![PyPI](https://img.shields.io/pypi/v/gonzalgo)](https://pypi.org/project/gonzalgo/)
[![Python](https://img.shields.io/pypi/pyversions/gonzalgo)](https://pypi.org/project/gonzalgo/)
[![License](https://img.shields.io/pypi/l/gonzalgo)](LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21769847-blue)](https://doi.org/10.5281/zenodo.21769847)

`#print axioms` tells you whether *one* theorem depends on an axiom. It cannot
tell you where an axiom is **spent** rather than inherited, how far that spending
reaches, how much of it could be avoided, or — for a given theorem — **which step
introduced it**. This does.

Works on **Lean 4 / Mathlib** and on **Metamath** databases (`set.mm`,
`iset.mm`, `nf.mm`), by one program, so two foundations are compared under
identical definitions rather than by analogy.

```console
$ pip install gonzalgo
```

Pure Python. macOS, Windows, Linux. `numpy` is the only dependency.

---

## What it found

Pointed at Lean 4.32.1 with Mathlib — 790,171 declarations, 30 million
dependency edges — the funnel from "the whole library" down to "provably
removable" runs like this:

```
   532,605   theorems in Mathlib
  ─────────────────────────────────────────────────────────────────────
   324,808   ██████████████████████████████░░░░░░░░░░  depend on Classical.choice   61.0%
       144   ▏                                         actually SPEND it (entry points)
  ─────────────────────────────────────────────────────────────────────
    69,571   ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  could be stated without it   13.1%
                                                       └─ a ceiling, not an estimate
  ─────────────────────────────────────────────────────────────────────
       805   substitutable sites — a choice-free instance existed, unused
       280   declarations whose ONLY route to the axiom runs through one
       276   ▏ attributable to a single tactic  ────────────────────┐
       275   ▏ kernel-verified choice-free after substitution       │
         4   ▏ kernel REJECTED — and they are exactly the 4 NOT ────┘
             ▏ attributable to that tactic. The partition was not designed.
```

That single tactic is **`omega`**, which supplies the `Decidable` arguments of
six helper lemmas as a hardcoded `Classical.propDecidable` and never attempts
instance synthesis — so proofs as elementary as `a - b = 0 ↔ a ≤ b` over `Nat`
rest on the axiom of choice with no need. Filed upstream; the fix is one file.

---

## How it fits together

```
        your Lean project
               │
               │  gonzalgo lean-files ./scripts
               │  lake env lean scripts/Split.lean
               ▼
     ┌───────────────────────┐
     │   dependency graph    │   one row per declaration:
     │  statement │ proof    │   KIND · NAME · stmt-deps · proof-deps
     └───────────┬───────────┘
                 │
                 │  gonzalgo check      ← refuses a dump with no proof terms
                 ▼
     ┌───────────────────────────────────────────────────┐
     │                                                   │
     ▼                  ▼                ▼               ▼
  amplify           eligible            why            audit
  ───────           ────────            ───            ─────
  where is the      how much is         which step     which sites are
  axiom spent,      even eligible       introduced     substitutable, and
  and how far       for removal?        it?            which declarations
  does it reach?    (the ceiling)                      go clean if you fix
                                                       every one
                                                            │
                                                            ▼
                                                   lake env lean Rewrite.lean
                                                   ───────────────────────────
                                                   swap the instance in and ask
                                                   the KERNEL if the proof holds
```

Nothing above the kernel step is trusted on my say-so: `Substitute.lean` decides
substitutability with `collectAxioms`, and `Rewrite.lean` submits the rewritten
proof term to `addDecl`. A name-based screen was tried first and measured 41.5%
precision, which is why none of this reads names.

---

## Quickstart

Generate a dump from your own Lean project, then ask questions of it.

```console
$ gonzalgo lean-files ./scripts        # writes the Lean extractors
$ cd my-lean-project
$ lake env lean scripts/Split.lean     # -> mathlib_split.tsv
$ gonzalgo check mathlib_split.tsv     # verify it actually contains proofs
```

**Why does this theorem need choice?**

```console
$ gonzalgo why mathlib_split.tsv Int.mem_box

  Int.mem_box
    Int.mem_box
      --proof-->  Int.mem_box._proof_1_5
        --proof-->  Classical.propDecidable
          --proof-->  Classical.choice
```

Every hop is labelled `stmt` or `proof`, and that label is the point: a proof
edge can often be rerouted by changing a tactic, a statement edge cannot be
touched without changing what the theorem says. A path made only of proof edges
is what makes a declaration worth patching at all.

**If I change this, what breaks?**

```console
$ gonzalgo impact mathlib_split.tsv Nat.decLe

  Nat.decLe
    reached transitively    398,968   (295,411 of them theorems)
    ── direct ──
    in a STATEMENT              626   API surface: changing the
                                      type changes their meaning
    in a PROOF only           4,225   insulated: a type-preserving
                                      change costs a recompile
```

`why` run backwards. The statement/proof split is the value: a declaration whose
*type* mentions the target has the target in its API, so its meaning moves when
the target moves and its own users may need rewriting. One that merely calls it
inside a proof needs nothing but a rebuild. A plain "who uses this" cannot tell
them apart, which is why it can't tell you whether a change is safe.

**How far does an axiom reach, and where is it spent?**

```console
$ gonzalgo amplify mathlib_split.tsv

  axiom            Classical.choice
  theorems              532,605
  dependents            324,808   reach 61.0%
  entry points              144   2.704e-04 per theorem
  amplification           2,256x
```

**How much of that could even in principle be removed?**

```console
$ gonzalgo eligible mathlib_split.tsv

  statement CHOICE-FREE, proof dep    69,571   13.1%   <- eligible
  ...
  ceiling on removable classical dependence: 13.1%
```

A theorem whose *statement* mentions something choice-dependent cannot be made
choice-free however it is proved. Only the rest are candidates, and that figure
is a ceiling, not an estimate.

**Metamath, same measurements:**

```console
$ gonzalgo mm set.mm iset.mm nf.mm

  set.mm
    theorems                     47,621
    logical axioms (|-)           1,561   used 1447
    median entries per axiom        2.0
    overall amplification         292.1x
```

---

## Reach versus amplification

Under inlining and factoring — operations that change how a library is written,
not what it proves — the set of *dependents* is invariant while the set of
*entry points* is not. Rerouting every use of an axiom through one gateway
lemma, or inlining that lemma, moves amplification anywhere between 1 and the
number of dependents without changing a single theorem.

So **reach bears comparison between libraries; amplification describes one
library's factorisation.** The tool reports both and this README says which is
which, because the distinction is easy to lose and expensive to lose.

---

## One hazard worth knowing about

In Lean 4.32, `ConstantInfo.value?` returns `none` for **theorems** unless
called as `value? (allowOpaque := true)`, and this has changed across releases.
An extractor written the obvious way records no proof terms at all: every
theorem's value comes back empty, the analysis silently measures statements, and
reports them as proofs. Nothing about the output looks wrong — the library just
appears cleaner than it is.

`gonzalgo check` exists for this, and every subcommand runs it before trusting a
dump:

```console
$ gonzalgo check bad_dump.tsv
ERROR: bad_dump.tsv: 532,605 theorems, none carrying a proof term.
The extractor called `ConstantInfo.value?` without `(allowOpaque := true)` ...
```

It raises rather than warns. A dump with no proof terms does not produce
slightly worse numbers; it produces confidently wrong ones.

---

## Library use

```python
from pathlib import Path
from gonzalgo import lean

dump = Path("mathlib_split.tsv")
lean.check_dump(dump)
g = lean.load(dump)

g.path_to("Int.mem_box", lean.AXIOM)      # why
g.entry_points(lean.AXIOM, among="T")     # where it is spent
g.dependents(lean.AXIOM)                  # boolean mask over all nodes
lean.eligibility(dump, g).ceiling         # what fraction could be removed
```

---

## Shipped Lean sources

`gonzalgo lean-files` writes these into a directory of your choosing:

| file | what it does |
|---|---|
| `Split.lean` | declaration graph, statement and proof deps in separate columns |
| `Substitute.lean` | re-synthesizes each classical-decidability site, classifies by `collectAxioms` |
| `Rewrite.lean` | rewrites proof terms and kernel-checks the substitution |
| `OmegaFix.lean` | a patched `omega` frontend — demonstration only, see below |
| `Extract.lean` | earlier graph dump, superseded by `Split.lean` |

`Substitute.lean` decides substitutability with the kernel's own bookkeeping
rather than by name. A name-based screen measured 41.5% precision on `set.mm`;
its characteristic failure is a lemma that relocates choice into an antecedent
instead of discharging it, which looks like progress and is not.

---

## Background

This package is the tooling behind *Where Formal Libraries Spend Their Axioms:
A Cross-Foundation Measurement, and an Avoidable Classical Dependency in Lean's
`omega`* — [10.5281/zenodo.21769847](https://doi.org/10.5281/zenodo.21769847).

Applied to Lean 4.32.1 with Mathlib (790,171 declarations, 30M dependency
edges), it finds 280 declarations whose only route to `Classical.choice` runs
through a substitutable site, 276 of them attributable to a single cause in the
`omega` decision procedure. Rewriting all 280 proof terms and submitting them to
the kernel: 276 accepted, 4 rejected, 275 left free of `Classical.choice`.

---

## Attribution and licence

Apache-2.0. See `LICENSE` and `NOTICE`.

`OmegaFix.lean` is a **modified copy** of Lean 4's
`src/Lean/Elab/Tactic/Omega/Frontend.lean`, Copyright (c) 2023 Lean FRO, LLC,
used under Apache-2.0. Its modifications are listed in a notice at the top of
that file. It exists to demonstrate that a proposed fix compiles and produces
choice-free proofs; **it is not a replacement for `omega` and should not be used
as one.**

Not affiliated with or endorsed by the Lean FRO or the Mathlib community.
