/-
  Does the substitution preserve the proof?

  Everything up to now established that a choice-free `Decidable` instance
  EXISTS at each site. That is not the same as the proof surviving once the
  instance is swapped in: `Decidable` is data, not a proposition, so two
  instances for the same proposition are interchangeable only up to whatever
  definitional unfolding the surrounding proof relies on. A proof that closes a
  goal by `rfl` on something that computes through `propDecidable` will break.

  This file settles it, per declaration, without rebuilding Lean:

      take the stored proof term
      replace every classical decidability site with the synthesized instance
      hand the result to the KERNEL against the original, unchanged type
      run collectAxioms on what the kernel accepted

  `addDecl` is the real type-checker, not the elaborator, so acceptance here is
  the same standard a rebuild would apply to the resulting term. What it does
  NOT test is whether the original *source syntax* would re-elaborate to this
  term under a patched `omega`; that remains a rebuild question. It tests the
  claim actually made in the paper — that substituting the instance leaves a
  valid proof of the same statement.

  Output, one row per declaration:

      status  name  replaced  left  choiceBefore  choiceAfter  detail
-/
import Mathlib
import Lean

open Lean Meta

def fallbacks : Array Name :=
  #[``Classical.propDecidable, ``Classical.dec, ``Classical.decEq,
    ``Classical.decPred, ``Classical.decRel]

def decidableHeads : Array Name :=
  #[``Decidable, ``DecidablePred, ``DecidableRel, ``DecidableEq]

def termAxioms (e : Expr) : CoreM NameSet := do
  let mut out : NameSet := {}
  for c in e.getUsedConstants do
    for a in (← collectAxioms c) do
      out := out.insert a
  return out

def withCap {α : Type} (n : Nat) (x : MetaM α) : MetaM α :=
  withTheReader Core.Context (fun ctx => { ctx with maxHeartbeats := n }) <|
    Core.withCurrHeartbeats x

/-- Replace each classical decidability site by a synthesized choice-free
    instance. Sites where synthesis fails, or returns something that still
    rests on choice, are left exactly as they are and counted. -/
def rewriteValue (v : Expr) : MetaM (Expr × Nat × Nat) := do
  let done ← IO.mkRef 0
  let kept ← IO.mkRef 0
  let v' ← Meta.transform v (pre := fun e => do
    if let some c := e.getAppFn.constName? then
      if fallbacks.contains c then
        let r ← withCap 40000 <| tryCatchRuntimeEx (do
          let ty ← inferType e
          let some h := ty.getAppFn.constName? | return none
          unless decidableHeads.contains h do return none
          match ← trySynthInstance ty with
          | .some inst =>
              if (← termAxioms inst).contains ``Classical.choice then
                return none
              else
                return some inst
          | _ => return none)
          (fun _ => return none)
        match r with
        | some inst => done.modify (· + 1); return .done inst
        | none      => kept.modify (· + 1)
    return .continue)
  return (v', ← done.get, ← kept.get)

/-- Kernel-check the rewritten term against the original type. -/
def checkRewrite (name : Name) (ci : ConstantInfo) (v' : Expr) :
    MetaM (Bool × String × NameSet) := do
  let newName := name ++ `subst
  let cv : ConstantVal :=
    { name := newName, levelParams := ci.levelParams, type := ci.type }
  let decl : Declaration :=
    match ci with
    | .defnInfo d =>
        .defnDecl { toConstantVal := cv, value := v',
                    hints := d.hints, safety := d.safety, all := [newName] }
    | _ =>
        .thmDecl { toConstantVal := cv, value := v', all := [newName] }
  try
    addDecl decl
    let axs ← collectAxioms newName
    let mut s : NameSet := {}
    for a in axs do s := s.insert a
    return (true, "", s)
  catch e =>
    let msg := ((← e.toMessageData.toString).replace "\n" " ").take 160
    return (false, msg.toString, {})

def flat (s : String) : String := s.map (fun c => if c.isWhitespace then ' ' else c)

def run (todo : System.FilePath) (out : System.FilePath) : MetaM Unit := do
  let txt ← IO.FS.readFile todo
  let names := txt.splitOn "\n" |>.map (·.trimAscii.toString) |>.filter (· ≠ "")
  let h ← IO.FS.Handle.mk out IO.FS.Mode.append
  let env ← getEnv
  let mut n := 0
  let mut ok := 0
  let mut broke := 0
  let mut cleaned := 0
  for nm in names do
    let name := nm.toName
    let some ci := env.find? name | continue
    let some v := ci.value? (allowOpaque := true) | continue
    n := n + 1
    let before ← collectAxioms name
    let hadChoice := before.contains ``Classical.choice
    let res ← tryCatchRuntimeEx (do
        let (v', d, k) ← rewriteValue v
        if d == 0 then
          return (false, "no site rewritten", (0 : Nat), k, ({} : NameSet))
        let (okk, err, ax) ← checkRewrite name ci v'
        return (okk, err, d, k, ax))
      (fun e => do
        let msg := ((← e.toMessageData.toString).replace "\n" " ").take 120
        return (false, msg.toString, 0, 0, ({} : NameSet)))
    let (okk, err, d, k, ax) := res
    let stillChoice := ax.contains ``Classical.choice
    if okk then
      ok := ok + 1
      if hadChoice && !stillChoice then cleaned := cleaned + 1
    else broke := broke + 1
    let status := if !okk then "FAIL" else if stillChoice then "kept-choice" else "CLEAN"
    h.putStrLn s!"{status}\t{name}\t{d}\t{k}\t{hadChoice}\t{stillChoice}\t{flat err}"
    h.flush
    if n % 25 == 0 then
      IO.println s!"  ... {n} checked, {ok} kernel-accepted, {cleaned} now choice-free, {broke} rejected"
  IO.println s!"declarations checked          {n}"
  IO.println s!"  kernel ACCEPTED the rewrite {ok}"
  IO.println s!"  kernel REJECTED             {broke}"
  IO.println s!"  choice-dependent -> free    {cleaned}"

-- async elaboration defers the kernel check past the try/catch, so a real
-- rejection surfaces after the loop and is counted as an acceptance
set_option Elab.async false in
set_option maxHeartbeats 0 in
set_option maxRecDepth 10000 in
#eval run "cleanable_names.txt" "rewrite.tsv"
