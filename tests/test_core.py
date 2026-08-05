"""Tests over small hand-built fixtures.

The fixtures are tiny on purpose. Every property tested here is one that a
real dump would also have to satisfy, and each corresponds to a mistake that
actually occurred while the tool was being written: proof terms silently absent,
statement and proof edges conflated, a witness that is a local hypothesis rather
than a library instance.
"""

from __future__ import annotations

import pytest

from gonzalgo import lean, lean_files, metamath
from gonzalgo.graph import PROOF, STATEMENT, Graph


def write(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text("".join("\t".join(r) + "\n" for r in rows), encoding="utf-8")
    return p


# ---- the allowOpaque hazard ---------------------------------------------

def test_dump_without_proof_terms_is_rejected(tmp_path):
    """A dump whose theorems carry no proofs must fail loudly, not quietly.

    This is the `value? (allowOpaque := true)` mistake. It does not degrade the
    numbers, it inverts them: every theorem looks constructive because its proof
    is invisible.
    """
    p = write(tmp_path, "bad.tsv", [
        ("A", "Classical.choice", "", ""),
        ("T", "thm1", "Nat", ""),
        ("T", "thm2", "Nat", ""),
    ])
    with pytest.raises(lean.DumpError, match="allowOpaque"):
        lean.check_dump(p)


def test_dump_with_proof_terms_passes(tmp_path):
    p = write(tmp_path, "ok.tsv", [
        ("A", "Classical.choice", "", ""),
        ("T", "thm1", "Nat", "Classical.choice"),
    ])
    stats = lean.check_dump(p)
    assert stats["theorems"] == 1
    assert stats["theorems_with_proof"] == 1


def test_a_dump_with_no_theorems_at_all_is_not_an_error(tmp_path):
    p = write(tmp_path, "defs.tsv", [("D", "f", "Nat", "Nat.succ")])
    assert lean.check_dump(p)["theorems"] == 0


# ---- reachability and edge labelling ------------------------------------

def test_dependents_is_transitive():
    g = Graph()
    g.add("ax", kind="A")
    g.add("mid", kind="T", proof=["ax"])
    g.add("top", kind="T", proof=["mid"])
    g.add("unrelated", kind="T", proof=["Nat"])
    dep = g.dependents("ax")
    assert dep[g.ids["top"]] and dep[g.ids["mid"]]
    assert not dep[g.ids["unrelated"]]


def test_entry_points_are_direct_citers_only():
    g = Graph()
    g.add("ax", kind="A")
    g.add("gateway", kind="T", proof=["ax"])
    g.add("user", kind="T", proof=["gateway"])
    assert g.entry_points("ax", among="T") == ["gateway"]


def test_path_labels_statement_and_proof_edges_differently():
    """The label is the whole point: a proof edge can be rerouted by changing a
    tactic, a statement edge cannot be touched without changing the theorem."""
    g = Graph()
    g.add("ax", kind="A")
    g.add("viaProof", kind="T", proof=["ax"])
    g.add("viaStatement", kind="T", statement=["ax"])
    assert g.path_to("viaProof", "ax")[-1][1] == PROOF
    assert g.path_to("viaStatement", "ax")[-1][1] == STATEMENT


def test_path_is_none_when_independent():
    g = Graph()
    g.add("ax", kind="A")
    g.add("free", kind="T", proof=["Nat.succ"])
    assert g.path_to("free", "ax") is None
    assert g.path_to("nonexistent", "ax") is None


# ---- statement versus proof ---------------------------------------------

def test_eligibility_separates_statement_from_proof(tmp_path):
    p = write(tmp_path, "d.tsv", [
        ("A", "Classical.choice", "", ""),
        ("D", "Real", "", "Classical.choice"),       # choice-dependent constant
        ("T", "eligible", "Nat", "Classical.choice"),  # clean stmt, dirty proof
        ("T", "ineligible", "Real", "Classical.choice"),
        ("T", "clean", "Nat", "Nat.succ"),
    ])
    g = lean.load(p)
    e = lean.eligibility(p, g)
    assert e.theorems == 3
    assert e.proof_only == 1        # only `eligible` can ever be cleaned
    assert e.stmt_and_proof == 1
    assert e.neither == 1
    assert e.ceiling == pytest.approx(1 / 3)


# ---- witness filtering ---------------------------------------------------

@pytest.mark.parametrize("witness,expected", [
    ("instDecidableEqNat a b", True),
    ("Nat.decLe", True),
    ("x", False),                 # a local hypothesis, nothing to substitute
    ("inst✝ a b", False),         # same, with arguments applied
    ("", False),
    ("   ", False),
])
def test_real_witness(witness, expected):
    assert lean.real_witness(witness) is expected


def test_audit_counts_cleanable_below_declarations(tmp_path):
    """Cleanable must be the smallest of the three quantities: a declaration
    with a substitutable site can still reach the axiom another way."""
    dump = write(tmp_path, "d.tsv", [
        ("A", "Classical.choice", "", ""),
        ("D", "Other", "", "Classical.choice"),
        ("T", "onlyRoute", "Nat", "Classical.propDecidable"),
        ("T", "alsoOtherRoute", "Nat", "Classical.propDecidable Other"),
    ])
    sites = tmp_path / "sites.tsv"
    sites.write_text(
        "REMOVABLE\tM\tonlyRoute\tsite\tinstDecidableEqNat a b\n"
        "REMOVABLE\tM\talsoOtherRoute\tsite\tinstDecidableEqNat a b\n",
        encoding="utf-8")
    g = lean.load(dump)
    a = lean.audit(sites, dump, g)
    assert a.declarations == 2
    assert a.cleanable == 1 and a.blocked == 1
    assert a.cleanable_names == ["onlyRoute"]


# ---- Metamath ------------------------------------------------------------

MM = """
$( a toy database $)
$c |- wff ( ) -> ph ps $.
$v ph ps $.
wph $f wff ph $.
wps $f wff ps $.
wi $a wff ( ph -> ps ) $.
ax-1 $a |- ( ph -> ( ps -> ph ) ) $.
ax-mp $a |- ps $.
th1 $p |- ( ph -> ( ps -> ph ) ) $= ( ax-1 ) ABC $.
th2 $p |- ( ph -> ( ps -> ph ) ) $= ( th1 ) ABC $.
"""


def test_logical_axioms_found_by_typecode_not_by_name(tmp_path):
    """`wi` is named like an axiom and is a grammar production; it must not be
    counted. The `ax-` convention differs between databases, so name rules
    miscount two of the three this package targets."""
    p = tmp_path / "toy.mm"
    p.write_text(MM, encoding="utf-8")
    db = metamath.parse(p)
    assert db.logical_axioms == {"ax-1", "ax-mp"}
    assert "wi" not in db.logical_axioms


def test_metamath_closure_is_transitive(tmp_path):
    p = tmp_path / "toy.mm"
    p.write_text(MM, encoding="utf-8")
    db = metamath.parse(p)
    clos = metamath.closures(db)
    assert "ax-1" in clos["th1"]
    assert "ax-1" in clos["th2"]          # inherited through th1


def test_amplification_counts_entries_below_dependents(tmp_path):
    p = tmp_path / "toy.mm"
    p.write_text(MM, encoding="utf-8")
    a = metamath.amplification(p)
    by = {s.name: s for s in a.stats}
    assert by["ax-1"].dependents == 2     # th1 and th2
    assert by["ax-1"].entry_points == 1   # only th1 cites it directly
    assert by["ax-1"].amplification == 2.0


# ---- shipped Lean sources ------------------------------------------------

def test_lean_files_are_shipped_and_nonempty():
    paths = lean_files.paths()
    assert {p.name for p in paths} >= {"Split.lean", "Substitute.lean", "Rewrite.lean"}
    for p in paths:
        assert p.stat().st_size > 0


def test_omegafix_retains_upstream_copyright_and_modification_notice():
    """Apache 2.0 section 4(b): a modified file must say so, prominently."""
    src = lean_files.read("OmegaFix.lean")
    assert "Copyright (c) 2023 Lean FRO, LLC" in src
    assert "MODIFIED FILE" in src


def test_entry_points_default_to_proof_citations():
    """A theorem citing an axiom in its STATEMENT is about the axiom, not
    spending it. Counting the union inflated Mathlib's entry points from 144 to
    158 and deflated amplification by the same proportion."""
    g = Graph()
    g.add("ax", kind="A")
    g.add("spends", kind="T", proof=["ax"])
    g.add("mentions", kind="T", statement=["ax"])
    assert g.entry_points("ax", among="T") == ["spends"]
    assert g.entry_points("ax", among="T", via=STATEMENT) == ["mentions"]


def test_missing_target_is_an_error_not_a_negative_answer(capsys):
    """"This does not depend on that" and "you typed a name that does not
    exist" are opposite answers. Reporting the second as the first is the
    silent-wrong-answer this whole package exists to prevent."""
    import tempfile, pathlib
    from gonzalgo.cli import main
    d = pathlib.Path(tempfile.mkdtemp())
    p = d / "d.tsv"
    p.write_text("A\tClassical.choice\t\t\nT\tthm\tNat\tNat.succ\n", encoding="utf-8")
    rc = main(["why", str(p), "thm", "-a", "No.Such.Constant"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "no declaration named" in out
    assert "no path" not in out


def test_direct_dependents_splits_api_surface_from_recompile():
    """Statement dependents inherit a meaning change; proof dependents only
    need rebuilding. Collapsing the two is what makes ordinary "who uses this"
    useless for deciding whether a change is safe."""
    g = Graph()
    g.add("target", kind="D")
    g.add("usesInType", kind="T", statement=["target"])
    g.add("usesInProof", kind="T", proof=["target"])
    g.add("indirect", kind="T", proof=["usesInProof"])
    stmt, proof = g.direct_dependents("target")
    assert stmt == ["usesInType"]
    assert proof == ["usesInProof"]
    assert "indirect" not in stmt + proof          # direct only
    assert g.dependents("target")[g.ids["indirect"]]  # but reached transitively


def test_direct_dependents_of_unknown_name_is_empty_not_an_error():
    g = Graph()
    g.add("x", kind="D")
    assert g.direct_dependents("nope") == ([], [])


def test_trust_reports_unfinished_proofs_and_their_reach(tmp_path, capsys):
    """The point of tracking sorryAx on a graph: Lean warns about the `sorry`
    you just typed, not about the theorem far downstream that inherits it."""
    from gonzalgo.cli import main
    p = tmp_path / "d.tsv"
    p.write_text(
        "A\tsorryAx\t\t\n"
        "A\tClassical.choice\t\t\n"
        "T\tunfinished\tNat\tsorryAx\n"
        "T\tinnocent\tNat\tunfinished\n"      # inherits it without saying so
        "T\tclean\tNat\tNat.succ\n",
        encoding="utf-8")
    assert main(["trust", str(p)]) == 0
    out = capsys.readouterr().out
    assert "UNFINISHED" in out
    # both the direct user and the downstream inheritor must be counted
    assert "2" in [w for line in out.splitlines() if "sorryAx" in line
                   for w in line.split()]


def test_trust_says_so_when_nothing_is_wrong(tmp_path, capsys):
    from gonzalgo.cli import main
    p = tmp_path / "d.tsv"
    p.write_text("A\tpropext\t\t\nT\tt\tNat\tpropext\n", encoding="utf-8")
    main(["trust", str(p)])
    out = capsys.readouterr().out
    assert "CLEAN" in out


def test_fail_on_trust_gates_a_build(tmp_path, capsys):
    """The certifier's point: a clean library should be able to PROVE it is
    clean on every commit rather than assuming it."""
    from gonzalgo.cli import main
    dirty = tmp_path / "dirty.tsv"
    dirty.write_text(
        "A\tsorryAx\t\t\n"
        "T\tbad\tNat\tsorryAx\n", encoding="utf-8")
    assert main(["trust", str(dirty), "--fail-on-trust"]) == 1

    clean = tmp_path / "clean.tsv"
    clean.write_text(
        "A\tpropext\t\t\nT\tgood\tNat\tpropext\n", encoding="utf-8")
    assert main(["trust", str(clean), "--fail-on-trust"]) == 0


def test_declared_but_unreached_trust_axiom_is_not_a_finding(tmp_path, capsys):
    """Lean's environment always declares the native_decide primitives. What
    matters is whether a THEOREM reaches one, not whether it exists."""
    from gonzalgo.cli import main
    p = tmp_path / "d.tsv"
    p.write_text(
        "A\tLean.trustCompiler\t\t\n"
        "O\tLean.reduceBool\t\tLean.trustCompiler\n"   # primitive, no theorem uses it
        "T\tthm\tNat\tNat.succ\n", encoding="utf-8")
    assert main(["trust", str(p), "--fail-on-trust"]) == 0
    assert "CLEAN" in capsys.readouterr().out


# ---- MCP server ----------------------------------------------------------

def test_mcp_scope_refuses_the_questions_it_cannot_answer():
    """The likeliest failure of the MCP server is a model reaching for a
    proof-shaped tool when asked about prose. `scope` exists to stop that, so
    its refusals are load-bearing and pinned here."""
    pytest.importorskip("mcp")
    from gonzalgo import mcp_server
    s = mcp_server.scope()
    joined = " ".join(s["cannot_answer"]).lower()
    for forbidden in ("homework", "slop", "natural-language", "paper"):
        assert forbidden in joined
    assert "formalise" in s["if_you_cannot_answer"].lower()


def test_mcp_exposes_the_expected_tools():
    pytest.importorskip("mcp")
    import asyncio
    from gonzalgo import mcp_server
    names = {t.name for t in asyncio.run(mcp_server.server.list_tools())}
    assert {"scope", "audit_trust", "why", "impact", "kernel_index"} <= names


def test_mcp_kernel_index_is_bundled():
    """The index answers questions with no dump and no network, which is the
    only tool a model can usefully call cold."""
    pytest.importorskip("mcp")
    from gonzalgo import mcp_server
    idx = mcp_server.kernel_index()
    assert idx.get("rows"), "kernel-index.json is not bundled in the package"
    assert len(idx["rows"]) >= 14
    libs = {r["library"] for r in idx["rows"]}
    assert "Mathlib" in libs and "set.mm" in libs


def test_registry_marker_and_server_json_agree_with_the_package():
    """The MCP Registry reads the ownership marker off the PyPI description,
    which is this README. 0.5.1 shipped without it and PyPI versions cannot be
    re-uploaded, so the miss cost a release. Three things must agree: the
    marker, the name in server.json, and the version being built."""
    import json
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    readme = (root / "README.md").read_text(encoding="utf-8")
    server = json.loads((root / "server.json").read_text(encoding="utf-8"))

    # The banner spelled GONZALG for six releases. A missing glyph in
    # box-drawing characters is invisible to the eye but not to a width check:
    # GONZALGO is 70 columns of art plus 3 padding either side. Drop a letter
    # and this lands at 68 or 70.
    box = [l for l in readme.splitlines() if l.startswith("║")]
    assert box, "banner is gone"
    assert len({len(l) for l in box}) == 1, "banner rows are ragged"
    assert len(box[0]) == 78, f"banner width {len(box[0])} - is a letter missing?"

    m = re.search(r"mcp-name:\s*(\S+?)\s*(?:-->|$)", readme, re.M)
    assert m, "README lost the mcp-name marker; registry publish will fail validation"
    assert m.group(1) == server["name"], "marker and server.json name disagree"

    from gonzalgo import __version__
    assert server["version"] == __version__
    assert server["packages"][0]["version"] == __version__


def test_mcp_is_reachable_as_a_subcommand():
    """The MCP Registry entry launches `uvx --from gonzalgo[mcp] gonzalgo mcp`.
    If the subcommand stops existing, that published entry silently starts the
    analysis CLI instead of a server, and every client using it breaks."""
    import argparse
    from gonzalgo import cli
    parser = cli.build_parser() if hasattr(cli, "build_parser") else None
    if parser is None:
        # The parser is built inside main(); assert via the dispatch table.
        assert hasattr(cli, "cmd_mcp"), "cmd_mcp is gone; server.json points at nothing"
        return
    with pytest.raises(SystemExit):
        parser.parse_args(["mcp", "--nonexistent-flag"])


def test_mcp_server_reports_its_version_to_the_host():
    """Driving the server through a real stdio client showed it handshaking as
    version='' — a host prints that next to the name. It has to be the package
    version, and it has to stay non-empty."""
    pytest.importorskip("mcp")
    from gonzalgo import __version__, mcp_server
    reported = getattr(mcp_server.server, "version", None)
    assert reported, "MCP server hands the host an empty version string"
    assert reported == __version__


def test_mcp_tools_report_a_missing_dump_rather_than_raising(tmp_path):
    pytest.importorskip("mcp")
    from gonzalgo import mcp_server
    missing = str(tmp_path / "nope.tsv")
    for fn in (mcp_server.audit_trust, mcp_server.check_dump):
        r = fn(missing)
        assert "error" in r or r.get("usable") is False


# ---- cold start ----------------------------------------------------------

def test_index_command_works_with_no_files(capsys):
    """Someone evaluating this should get real output one line after
    installing, without owning a Lean project. Every other command needs a
    dump; this one needs nothing."""
    from gonzalgo.cli import main
    assert main(["index"]) == 0
    out = capsys.readouterr().out
    assert "KERNEL INDEX" in out
    assert "Mathlib" in out and "set.mm" in out
    assert "14 libraries" in out
    assert "0 resting on an unfinished proof" in out
