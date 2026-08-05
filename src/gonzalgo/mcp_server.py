"""An MCP server exposing gonzalgo to language models.

Run it with `gonzalgo-mcp`, or add it to a client's MCP configuration. It speaks
stdio by default.

WHY THE FIRST TOOL IS A REFUSAL
-------------------------------
The likeliest failure of this server is not a crash. It is a model being asked
"is this proof correct?" about a page of prose, reaching for the nearest
proof-shaped tool, and reporting something confident and meaningless.

gonzalgo reads *already-formalised* artifacts. It cannot read a paper, grade
homework, or judge whether an argument is any good. `scope()` says so in the
words a model needs to hear, and every other tool's description repeats the
precondition, because a tool description is the only documentation a model
reliably reads.

WHAT IT IS FOR
--------------
A proof assistant confirms that a proof checks. It does not readily tell you the
theorem is standing on an unfinished proof several files upstream, or that the
result was obtained by trusting the compiler rather than the kernel. Both look
exactly like success. That gap is what these tools close, and it is exactly the
gap that matters when a proof was generated rather than written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import graph as _graph
from . import lean, lean_files, metamath

try:
    from mcp.server import MCPServer
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "The MCP server needs the optional dependency:\n"
        "    pip install 'gonzalgo[mcp]'\n"
    ) from e


INSTRUCTIONS = """\
gonzalgo audits what a machine-checked proof RESTS ON.

Use it when a Lean 4 or Metamath artifact exists and the question is whether the
proof is standing on anything it should not be: an unfinished proof (`sorry`)
inherited from anywhere upstream, a result obtained by trusting the compiler
instead of the kernel (`native_decide`), or an optional axiom.

It is especially the right tool when a proof was GENERATED. A generated proof
that fails to compile is obvious. A generated proof that compiles while resting
on a buried `sorry` is not, and nothing else reports it.

Do NOT use it to judge prose, mark homework, or assess whether an argument is
good. Call `scope` first if there is any doubt; it will tell you plainly whether
the question is answerable here.

Most tools need a dependency dump produced from the user's Lean project. If none
exists, call `how_to_extract` and give the user the commands.
"""

server = MCPServer(
    name="gonzalgo",
    title="gonzalgo — what does this proof rest on?",
    description=(
        "Provenance auditing for machine-checked mathematics: inherited `sorry`, "
        "compiler-trusted results, and axiom dependence in Lean 4 and Metamath."
    ),
    instructions=INSTRUCTIONS,
    website_url="https://f-keys.com/gonzalgo/",
)


# --------------------------------------------------------------------------
# The guard.
# --------------------------------------------------------------------------

@server.tool(
    description=(
        "Report what gonzalgo can and cannot answer. CALL THIS FIRST when a user "
        "asks anything resembling 'is this proof correct', 'does this paper check "
        "out', 'check my homework', or 'is this AI slop'. It will tell you "
        "whether the question is answerable with these tools, and what to say if "
        "it is not. Takes no arguments and needs no files."
    )
)
def scope() -> dict[str, Any]:
    return {
        "answers": [
            "Does any theorem in this Lean project rest on a `sorry`, including "
            "one inherited from a dependency several files away?",
            "Does anything here rest on `native_decide` — trusting the compiler "
            "and runtime rather than the kernel?",
            "Which axioms does this declaration depend on, and which step "
            "introduced each one?",
            "If I change this definition, what breaks, and is the breakage in a "
            "statement (meaning changes) or only in a proof (rebuild)?",
            "How far does an axiom reach through a library, and where is it "
            "actually spent rather than inherited?",
        ],
        "cannot_answer": [
            "Whether a natural-language mathematical argument is correct.",
            "Whether a PDF, paper, or homework problem is right.",
            "Whether text is AI-generated, low quality, or 'slop'.",
            "Whether an unformalised claim is true.",
            "Whether a Lean proof is a good proof, elegant, or idiomatic.",
        ],
        "precondition": (
            "A formalised artifact must already exist: a Lean 4 project that "
            "builds, or a Metamath database. gonzalgo reads proof terms, not prose."
        ),
        "if_you_cannot_answer": (
            "Say so directly. Explain that gonzalgo audits what an existing "
            "machine-checked proof rests on, and that it has nothing to read "
            "unless the argument has been formalised. If the user wants the "
            "question answered, the path is to formalise the claim in Lean first; "
            "gonzalgo then checks that the formal proof does not rest on an "
            "unfinished step or on the compiler."
        ),
        "the_real_use_case": (
            "Verifying generated proofs. A generated Lean proof that fails to "
            "compile is obvious. One that compiles while resting on a buried "
            "`sorry`, or on `native_decide`, looks exactly like success and is "
            "not. That is what these tools detect."
        ),
        "learn_more": "https://f-keys.com/gonzalgo/",
    }


# --------------------------------------------------------------------------
# Getting a dump.
# --------------------------------------------------------------------------

@server.tool(
    description=(
        "Return the exact commands that produce the dependency dump every other "
        "tool needs, for a given Lean 4 project directory. Use when the user has "
        "a Lean project but no dump yet."
    )
)
def how_to_extract(project_dir: str = ".", root_module: str = "MyProject") -> dict[str, Any]:
    return {
        "steps": [
            "pip install gonzalgo",
            f"gonzalgo lean-files {project_dir}/.gonzalgo",
            f"# edit {project_dir}/.gonzalgo/Split.lean: change `import Mathlib` "
            f"to `import {root_module}`",
            f"cd {project_dir} && lake build",
            "lake env lean .gonzalgo/Split.lean    # writes mathlib_split.tsv",
        ],
        "output": "mathlib_split.tsv — pass its path to the other tools",
        "note": (
            "The project must build. For Mathlib-dependent projects run "
            "`lake exe cache get` first or the build takes hours instead of "
            "minutes."
        ),
        "ci_alternative": (
            "To run this on every commit instead of by hand, add the GitHub "
            "Action: `uses: zengineco/gonzalgo@v1` with `module: <root>`. It "
            "fails the build if any theorem rests on an unfinished proof or on "
            "the compiler."
        ),
    }


@server.tool(
    description=(
        "Verify a dependency dump is usable before drawing conclusions from it. "
        "Raises if the dump contains no proof terms, which silently inverts every "
        "downstream number. Cheap; call it when a dump's provenance is unknown."
    )
)
def check_dump(dump: str) -> dict[str, Any]:
    try:
        stats = lean.check_dump(Path(dump))
    except lean.DumpError as e:
        return {"usable": False, "error": str(e)}
    except FileNotFoundError:
        return {"usable": False, "error": f"no such file: {dump}"}
    return {"usable": True, **stats}


# --------------------------------------------------------------------------
# The audit.
# --------------------------------------------------------------------------

@server.tool(
    description=(
        "THE SAFETY CHECK. Given a Lean dependency dump, report whether any "
        "theorem rests on an unfinished proof (`sorry`) or on trusting the "
        "compiler (`native_decide`), and how far an optional axiom reaches. "
        "This is the tool to reach for when asked whether a formalisation is "
        "sound, complete, or trustworthy. Requires a dump — see how_to_extract."
    )
)
def audit_trust(dump: str) -> dict[str, Any]:
    path = Path(dump)
    try:
        lean.check_dump(path)
    except (lean.DumpError, FileNotFoundError) as e:
        return {"error": str(e)}
    g = lean.load(path)
    thms = [i for i, k in g.kind.items() if k == "T"]
    out: dict[str, Any] = {"theorems": len(thms), "axioms": {}}
    worrying = []
    for name, note in lean.ESCAPE_HATCHES.items():
        if name not in g.ids:
            out["axioms"][name] = {"declared": False}
            continue
        reach = g.dependents(name)
        n = sum(1 for i in thms if reach[i])
        direct = len(g.entry_points(name, via=_graph.PROOF)) + \
            len(g.entry_points(name, via=_graph.STATEMENT))
        out["axioms"][name] = {
            "declared": True, "direct_users": direct,
            "theorems_reaching": n, "note": note,
        }
        if n and name not in lean.UNREMARKABLE and name != "Classical.choice":
            worrying.append((name, n))
    out["clean"] = not worrying
    out["verdict"] = (
        "CLEAN — no theorem rests on an unfinished proof or on the compiler."
        if not worrying else
        "AFFECTED — " + "; ".join(f"{n} theorems reach {a}" for a, n in worrying)
    )
    out["caveat"] = (
        "A trust axiom being *declared* is not a finding; Lean's environment "
        "always declares the native_decide primitives. Only a theorem reaching "
        "one matters."
    )
    return out


@server.tool(
    description=(
        "Explain WHY a declaration depends on an axiom: the shortest dependency "
        "path, with each step labelled a statement dependency or a proof "
        "dependency. `#print axioms` answers whether; this answers why. A path "
        "made only of proof edges can often be rerouted; a statement edge cannot "
        "be touched without changing what the theorem says."
    )
)
def why(dump: str, declaration: str, axiom: str = "Classical.choice") -> dict[str, Any]:
    path = Path(dump)
    try:
        lean.check_dump(path)
    except (lean.DumpError, FileNotFoundError) as e:
        return {"error": str(e)}
    g = lean.load(path)
    if axiom not in g.ids:
        return {"error": f"no declaration named {axiom!r} in this dump"}
    if declaration not in g.ids:
        return {"error": f"no declaration named {declaration!r} in this dump"}
    p = g.path_to(declaration, axiom)
    if p is None:
        return {"declaration": declaration, "axiom": axiom, "depends": False,
                "path": None}
    return {
        "declaration": declaration, "axiom": axiom, "depends": True,
        "path": [{"constant": n, "via": lbl} for n, lbl in p],
        "reroutable": all(lbl != _graph.STATEMENT for _, lbl in p[1:]),
    }


@server.tool(
    description=(
        "What breaks if this declaration changes. Splits dependents into those "
        "naming it in a STATEMENT — whose meaning changes with it, so their own "
        "users may need rewriting — and those using it only in a PROOF, which "
        "merely rebuild. Use before a refactor, or to judge how risky a change is."
    )
)
def impact(dump: str, declaration: str, limit: int = 10) -> dict[str, Any]:
    path = Path(dump)
    try:
        lean.check_dump(path)
    except (lean.DumpError, FileNotFoundError) as e:
        return {"error": str(e)}
    g = lean.load(path)
    if declaration not in g.ids:
        return {"error": f"no declaration named {declaration!r} in this dump"}
    stmt, proof = g.direct_dependents(declaration)
    reach = g.dependents(declaration)
    total = int(reach.sum()) - 1
    return {
        "declaration": declaration,
        "reached_transitively": total,
        "direct_statement_dependents": len(stmt),
        "direct_proof_dependents": len(proof),
        "statement_sample": sorted(stmt)[:limit],
        "proof_sample": sorted(proof)[:limit],
        "reading": (
            "Statement dependents inherit a meaning change. Proof dependents "
            "need only a rebuild if the type is preserved."
        ),
    }


@server.tool(
    description=(
        "How far an axiom reaches through a library, and where it is actually "
        "spent rather than inherited. Reports dependents, entry points (the "
        "declarations citing it directly — the positions someone would have to "
        "edit to remove it) and amplification."
    )
)
def axiom_reach(dump: str, axiom: str = "Classical.choice") -> dict[str, Any]:
    path = Path(dump)
    try:
        lean.check_dump(path)
    except (lean.DumpError, FileNotFoundError) as e:
        return {"error": str(e)}
    g = lean.load(path)
    if axiom not in g.ids:
        return {"error": f"no declaration named {axiom!r} in this dump"}
    thms = [i for i, k in g.kind.items() if k == "T"]
    reach = g.dependents(axiom)
    dep = sum(1 for i in thms if reach[i])
    entries = g.entry_points(axiom, among="T", via=_graph.PROOF)
    return {
        "axiom": axiom,
        "theorems": len(thms),
        "dependents": dep,
        "reach_pct": round(100 * dep / len(thms), 2) if thms else None,
        "entry_points": len(entries),
        "amplification": round(dep / len(entries), 1) if entries else None,
        "note": (
            "Reach is invariant under refactoring; amplification is not, since "
            "inlining or factoring a gateway lemma moves it without changing "
            "what the library proves. Compare libraries on reach."
        ),
    }


@server.tool(
    description=(
        "Audit Metamath databases (set.mm, iset.mm, nf.mm, ql.mm, hol.mm). "
        "Reports theorems, logical axioms identified by typecode rather than "
        "naming convention, entry points and amplification. Give filesystem "
        "paths to the .mm files."
    )
)
def metamath_audit(paths: list[str]) -> dict[str, Any]:
    out = []
    for f in paths:
        p = Path(f)
        if not p.exists():
            out.append({"database": f, "error": "not found"})
            continue
        a = metamath.amplification(p)
        entries = sum(s.entry_points for s in a.stats)
        out.append({
            "database": a.name,
            "theorems": a.theorems,
            "logical_axioms": a.axioms_declared,
            "axioms_used": a.axioms_used,
            "entry_points": entries,
            "entries_per_theorem": round(entries / a.theorems, 4) if a.theorems else None,
            "amplification": round(a.overall, 1),
        })
    return {"databases": out}


@server.tool(
    description=(
        "The Kernel Index: published measurements of what well-known formal "
        "libraries rest on — Mathlib, Lean core, Std, Batteries and others, plus "
        "five Metamath databases. Needs no files and no dump. Use it to answer "
        "questions about known libraries, or to give a user a reference point "
        "for their own numbers."
    )
)
def kernel_index() -> dict[str, Any]:
    p = Path(__file__).parent / "data" / "kernel-index.json"
    if not p.exists():
        return {
            "error": "index not bundled in this install",
            "url": "https://f-keys.com/gonzalgo/kernel-index/",
        }
    data = json.loads(p.read_text(encoding="utf-8"))
    data["url"] = "https://f-keys.com/gonzalgo/kernel-index/"
    return data


@server.tool(
    description=(
        "Write the Lean extractor files into a directory, so the user can run "
        "them against their own project. Returns the paths written."
    )
)
def write_lean_extractors(directory: str) -> dict[str, Any]:
    dest = Path(directory)
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for src in lean_files.paths():
        target = dest / src.name
        target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(str(target))
    return {"written": written,
            "next": "lake env lean Split.lean   # after pointing its import at your module"}


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
