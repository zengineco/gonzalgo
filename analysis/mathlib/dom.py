import sys
import os
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, os.environ.get("SETMM_CHOICE_TOOLS") or "tools")
import necessity as N
import impact as I

DB = Path(os.environ.get("SETMM") or "vendor/set.mm")
kind, refs = N.parse(DB)
axioms = {"ax-ac", "ax-ac2"}
res = N.analyse(kind, refs, list(axioms))
reach = res["reach"]
ROOT = I.ROOT
succ = defaultdict(set)
nodes = reach | axioms
for t in reach:
    for r in refs.get(t, ()):
        if r in nodes:
            succ[r].add(t)
for ax in axioms:
    succ[ROOT].add(ax)
seen, order, stack = set(), [], [(ROOT, iter(sorted(succ[ROOT])))]
seen.add(ROOT)
while stack:
    node, it = stack[-1]
    adv = next(it, None)
    if adv is None:
        order.append(node); stack.pop()
    elif adv not in seen:
        seen.add(adv); stack.append((adv, iter(sorted(succ.get(adv, ())))))
order.reverse()
idom = I.dominators(succ, ROOT, order)
kids = defaultdict(list)
for n, d in idom.items():
    if n != d:
        kids[d].append(n)

def sub(n, out):
    out.append(n)
    for c in kids[n]:
        sub(c, out)

target = sys.argv[1] if len(sys.argv) > 1 else "imadomg"
out = []
sub(target, out)
print(f"{target}: dominator subtree size {len(out)}")
for n in out:
    print("   ", n, "  idom=", idom.get(n))
print()
# direct users of target that reach choice
users = sorted(t for t in reach if target in refs.get(t, ()))
print(f"direct users of {target} that reach choice ({len(users)}):")
for u in users:
    print("   ", u)
allusers = sorted(t for t in refs if target in refs.get(t, ()))
print(f"\nALL direct users of {target} ({len(allusers)}):")
for u in allusers:
    print("   ", u, "" if u in reach else "  [choice-free already?!]")
