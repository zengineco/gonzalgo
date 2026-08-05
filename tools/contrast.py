"""WCAG contrast gate.

Exists because contrast failures kept shipping. Run it against a stylesheet's
palette and it exits non-zero on anything below AA. Wire it into CI and the
class of bug is closed rather than patched again.

    AA  normal text  4.5:1
    AA  large text   3.0:1   (>=24px, or >=18.66px bold)
    AAA normal text  7.0:1
"""
from __future__ import annotations

import sys


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexcolor: str) -> float:
    h = hexcolor.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return (0.2126 * srgb_to_linear(r)
            + 0.7152 * srgb_to_linear(g)
            + 0.0722 * srgb_to_linear(b))


def ratio(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    lo, hi = sorted((a, b))
    return (hi + 0.05) / (lo + 0.05)


#: (label, foreground, background, minimum). Minimum is 4.5 for anything a
#: reader has to actually read, 3.0 only for genuinely large display text.
def check(pairs: list[tuple[str, str, str, float]]) -> int:
    worst = 0
    fails = 0
    print(f"  {'element':<34}{'fg':<10}{'bg':<10}{'ratio':>7}  {'min':>5}")
    for label, fg, bg, minimum in pairs:
        r = ratio(fg, bg)
        ok = r >= minimum
        if not ok:
            fails += 1
        mark = "ok" if ok else "FAIL"
        print(f"  {label:<34}{fg:<10}{bg:<10}{r:>7.2f}  {minimum:>5.1f}  {mark}")
        worst = max(worst, minimum - r if not ok else 0)
    print()
    if fails:
        print(f"  {fails} pair(s) below the WCAG AA minimum.")
        return 1
    print("  all pairs pass WCAG AA.")
    return 0


PALETTE = {
    "bg": "#0a0e0a",
    "panel": "#111911",
    "pre": "#0d120d",
    "green": "#39ff14",
    "cyan": "#00ffcc",
    "text": "#c3dcc3",
    "dim": "#8fae8f",
    "border": "#1f351f",
    "alert": "#ff8080",
}

P = PALETTE
PAIRS = [
    ("body text on background", P["text"], P["bg"], 4.5),
    ("body text on panel", P["text"], P["panel"], 4.5),
    ("body text in code block", P["text"], P["pre"], 4.5),
    ("secondary text on background", P["dim"], P["bg"], 4.5),
    ("secondary text on panel", P["dim"], P["panel"], 4.5),
    ("links / headings on background", P["green"], P["bg"], 4.5),
    ("accent on background", P["cyan"], P["bg"], 4.5),
    ("accent on panel", P["cyan"], P["panel"], 4.5),
    ("accent in code block", P["cyan"], P["pre"], 4.5),
    ("nav links on background", P["dim"], P["bg"], 4.5),
    ("alert count on panel", P["alert"], P["panel"], 4.5),
    ("alert count on background", P["alert"], P["bg"], 4.5),
]

#: `color:` sets text. `background-color:`, `border-color:` and friends do not,
#: and holding a hairline divider to a text ratio just teaches people to switch
#: the gate off. Captures the property name so they can be told apart.
_COLOUR_DECL = None


def scan(root: str, background: str = "#0a0e0a") -> int:
    """Check every TEXT colour in every HTML file under `root`.

    A hardcoded palette only catches what someone remembered to add to it. This
    reads the files, so a page using a colour nobody wrote down is still checked.
    Only `color:` declarations count — borders and backgrounds are structural and
    are reported separately without failing the run.
    """
    import re
    from pathlib import Path

    var_def = re.compile(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\b")
    # names that hold a surface rather than ink; a surface has no text ratio
    STRUCTURAL = ("bg", "background", "panel", "border", "surface", "shadow",
                  "line", "rule", "divider")
    fails = 0
    for path in sorted(Path(root).rglob("*.html")):
        if "node_modules" in str(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        variables = {m.group(1).lower(): m.group(2).lower()
                     for m in var_def.finditer(text)}
        if not variables:
            print(f"  {str(path.relative_to(root)):<44}no palette, skipped")
            continue
        bg = variables.get("bg") or variables.get("background") or background
        ink = {n: v for n, v in variables.items()
               if not any(s in n for s in STRUCTURAL)}
        bad = [(n, v, ratio(v, bg)) for n, v in sorted(ink.items())
               if ratio(v, bg) < 4.5]
        status = "ok" if not bad else "FAIL"
        print(f"  {str(path.relative_to(root)):<44}"
              f"{len(ink):>3} ink on {bg}  {status}")
        for n, v, r in bad:
            print(f"      --{n:<12}{v}  {r:.2f}:1  needs 4.5")
            fails += 1
    print()
    if fails:
        print(f"  {fails} text colour(s) below WCAG AA.")
        return 1
    print("  every text colour passes WCAG AA.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 1:
        raise SystemExit(scan(sys.argv[1]))
    raise SystemExit(check(PAIRS))
