# Changelog

## 0.2.0 — 2026-08-04

**New: `gonzalgo impact` — `why` run backwards.** Given a declaration, what
breaks if you change it, and how badly:

```
Nat.decLe
  reached transitively    398,968   (295,411 of them theorems)
  in a STATEMENT              626   API surface: their meaning changes with it
  in a PROOF only           4,225   insulated: a type-preserving change rebuilds
```

The split is the whole value. A plain "who uses this" cannot distinguish a
declaration whose *type* mentions the target — whose meaning therefore moves
when the target moves, and whose own users may need rewriting — from one that
merely calls it inside a proof and needs nothing but a recompile.

**Fixed: `why` reported a missing target as "no path".** That is
indistinguishable from a genuine negative, and the two are opposite answers.
Now errors with exit 2 and suggests near matches. A missing *start* declaration
is reported separately, and a real negative reads "does not depend on X".

Found by pointing `why` at an ordinary definition rather than an axiom, which
also demonstrated the more general capability the package had all along:

```
Int.mem_box  --stmt-->  Finset.box  --proof-->  disjointed
```

First hop lives in the statement, second in the body. Nothing about this is
specific to axioms; `-a` accepts any constant.

## 0.1.1 — 2026-08-04

Documentation and packaging only. No change to any behaviour, API or result.

- README rewritten for the project page: the funnel from 532,605 theorems down
  to 275 kernel-verified removals, and a diagram of how the commands fit
  together. 0.1.0's page was built before these existed.
- `Source` and `Issues` links now resolve; on 0.1.0 they pointed at a repository
  that did not exist yet.
- CI added: the test suite runs on Linux, macOS and Windows across Python
  3.10–3.13, which is what makes the cross-platform claim checkable rather than
  asserted.
- Package description no longer contains an em dash. PowerShell 5.1 round-tripped
  it through cp1252 and produced mojibake in the built metadata; the character is
  not worth the failure mode.

## 0.1.0 — 2026-08-03

First release. The measurement pipeline from
[10.5281/zenodo.21769847](https://doi.org/10.5281/zenodo.21769847), packaged.

**Library.** `Graph` with statement and proof edges kept apart, backward
reachability, and shortest labelled path to an axiom. Lean dump reader with a
hard guard on the `allowOpaque` hazard. Metamath parser, closure engine and
amplification. Substitutability audit.

**CLI.** `lean-files`, `check`, `amplify`, `eligible`, `why`, `audit`, `mm`.

**Shipped Lean sources.** `Split.lean`, `Substitute.lean`, `Rewrite.lean`,
`Extract.lean`, and `OmegaFix.lean` — a modified copy of Lean's own
`Frontend.lean`, Apache-2.0, Copyright Lean FRO, shipped for demonstration only.
See `NOTICE`.

Two decisions that are easy to get wrong, and were got wrong first:

- **`check_dump` raises rather than warns** when a dump's theorems carry no
  proof terms. Lean 4.32's `ConstantInfo.value?` returns `none` for theorems
  unless called with `(allowOpaque := true)`, and the resulting numbers are not
  degraded — they are inverted. Every theorem looks constructive because its
  proof is invisible, and nothing about the output looks wrong.

- **`entry_points` counts proof citations by default**, not the union of proof
  and statement citations. A theorem citing an axiom in its proof is spending
  it; a theorem citing it in its statement is a theorem *about* it, in practice
  mostly equation lemmas for definitions that use it. In Mathlib the union
  inflates the count from 144 to 158 and deflates amplification by the same
  proportion.
