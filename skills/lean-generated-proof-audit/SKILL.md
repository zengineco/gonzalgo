---
name: lean-generated-proof-audit
description: >-
  Check whether a machine-generated Lean 4 proof actually proves its theorem. A
  proof can appear in the environment, pass `lake build`, and still not have been
  proved: when elaboration fails Lean admits the declaration carrying `sorryAx`,
  which an axiom report cannot tell apart from a `sorry` somebody typed. Use when
  auditing output from a prover or an LLM, scoring a proof benchmark, asking
  whether an AI-written proof is real, whether a green build means anything,
  whether `native_decide` was used, or why a generated corpus depends on the axiom
  of choice. Also for reporting a pass rate honestly. Reads proofs Lean has
  already checked; proves nothing itself.
---

# Auditing machine-generated Lean proofs

Compilation is not verification. This is established — SorryDB (arXiv 2603.02668),
AXLE (arXiv 2606.26442) and *Faults in Our Formal Benchmarking* (arXiv 2606.29493)
all say so, and the last recommends checking `#print axioms` output. What the
field has not published is how much difference the check makes.

One measurement exists. Over 10,000 Goedel-Prover outputs on the Lean Workbook
problems, **560 were admitted into the environment carrying `sorryAx`** — present,
counted by a naive compile check, not proved. With 1 unparsable header and 270
that never entered the environment, 831 of 10,000 are excluded and the real
denominator is 9,169.

## Setup

```bash
pip install gonzalgo
```

```bash
gonzalgo lean-files ./scripts
lake build
lake env lean -D maxErrors=4000 scripts/Split.lean   # -> dump.tsv
gonzalgo check dump.tsv
```

`gonzalgo check` is not optional. `ConstantInfo.value?` returns `none` for theorems
unless passed `allowOpaque := true`, and an extractor written the obvious way reads
every proof as empty while reporting statement figures as proof figures.
`-D maxErrors=4000` must be on the command line; `set_option maxErrors` inside a
file is ignored, and a generated corpus produces errors early and often.

## The audit

**1. Establish the denominator before anything else.**

Count what entered the environment, what failed to parse, and what carries
`sorryAx`. Those three are different populations and mixing them is how a pass
rate gets overstated. Report the corpus size, the excluded count with its reasons,
and the number that actually compiled — and check that they sum.

```bash
gonzalgo trust dump.tsv
```

**2. Separate the three outcomes of a failed proof.**

Lean's `sorry` is implemented by `sorryAx`, and the elaborator emits a *synthetic*
one when a tactic fails to close a goal or an expression fails to typecheck.

1. A `sorry` in the source. In the environment, carrying `sorryAx`.
2. A failed elaboration that was admitted anyway. Also in the environment, also
   carrying `sorryAx`, and identical to case 1 in an axiom report.
3. A failure whose declaration **never entered the environment**. Invisible to an
   axiom report, because there is nothing there to report on.

Case 3 is the one that has actually fooled a benchmark. Lean issue #8212: `apply?`
created a synthetic `sorry` without logging an error, so `lake build --wfail` exited
0 while the theorem was never added — and DeepSeek-Prover-V2 output hit exactly
that. Kim Morrison's rule on Zulip is the one to follow: verify that the
declaration you are claiming to have proved is in the environment.

So an audit needs two passes, not one: what was submitted versus what entered the
environment, then what entered versus what carries `sorryAx`. In the measured
corpus that split was 1 unparsable header, 270 that never entered, 560 admitted
with `sorryAx`. Cases 1 and 2 need the source or build log to separate; if you
cannot, say so rather than choosing.

**3. Check for compiler-trusted results.**

`native_decide` emits `Lean.ofReduceBool` / `Lean.ofReduceNat`. Those results were
obtained by compiling and running code and believing the output, so the compiler
and runtime are trusted instead of the kernel. In a benchmark context that is a
different claim from "the kernel verified it."

**4. Check for axioms outside the standard three.**

Anything beyond `propext`, `Quot.sound` and `Classical.choice` is a custom axiom.
This is the failure mode where a hard theorem is assumed and then applied — a
`p_equals_np` resting on `cook_np_completeness` as an axiom compiles perfectly.

**5. Split choice dependence by statement versus proof.**

```bash
gonzalgo eligible dump.tsv
```

This is what makes a choice-dependence figure mean anything. In the measured
corpus, 92.7% of compiled proofs depended on the axiom of choice — and 86.1% were
bound by the **statement**, because the theorems are about the reals and Mathlib
builds those with choice. No proof of such a statement avoids it. Only 6.5%
carried a dependence the proof introduced.

Reporting 92.7% alone is alarming and close to meaningless. Reporting the split is
the whole contribution.

## Reporting a rate honestly

State all of: corpus size, how many entered the environment, how many carry
`sorryAx` and why, the denominator you used, and the Lean and Mathlib versions. A
pass rate with no denominator definition is not checkable, and two papers using
different definitions are not comparable.

If a published rate used a compile-only check, say what recomputing it under a
kernel check would require rather than asserting a corrected figure you have not
computed.

## What not to conclude

- A proof depending on `Classical.choice` is not wrong. Nearly all of Mathlib does.
- A model is not dishonest because its output carries `sorryAx`. Lean admitted the
  declaration; that is the system's behaviour, not the model's intent.
- Do not report a corrected pass rate for a corpus you have not measured yourself.
- Do not claim a theorem is constructively provable. This reports what a proof
  rests on and does not search for another proof.

## Related

`lean-axiom-provenance` (same package) answers *why* a given declaration depends
on an axiom, with each hop labelled statement or proof. For deciding whether a
headline theorem is vacuous — defined to be `True`, aliased, or parked in a
hypothesis — `LionSR/is-my-lean-proof-vacuous` targets that directly.

To publish what an audited corpus rests on in a fixed shape, the Kernel Trust
Profile specifies one: <https://f-keys.com/gonzalgo/kernel-trust/> · [10.5281/zenodo.21913736](https://doi.org/10.5281/zenodo.21913736)

Measured tables, JSON and CSV, CC-BY-4.0: <https://f-keys.com/gonzalgo/data/> ·
DOI [10.5281/zenodo.21900625](https://doi.org/10.5281/zenodo.21900625)
