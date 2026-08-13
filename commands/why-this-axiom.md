---
description: Explain why a Lean declaration depends on an axiom, and whether that dependence could be rerouted
argument-hint: <declaration> [--axiom NAME] [--dump PATH]
---

Use the **lean-axiom-provenance** skill to explain why the declaration named in
`$ARGUMENTS` depends on an axiom, and whether the dependence is one that could be
rerouted.

Run `gonzalgo why` against the project's dump and read the path it returns. Each
hop is labelled `stmt` or `proof` and that label carries the answer:

- A **statement** edge means the theorem's own type mentions something that
  reaches the axiom. Removing it changes what the theorem says. Report it as
  required, not as a defect.
- A **proof** edge means a tactic or lemma choice put it there. A path made only
  of proof edges is the case worth investigating.

Then say what would actually be involved:

- `gonzalgo impact` on the constant the path passes through, to show what a change
  would touch, split into dependents that name it in a statement and dependents
  that only use it in a proof.
- Whether the constant is one that can be made constructive at all. A choice-free
  *type* does not imply a constructive *instance* exists —
  `Classical.propDecidable` has a choice-free type, is reached by 91,858 theorems,
  and cannot be replaced.

Quote the path verbatim. Do not claim a constructive proof exists; this reports
what the existing proof rests on and does not search for another one. If the
answer is that the dependence is required by the statement, say so plainly — that
is a real answer and the common one.
