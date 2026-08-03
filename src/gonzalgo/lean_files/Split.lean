/-
  Declaration-graph extractor, STATEMENT and PROOF kept apart.

      KIND <tab> NAME <tab> type-deps <tab> value-deps

  The earlier extractor unioned the constants of a declaration's type with those
  of its value, which is right for asking what a declaration rests on, and wrong
  for the question here.

  A theorem whose STATEMENT is choice-free but whose PROOF is choice-dependent is
  the candidate population for "incidental" classical reasoning: nothing in what
  the theorem says requires choice, only how it happens to have been proved. The
  size of that population is an upper bound on how much classical dependence
  could in principle be removed, and it is computable without claiming any
  particular proof can actually be rewritten.

  The converse class matters too and is counted the same way: theorems whose
  statement already mentions choice-dependent constants (anything built over the
  reals, ultrafilters, ordinals) can never be made choice-free, however they are
  proved. Separating the two is the whole point of this pass.

  Extraction only. Closures and counts are computed by the same Python used on
  the Metamath databases, so both library families are measured by one program.
-/
import Mathlib
import Lean

open Lean

def kindOf : ConstantInfo → String
  | .axiomInfo _  => "A"
  | .thmInfo _    => "T"
  | .defnInfo _   => "D"
  | _             => "O"

def consts (e : Expr) : String :=
  String.intercalate " " (e.getUsedConstants.toList.map (·.toString))

def dumpSplit (out : System.FilePath) : CoreM Unit := do
  let env ← getEnv
  let h ← IO.FS.Handle.mk out IO.FS.Mode.write
  let mut n : Nat := 0
  for (name, ci) in env.constants.toList do
    let tdeps := consts ci.type
    -- 4.32 hides THEOREM proof terms behind allowOpaque; without it every
    -- proof in the library reads as empty and only statements are measured
    let vdeps := match ci.value? (allowOpaque := true) with
      | some v => consts v
      | none   => ""
    h.putStrLn s!"{kindOf ci}\t{name}\t{tdeps}\t{vdeps}"
    n := n + 1
  h.flush
  IO.println s!"declarations written: {n}"

#eval dumpSplit "mathlib_split.tsv"
