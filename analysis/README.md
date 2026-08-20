# analysis — the measurement code behind the papers

The scripts that produced the figures in the dominator, specialisation-loss and
eligibility papers. They run against a Mathlib dependency dump and against
`set.mm`, and they are kept here rather than in `tools/` because they are
research code answering one question each, not part of the packaged CLI.

## mathlib/

| script | what it does |
|---|---|
| `chokepoint.py` | reverse reachability over the whole graph: which declarations reach a target, in one sweep rather than 790,000 searches. Names are interned to integers — 30 M edges as a flat array is about 120 MB, as Python strings it does not fit |
| `dominators.py` | the dominator tree, Cooper–Harvey–Kennedy. Ranks all 766,564 constants at once. Its header records the six severing counts it was validated against |
| `counterfactual.py` | the independent severing check: delete a constant, recompute reachability, count what actually leaves. This is what distinguishes responsibility from reach |
| `sites2.py` | collapses dominator chains into sites on a weight ratio, and charges each theorem once to its immediate dominator so the partition sums |
| `site_eligibility.py` | applies the statement/proof test to sites rather than theorems. Re-reads the dump keeping statement and proof edges apart, which the dominator run merges |
| `controlled.py` | the controlled tactic experiment — 270 cells, tactic × goal-shape |
| `build_repro.py` | rebuilds the published figures from a fresh dump |
| `dom.py` | the `set.mm` dominator measurement, using `setmm_choice`'s tools |
| `state_of_gonzalgo.py` | corpus state snapshot |

## Running them

No path is compiled in. Each script takes its input from an environment
variable and otherwise looks in `analysis/data/`:

| variable | used by | default |
|---|---|---|
| `MATHLIB_DUMP` | `chokepoint`, `dominators`, `site_eligibility` | `analysis/data/mathlib_graph.tsv` |
| `MATHLIB_SPLIT_DUMP` | `counterfactual` | `analysis/data/mathlib_split-v4.32.1.tsv` |
| `SETMM` | `dom` | `vendor/set.mm` |
| `SETMM_CHOICE_TOOLS` | `dom` | `tools` |
| `LEAN_WORK`, `PAPERS`, `REPRO_OUT` | `build_repro` | relative |

The dumps are not in the repository. `mathlib_graph.tsv` is about 594 MB and is
regenerated from `Dump.lean` in roughly three minutes; the dominator tree then
takes 42 seconds over the full graph and each severing run about 20 seconds.
Environment for every figure quoted in the papers: **Lean 4.32.1, Mathlib
v4.32.1**.

`dom.py` additionally wants a clone of
[`setmm_choice`](https://github.com/vince-gonzalez/setmm_choice) for its
Metamath tools, and a `set.mm`.

## data/

Committed outputs, so every published figure is checkable without regenerating
a 594 MB dump:

| file | holds |
|---|---|
| `sites2.json` | the source of every site figure in the papers |
| `dominators.json` | the ranked dominator table |
| `site_eligibility.json` | the site-level statement/proof test |
| `sites.json` | the pre-collapse site enumeration |
| `controlled_cells.json`, `controlled_results.json` | the 270-cell experiment |
| `subst_targets.json` | the substitution targets |

## Reproduction status

`counterfactual.py` and `controlled.py` were lost to a temporary-directory
sweep and rebuilt from their surviving outputs. `counterfactual.py` reproduces
five of the six published severing counts exactly, across a Mathlib dump-version
boundary. The sixth, `Classical.propDecidable`, gives 92,076 against a published
91,858 — a 1% difference between dump versions, and the papers state the figure
with that bound rather than as an exact count.

The rebuild validates itself: `counterfactual.py` run with no arguments recounts
all six candidates and **exits non-zero** if any falls outside its stated
tolerance — zero drift allowed on the five small order lemmas, 1% on
`propDecidable`. A validation that cannot fail validates nothing, so the
tolerance is written as a bound rather than left open.

It shares no code with `dominators.py`. The tree is built once from the graph's
structure; the counterfactual recomputes reachability from scratch with a
candidate's edges removed. Agreement between two implementations that have
nothing in common is the reason both exist.
