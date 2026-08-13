---
name: lean-axiom-provenance
description: >-
  Find out what a Lean 4 project actually rests on, and why. Reports every
  theorem reaching a `sorry` anywhere upstream, everything settled by
  `native_decide` rather than the kernel, and the shortest path from any
  declaration to any axiom with each hop labelled a statement dependency or a
  proof dependency. Use when the user asks what their proof depends on, whether
  a `sorry` is inherited from a dependency, why a theorem needs
  `Classical.choice`, whether that dependence could be removed, what breaks if a
  definition changes, or wants a CI gate that fails on an unfinished proof. Also
  for the same questions about Metamath databases, and for auditing a Lean repo
  or formalization generally — what its trusted base is, whether a green build
  means anything, whether `sorry`, `native_decide` or a custom `axiom` is
  reachable from its headline theorem. This reads proofs the system has already
  checked — it proves nothing and checks no proofs itself.
---

# Lean axiom provenance

`#print axioms` tells you a theorem depends on `Classical.choice`. It does not
tell you which step introduced it, whether the theorem's own statement required
it, or whether a constructive route exists. This skill answers those, over a
whole environment rather than one declaration at a time.

The tool produces facts. Reading them without overclaiming is the hard part and
most of this file is about that.

## Setup

```bash
pip install gonzalgo
```

Analysis runs against a **dump**: a declaration graph written out of a built
Lean environment. Generate it once, then ask it many questions.

```bash
gonzalgo lean-files ./scripts      # writes the Lean extractors
cd my-lean-project
lake build                         # the environment must already be built
lake env lean scripts/Split.lean   # -> mathlib_split.tsv
gonzalgo check mathlib_split.tsv   # verify it contains proof terms
```

**Run `check` and do not skip it.** `ConstantInfo.value?` returns `none` for
theorems unless it is passed `allowOpaque := true`. An extractor written the
obvious way silently reads every theorem's proof as empty, and then every
statement-versus-proof figure is not imprecise, it is measuring statements and
labelling them proofs. `check` is what catches that.

A dump of Mathlib takes about three minutes and roughly 600 MB. For a small
project it is seconds.

If the environment is large, `lake env lean` needs `-D maxErrors=4000` on the
command line. `set_option maxErrors` inside a file is ignored, and without the
flag Lean stops at 100 errors long before the last declaration.

## The questions

**What does this project rest on?**

```bash
gonzalgo trust mathlib_split.tsv
gonzalgo trust mathlib_split.tsv --fail-on-trust   # non-zero exit, for CI
```

Every theorem reaching `sorryAx` anywhere upstream, and everything carrying
`Lean.ofReduceBool` / `Lean.ofReduceNat`, which is what `native_decide` emits —
those results were obtained by compiling and running code and believing the
answer, so the compiler and runtime are trusted rather than the kernel. Lean
warns once, on the line where the `sorry` was typed; it says nothing about a
theorem three files later that uses that lemma and is therefore also not proved.

**Why does this theorem need that axiom?**

```bash
gonzalgo why mathlib_split.tsv Int.mem_box
```

The shortest path from the declaration to the axiom, each hop labelled `stmt` or
`proof`. That label is the whole point. A proof edge can often be rerouted by
changing a tactic. A statement edge cannot be touched without changing what the
theorem says. A path made only of proof edges is what makes a declaration worth
patching.

**Could the dependence be removed?**

```bash
gonzalgo eligible mathlib_split.tsv
```

Reports theorems whose statement is choice-free while their proof is not. Read
the next section before repeating the number.

**If I change this definition, what breaks?**

```bash
gonzalgo impact mathlib_split.tsv Nat.decLe
```

Splits dependents into those naming it in a statement — whose meaning moves when
it moves — and those using it only in a proof, which just recompile.

**Metamath:**

```bash
gonzalgo mm set.mm iset.mm nf.mm ql.mm hol.mm
```

**Reference measurements, no files needed:**

```bash
gonzalgo index
```

## How to read the output

These are the mistakes that get made. Each one has been made in practice.

**Eligible is a ceiling, not a plan.** A theorem whose statement is choice-free
may still require excluded middle to prove. `eligible` bounds what *could* be
removable from above; it never says removal will work. Over Mathlib the ceiling
is 13.1% of theorems. Applied to the constants those theorems rest on it stops
discriminating entirely — above 99% among constants that dominate two or more
theorems — so it cannot be used to choose which one to attack.
`Classical.propDecidable` has a choice-free type, passes the test, is reached by
91,858 theorems, and cannot be made constructive.

**Reach is not responsibility.** The count of theorems that *reach* a constant
and the count that would stop being classical if it were rebuilt differ by 58×
in the first case measured: 116,766 theorems reach `lt_or_eq_of_le`, 2,018 are
dominated by it. When a user asks "how much rests on this", establish which
question they mean. Also: 60.1% of classically dependent theorems in Mathlib
have no responsible constant at all — their immediate dominator is the axiom
itself, so no local repair reaches them.

**A per-tactic rate does not identify a defective tactic.** Scoring tactics by
how often their proofs carry an avoidable classical dependence measures the
population the tactic gets used on. Calibrated against tactics that *cannot*
introduce a classical instance, the background band is 5.8–28.2% in Mathlib and
45–100% in Lean core, and varies as much within a library as between. `grind` is
classical on everything it closes and that is architectural rather than
defective. `norm_num` carries a genuinely avoidable dependence and ranks *below*
the floor. Do not rank tactics by this number.

**`sorryAx` has two very different causes.** One is a `sorry` somebody typed. The
other is a proof that failed to elaborate: Lean admits the declaration into the
environment carrying `sorryAx`, and in an axiom report the two are
indistinguishable. This matters when auditing generated proofs — a declaration
that "compiles" in the sense of appearing in the environment may not have been
proved at all. Say which case you found, or say you cannot tell.

**Distinguish the axiom from its primitives.** In Lean, most classical
dependence arrives through `Classical.propDecidable` and
`Classical.byContradiction` rather than by citing `Classical.choice` directly.
In Metamath, `set.mm` declares full choice, countable choice and dependent
choice as separate axioms, so "depends on choice" does not have to be one bit
there — and more of that library rests on countable choice than on full choice.

**A site can dominate without spending.** A constant can be the sole route to
the axiom for thousands of theorems and contain no direct use of a choice
primitive anywhere beneath it. Rebuilding such a site removes a route, not a
use, and only helps if that route was the only one.

## What not to say

- Do not call a proof wrong because it depends on `Classical.choice`. Nearly all
  of Mathlib does, and for most theorems the statement requires it.
- Do not report "92% depend on choice" without the split. In one generated
  corpus 92.7% depended on choice and 86.1% of those were bound by the
  statement — the theorems are about the reals, which Mathlib builds with
  choice. Only 6.5% were introduced by the proof. Separating those is what makes
  the first number mean anything.
- Do not claim a theorem is constructively provable. This tool reports what a
  proof rests on; it does not search for another proof.
- Do not present a count from one Lean or Mathlib version as current. Say which
  version was measured. The figures above are Lean 4.32.1 with Mathlib v4.32.1.

## Related tools

For a pass/fail axiom allowlist in CI and nothing more,
`leanprover-community/axiom-audit` is Lean-native and needs no Python. For
deciding whether a repository's headline theorem is vacuous — defined to be
`True`, aliased, or parked in a hypothesis —
`LionSR/is-my-lean-proof-vacuous` targets that directly. This skill is for
provenance: which step, and whether the statement required it.

## Published measurements

Twelve tables of what formal libraries rest on, as JSON and CSV under CC-BY-4.0:
<https://f-keys.com/gonzalgo/data/> · DOI
[10.5281/zenodo.21900625](https://doi.org/10.5281/zenodo.21900625)

Method and definitions: Gonzalez, V. (2026). *Where Formal Libraries Spend Their
Axioms*. Zenodo. [10.5281/zenodo.21769846](https://doi.org/10.5281/zenodo.21769846)
