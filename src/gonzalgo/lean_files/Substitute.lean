/-
  Substitutability test for elaborator-inserted choice in mathlib.

  `Classical.propDecidable : (p : Prop) → Decidable p` is a low-priority
  instance. No author writes it; the elaborator inserts it when it needs
  `Decidable P` and instance search finds nothing better. Every such insertion
  makes the enclosing declaration depend on `Classical.choice`.

  That dependence is INCIDENTAL exactly when a choice-free `Decidable P` was
  available and simply not found — because the relevant instance was not in
  scope at that point, or `open Classical` suppressed the search. This file
  decides that question per site, mechanically:

      1. find every closed subterm `@Classical.propDecidable P` in the
         environment;
      2. ask instance synthesis for `Decidable P` again, now with the whole of
         Mathlib in scope;
      3. run `Lean.collectAxioms` on every constant of the synthesized term.

  If the synthesized instance's axiom closure omits `Classical.choice`, the
  site is REMOVABLE: a constructive instance exists for that exact proposition.
  The verdict comes from Lean's own kernel bookkeeping, not a name heuristic —
  which is the point, since the Metamath phase of this work measured a
  name-based screen at 41.5% precision.

  SOUNDNESS, NOT COMPLETENESS. Only subterms with no loose bound variables are
  tested, so propositions mentioning the enclosing declaration's binders are
  skipped rather than guessed at. The reported list undercounts. Synthesis runs
  under a heartbeat cap; timeouts are counted separately and never reported as
  either verdict.

  A REMOVABLE verdict says a choice-free instance exists for that proposition.
  It does not say the enclosing proof still compiles after substitution: the
  proof may rely on definitional unfolding specific to `propDecidable`. That is
  settled by rebuilding, which this file does not attempt.
-/
import Mathlib
import Lean

open Lean Meta

/-!
Sites are visited with `Meta.transform`, which instantiates binders with real
free variables and registers class-typed ones as local instances. That matters:
essentially every `@Classical.propDecidable P` in mathlib sits under a binder,
so `P` mentions the enclosing declaration's variables, and the `[DecidableEq α]`
arguments that would supply a constructive replacement are themselves binders.
Synthesis must therefore run *inside* the traversal, while that context is
live — a proposition collected and carried out would reference dangling
variables. A first version of this file filtered to closed subterms instead and
found zero sites in the whole library, which is the same fact seen from the
wrong side.
-/

/-- Axiom closure of a term: the union of `collectAxioms` over its constants. -/
def termAxioms (e : Expr) : CoreM NameSet := do
  let mut out : NameSet := {}
  for c in e.getUsedConstants do
    for a in (← collectAxioms c) do
      out := out.insert a
  return out

/-- Bound one synthesis attempt: reset the heartbeat baseline, cap it, and
    permit the resulting exception to be caught.

    Both parts are needed: the cap is measured against the current baseline, so
    it does nothing without the reset. -/
def withCap {α : Type} (n : Nat) (x : MetaM α) : MetaM α :=
  withTheReader Core.Context (fun ctx => { ctx with maxHeartbeats := n }) <|
    Core.withCurrHeartbeats x

/-- The classical decidability fallbacks: instances the elaborator reaches for
    when constructive search fails. Their arities differ, so sites are located
    by head symbol and the goal is recovered from the term's own TYPE rather
    than by picking out an argument position. -/
def fallbacks : Array Name :=
  #[``Classical.propDecidable, ``Classical.dec, ``Classical.decEq,
    ``Classical.decPred, ``Classical.decRel]

/-- Goal shapes worth re-synthesizing. A term still missing arguments has a
    pi type and is skipped. -/
def decidableHeads : Array Name :=
  #[``Decidable, ``DecidablePred, ``DecidableRel, ``DecidableEq]

/-- Re-synthesize the site's own type; classify by the axiom closure of the
    result. Returns a tag and, for a removable site, the witnessing instance.

    Lean classifies heartbeat exhaustion as a RUNTIME exception, which ordinary
    `catch` deliberately re-throws; without `tryCatchRuntimeEx` the first
    expensive site aborts the whole pass instead of being recorded as one
    timeout. -/
def testSite (cap : Nat) (e : Expr) : MetaM (String × String) :=
  withCap cap <|
    tryCatchRuntimeEx
      (do
        let goal ← inferType e
        let some h := goal.getAppFn.constName? | return ("not-a-goal", "")
        unless decidableHeads.contains h do return ("not-a-goal", "")
        match ← synthInstance? goal with
        | none => return ("no-instance", "")
        | some inst =>
            let ax ← termAxioms inst
            if ax.contains ``Classical.choice then
              return ("choice-needed", "")
            else
              return ("REMOVABLE", toString (← ppExpr inst)))
      (fun _ => return ("timeout", ""))

structure Tally where
  sites : Nat := 0
  removable : Nat := 0
  needed : Nat := 0
  noinst : Nat := 0
  notgoal : Nat := 0
  timeout : Nat := 0

/-- Pretty-printed terms contain newlines, which would split one record across
    several TSV lines. Flatten whitespace so each site stays one row. -/
def flat (s : String) : String :=
  s.map (fun c => if c.isWhitespace then ' ' else c)

/-- Visit one declaration's value, testing each fallback site in place. -/
def scanDecl (cap : Nat) (name : Name) (mod : Name) (v : Expr)
    (h : IO.FS.Handle) (tally : IO.Ref Tally) : MetaM Unit := do
  let seen ← IO.mkRef (#[] : Array String)
  let _ ← Meta.transform v (pre := fun e => do
    if let some c := e.getAppFn.constName? then
      if fallbacks.contains c then
        let es ← (do pure (flat (toString (← ppExpr e)))) <|> pure "<unprintable>"
        -- one verdict per distinct site shape per declaration
        unless (← seen.get).contains es do
          seen.modify (·.push es)
          let (tag, witness) ← testSite cap e
          tally.modify fun t =>
            let t := { t with sites := t.sites + 1 }
            match tag with
            | "REMOVABLE"     => { t with removable := t.removable + 1 }
            | "choice-needed" => { t with needed := t.needed + 1 }
            | "no-instance"   => { t with noinst := t.noinst + 1 }
            | "not-a-goal"    => { t with notgoal := t.notgoal + 1 }
            | _               => { t with timeout := t.timeout + 1 }
          h.putStrLn s!"{tag}\t{mod}\t{name}\t{es}\t{flat witness}"
    return .continue)

/-- `only`: if non-empty, restrict the pass to these declaration names. Used to
    re-test just the sites a previous, cheaper pass left undecided, so the
    expensive budget is spent only where the cap actually bound. -/
def run (out : System.FilePath) (cap : Nat) (lo hi : Nat)
    (only : Array String := #[]) : MetaM Unit := do
  let env ← getEnv
  -- append: each round of a sharded run must add to the ledger, not replace it
  let h ← IO.FS.Handle.mk out IO.FS.Mode.append
  let tally ← IO.mkRef ({} : Tally)
  let mut seenDecls := 0
  let mut decls := 0
  for (name, ci) in env.constants.toList do
    let some v := ci.value? (allowOpaque := true) | continue
    unless v.getUsedConstants.any (fallbacks.contains ·) do continue
    unless only.isEmpty || only.contains (toString name) do continue
    seenDecls := seenDecls + 1
    -- shard so a full pass fits inside one interactive run
    unless lo ≤ seenDecls && seenDecls < hi do continue
    decls := decls + 1
    let mod := (env.getModuleFor? name).getD `«?»
    try
      scanDecl cap name mod v h tally
    catch _ =>
      h.putStrLn s!"scan-failed\t{mod}\t{name}\t\t"
    -- flush per declaration: the Mathlib import costs minutes, so a run that
    -- is cut short must still leave every verdict it already reached on disk
    h.flush
    if decls % 100 == 0 then
      let t ← tally.get
      IO.println s!"  ... {decls} decls, {t.sites} sites, {t.removable} removable, {t.timeout} timeout"
  h.flush
  let t ← tally.get
  IO.println s!"declarations citing a fallback (total): {seenDecls}"
  IO.println s!"declarations scanned in this shard:     {decls}"
  IO.println s!"sites tested:                           {t.sites}"
  IO.println s!"  REMOVABLE (choice-free instance)      {t.removable}"
  IO.println s!"  choice genuinely needed               {t.needed}"
  IO.println s!"  no instance found                     {t.noinst}"
  IO.println s!"  not a decidability goal (skipped)     {t.notgoal}"
  IO.println s!"  synthesis timed out                   {t.timeout}"

-- The whole scan is one command; without this it dies on the global heartbeat
-- budget long before the per-synthesis cap in `withCap` ever matters.
set_option maxHeartbeats 0 in
set_option maxRecDepth 10000 in
#eval show MetaM Unit from do
  let txt ← IO.FS.readFile "todo.txt"
  let only := txt.splitOn "
" |>.map (·.trimAscii.toString) |>.filter (· ≠ "") |>.toArray
  IO.println s!"scanning {only.size} remaining declarations"
  run "sites2.tsv" 40000 0 1000000 only
