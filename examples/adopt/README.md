# Adopt

Two things a Lean 4 project can add, both independent of each other.

## 1. Gate the build on what it rests on

Copy `kernel-clean.yml` to `.github/workflows/` and add the badge to your README.
The workflow fails when a theorem reaches an unfinished proof or a
compiler-trusted result, so the badge is an assertion rather than decoration.

Keep the filename. GitHub derives the badge text from it, and `kernel-clean` is
what you want it to say.

## 2. Declare what the project rests on

A [Kernel Trust Profile](https://f-keys.com/gonzalgo/kernel-trust/) is a fixed
shape for that statement, conventionally `kernel-trust.json` at the repository
root — the way `CITATION.cff` fixes how to cite you and SPDX fixes your licence.

Two implementations exist and neither is required by the other:

```bash
# from a declaration graph
gonzalgo profile mathlib_split.tsv -o kernel-trust.json

# or from Lean's own output, with nothing of ours installed
lake env lean YourAxiomsFile.lean > axioms.txt
python tools/ktp_emit.py axioms.txt --name YourProject \
  --system-version 4.33.0 --revision "$(git rev-parse HEAD)" > kernel-trust.json
```

A profile carries no score. A theorem either reaches an unfinished proof or it
does not, and averaging that against anything invents precision the measurement
does not have — so there is nothing in the format to rank projects by.

Specification: https://doi.org/10.5281/zenodo.21913736
