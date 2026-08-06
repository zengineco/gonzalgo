/-
  Declaration-graph extraction, with a theorem's STATEMENT kept apart from its
  PROOF.

  `#print axioms` answers one theorem at a time, and only whether rather than
  why. Answering the global questions — where an axiom is *spent* as opposed to
  inherited, how far that spending reaches, which step introduced it — needs the
  whole graph, so this writes it out and the analysis happens outside Lean.

  Output is one tab-separated row per declaration:

      KIND <tab> NAME <tab> statement-deps <tab> proof-deps <tab> module

  KIND is A (axiom), T (theorem), D (definition) or O (other). The dependency
  columns are space-separated constant names.

  Why the two dependency columns are separate: a theorem whose statement is
  choice-free but whose proof is choice-dependent is a candidate for having the
  classical reasoning removed — nothing it *says* requires choice, only how it
  happens to have been proved. A theorem whose statement already mentions
  something choice-dependent can never be made choice-free however it is proved.
  Unioning the columns discards exactly that distinction.

  Copyright (c) 2026 Vince Gonzalez. Apache-2.0.
-/
import Lean

namespace Gonzalgo

open Lean

/-- One letter per declaration kind, so the dump stays small on libraries with
hundreds of thousands of declarations. -/
def kindOf : ConstantInfo → String
  | .axiomInfo _ => "A"
  | .thmInfo _   => "T"
  | .defnInfo _  => "D"
  | _            => "O"

/-- The constants an expression mentions, space separated. -/
def consts (e : Expr) : String :=
  String.intercalate " " (e.getUsedConstants.toList.map (·.toString))

/--
The constants a declaration's PROOF (or body) mentions.

`ConstantInfo.value?` returns `none` for theorems unless it is passed
`allowOpaque := true`. An extractor written the obvious way therefore sees no
proof terms at all, silently measures statements, and reports them as proofs —
every statement-versus-proof figure computed from such a dump is wrong rather
than merely imprecise. This cost the original study a full round of results.
-/
def proofConsts (ci : ConstantInfo) : String :=
  match ci.value? (allowOpaque := true) with
  | some v => consts v
  | none   => ""

/--
The module a declaration was defined in.

A Lean name carries no package information whatever — `Int.mem_box` is Mathlib
and `Nat.decLe` is core — so without this column the environment cannot be split
per library and only whole-environment totals are measurable.
-/
def moduleOf (env : Environment) (name : Name) : Name :=
  match env.getModuleIdxFor? name with
  | some idx => env.header.moduleNames[idx.toNat]?.getD `«?»
  | none     => `«?»   -- defined in this file rather than imported

/--
Write the declaration graph of the current environment to `out`.

Call it from a file that imports whatever you want measured:

    import MyProject
    import Gonzalgo.Extract
    #eval Gonzalgo.dumpSplit "myproject.tsv"

Everything reachable from the imports is included, so importing `Mathlib` dumps
Mathlib and its dependencies together; the module column is what separates them
afterwards.
-/
def dumpSplit (out : System.FilePath) : CoreM Unit := do
  let env ← getEnv
  let h ← IO.FS.Handle.mk out IO.FS.Mode.write
  let mut n : Nat := 0
  for (name, ci) in env.constants.toList do
    h.putStrLn s!"{kindOf ci}\t{name}\t{consts ci.type}\t{proofConsts ci}\t{moduleOf env name}"
    n := n + 1
  h.flush
  IO.println s!"declarations written: {n}"
  IO.println s!"now run:  gonzalgo check {out}"

end Gonzalgo
