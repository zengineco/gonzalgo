/-
  `lake exe gonzalgo <Module> <out.tsv>`

  Dumps the declaration graph of a module and everything it imports, without
  needing a scratch file with an `#eval` in it. The module is imported at
  runtime, so this works against any project Lake can already build:

      lake exe gonzalgo MyProject myproject.tsv
      lake exe gonzalgo Mathlib   mathlib.tsv

  Copyright (c) 2026 Vince Gonzalez. Apache-2.0.
-/
import Lean
import Gonzalgo.Extract

open Lean Gonzalgo

-- Built by joining lines rather than with `\` continuations, which strip the
-- leading whitespace and quietly flatten the indentation.
def usage : String := String.intercalate "\n" [
  "gonzalgo — write out a Lean declaration graph",
  "",
  "usage:  lake exe gonzalgo <Module> <out.tsv>",
  "",
  "  <Module>   a module to import, e.g. MyProject or Mathlib. Everything it",
  "             imports is included; the fifth output column records which",
  "             module each declaration came from, which is what separates a",
  "             project from its dependencies afterwards.",
  "  <out.tsv>  where to write. Expect roughly 500 bytes per declaration.",
  "",
  "then:   gonzalgo check <out.tsv>     (pip install gonzalgo)",
  "        gonzalgo trust <out.tsv>",
  "",
  "https://f-keys.com/gonzalgo/"]

def main (args : List String) : IO UInt32 := do
  match args with
  | [modName, out] =>
      -- Lake puts the project's build directory on LEAN_PATH before running
      -- this, so the sysroot is all initSearchPath needs to resolve the rest.
      initSearchPath (← findSysroot)
      let mod := modName.toName
      if mod.isAnonymous then
        IO.eprintln s!"gonzalgo: {modName} is not a module name"
        return 1
      IO.println s!"importing {mod} ..."
      let env ← try
        importModules #[{ module := mod }] {}
      catch e =>
        IO.eprintln s!"gonzalgo: could not import {mod}: {e.toString}"
        IO.eprintln "  the module must be built first — try `lake build`"
        return 1
      let ctx : Core.Context := { fileName := "<gonzalgo>", fileMap := default }
      let st : Core.State := { env }
      discard <| (dumpSplit out).toIO ctx st
      return 0
  | _ =>
      IO.println usage
      return (if args.isEmpty then 0 else 1)
