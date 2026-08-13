# Measurements

One file per measured release of Mathlib, written by `.github/workflows/kernel-index.yml`
on a monthly schedule. Each is the reduction of a ~650 MB declaration dump to the
part worth keeping: counts by kind, the module count, and the **full axiom roster**.

The roster is stored in full rather than as a count. A release that swaps one
axiom for another leaves the count unchanged, and that is precisely the event
these files exist to catch.

`delta-<from>-to-<to>.json` carries the comparison between two releases, including
the two figures a text diff cannot produce: declarations whose **statement**
dependencies changed (a different claim under an old name) and those whose
**proof** dependencies changed while the statement held (the same claim,
reproved).

The dumps themselves are not in this repository. Each run uploads its dump as a
build artifact and caches it so the next run can diff against it.

## Measured so far

| release | declarations | theorems | axioms |
|---|---:|---:|---:|
| v4.32.1 | 790,171 | 532,605 | 15 |
| v4.33.0 | 795,218 | 535,601 | 15 |

Across v4.32.1 → v4.33.0 the axiom roster did not change — the same fifteen
names on both sides. 24,172 theorems kept their statement and changed their
proof, against 2,996 net new theorems.
