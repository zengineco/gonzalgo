---
description: Report what a Lean 4 project rests on — inherited sorry, native_decide, and where its axiom dependence comes from
argument-hint: <path-to-lean-project> [--axiom NAME]
---

Use the **lean-axiom-provenance** skill to report what the Lean 4 project at
`$ARGUMENTS` rests on. That skill is the single source for the commands and, more
importantly, for how to read what they return — follow it end to end.

Order of work:

1. Build the environment and generate a dump. Run `gonzalgo check` on it and do
   not proceed until it passes; a dump written without `allowOpaque` reads every
   theorem's proof as empty and every statement-versus-proof figure computed from
   it will be wrong rather than imprecise.
2. `gonzalgo trust` — every theorem reaching a `sorry` anywhere upstream, and
   everything carrying `Lean.ofReduceBool` / `Lean.ofReduceNat`. Where you find
   `sorryAx`, say which kind it is: a `sorry` somebody typed, or a proof that
   failed to elaborate and was admitted anyway. If you cannot tell them apart
   from the evidence, say that instead of guessing.
3. `gonzalgo eligible` — the ceiling on removable classical dependence. Report it
   as a ceiling. A theorem with a choice-free statement can still need excluded
   middle.
4. For anything notable, `gonzalgo why` on the specific declaration, and quote the
   labelled path rather than paraphrasing it.

Honor a `--axiom` in `$ARGUMENTS` if one is given; the default target is
`Classical.choice`.

Finish with a plain verdict — CLEAN / INHERITED-SORRY / COMPILER-TRUSTED /
CLASSICAL-ONLY — the counts behind it, and the exact Lean and Mathlib versions
measured. A count with no version attached goes stale silently.

Do not call a proof wrong because it depends on `Classical.choice`. Nearly all of
Mathlib does, and for most theorems the statement requires it. The finding worth
reporting is dependence the *proof* introduced.
