/-
  Declaration-graph extractor for mathlib.

  Walks the whole environment and writes one TSV line per declaration:

      KIND <tab> NAME <tab> dep1 dep2 ...

  KIND is A (axiom), T (theorem), D (definition), or O (other: constructors,
  recursors, inductives, opaque). Dependencies are the constants appearing in
  the declaration's VALUE (its proof term or body) together with those in its
  TYPE, since both are part of what the declaration rests on.

  Extraction only — no analysis here. The dependency closure, entry-point
  counting and amplification statistics are computed by the same Python
  machinery already used for the Metamath databases, so the two library
  families are measured by identical code.

  Internal and auto-generated names (`_private`, `.proof_1`, match auxiliaries,
  equation lemmas) are kept: they carry real dependencies, and excluding them
  would silently reroute inheritance. Filtering is a decision for the analysis
  stage, where it can be made explicit and varied.
-/
import Mathlib
import Lean

open Lean

def kindOf : ConstantInfo → String
  | .axiomInfo _  => "A"
  | .thmInfo _    => "T"
  | .defnInfo _   => "D"
  | _             => "O"

def dumpDeps (out : System.FilePath) : CoreM Unit := do
  let env ← getEnv
  IO.FS.withFile out IO.FS.Mode.write fun h => do
    let mut n : Nat := 0
    for (name, ci) in env.constants.toList do
      let mut deps : NameSet := {}
      for c in ci.type.getUsedConstants do
        deps := deps.insert c
      if let some v := ci.value? then
        for c in v.getUsedConstants do
          deps := deps.insert c
      let ds := deps.toList.map (·.toString)
      h.putStrLn s!"{kindOf ci}\t{name}\t{String.intercalate " " ds}"
      n := n + 1
    IO.println s!"declarations written: {n}"

#eval dumpDeps "mathlib_deps.tsv"
