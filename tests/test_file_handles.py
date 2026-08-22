"""Readers must close the file they open.

`rows` is a generator, so the file it opens lives as long as the generator
frame. A caller that stops early -- `next(rows(p))`, `any(...)`, a `break` --
leaves the dump open. On Windows an open handle blocks the next write to that
path, so the failure lands on an unrelated later line rather than at the read.

These tests hold a reference to every handle `_open` returns. That keeps the
handle alive, so it can only be closed by something actually calling `close()`,
and not by CPython dropping the last reference. Without that reference the test
passes on the broken code, which is how the first version of this file was
wrong: a ResourceWarning is raised during collection, outside any
`catch_warnings` block, and never fails the assertion it was supposed to.
"""

from __future__ import annotations

import gc
import gzip

import pytest

from gonzalgo import lean

ROWS = [
    ("A", "Classical.choice", "", ""),
    ("D", "Classical.propDecidable", "", "Classical.choice"),
    ("T", "thm", "Nat", "Classical.propDecidable"),
    ("T", "other", "Nat", "Classical.choice"),
]


def write(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text("".join("\t".join(r) + "\n" for r in rows), encoding="utf-8")
    return p


@pytest.fixture
def handles(monkeypatch):
    """Every handle `_open` returns, held open so only close() can shut it."""
    opened = []
    real = lean._open

    def spy(path):
        handle = real(path)
        opened.append(handle)
        return handle

    monkeypatch.setattr(lean, "_open", spy)
    return opened


def test_a_fully_read_dump_is_closed(tmp_path, handles):
    dump = write(tmp_path, "d.tsv", ROWS)
    assert len(list(lean.rows(dump))) == 4
    assert handles and all(h.closed for h in handles)


def test_an_abandoned_reader_is_closed(tmp_path, handles):
    """The case that actually leaks: the caller never reaches the end."""
    dump = write(tmp_path, "d.tsv", ROWS)
    reader = lean.rows(dump)
    assert next(reader)[1] == "Classical.choice"
    del reader
    gc.collect()
    assert handles and all(h.closed for h in handles)


def test_load_closes_the_dump(tmp_path, handles):
    dump = write(tmp_path, "d.tsv", ROWS)
    lean.load(dump)
    assert handles and all(h.closed for h in handles)


def test_audit_closes_the_sites_file(tmp_path, handles):
    dump = write(tmp_path, "d.tsv", ROWS)
    sites = tmp_path / "sites.tsv"
    sites.write_text(
        "REMOVABLE\tM\tthm\tsite\tinstDecidableEqNat a b\n", encoding="utf-8"
    )
    lean.audit(sites, dump, lean.load(dump))
    assert handles and all(h.closed for h in handles)


def test_a_gzipped_dump_is_closed(tmp_path, handles):
    """`_open` returns a gzip handle for .gz and a text handle otherwise."""
    path = tmp_path / "d.gz"
    with gzip.open(path, "wt", encoding="utf-8") as out:
        out.write("".join("\t".join(r) + "\n" for r in ROWS))

    reader = lean.rows(path)
    next(reader)
    del reader
    gc.collect()
    assert handles and all(h.closed for h in handles)


def test_the_dump_can_be_rewritten_straight_after_reading(tmp_path):
    """An open handle blocks this on Windows. No spy: this is the real symptom."""
    dump = write(tmp_path, "d.tsv", ROWS)
    lean.load(dump)
    dump.write_text("A\tClassical.choice\t\t\n", encoding="utf-8")
    assert len(list(lean.rows(dump))) == 1
