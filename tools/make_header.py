#!/usr/bin/env python3
"""Deterministic generator for header.svg.

The header is a Needleman-Wunsch dynamic-programming matrix that fills in
diagonal wavefront order, then draws its own optimal traceback, then types on
the name. The grid and the path are not decorative: both are computed here
from a real alignment, so the picture is the algorithm it depicts.

Design constraints, all of them load-bearing:
  * 900x220 viewBox, so at a 360px phone (scale 0.40) 34px text lands at 13.6px
  * transparent ground, so no theme detection is needed anywhere
  * CSS @keyframes only, permitted by `style-src 'unsafe-inline'`
  * no script, no url(), no @import, no data: URIs, all blocked by
    `default-src 'none'` plus `sandbox` on raw.githubusercontent.com
  * system monospace plus textLength, so no font is ever fetched
  * every default CSS state is the FINISHED state and keyframes animate from
    the start, so frame zero is already the intended artwork
  * prefers-reduced-motion: reduce disables all animation
  * byte-deterministic output, which CI asserts by regenerating and diffing
"""

import argparse

# Two strings whose alignment is the picture. 23 x 8 gives a 24 x 9 matrix.
SEQ_A = "molecularandcellbiology"
SEQ_B = "computer"
MATCH, MISMATCH, GAP = 1, -1, -2

CELL, PAD = 14, 2
PITCH = CELL + PAD
GRID_X, GRID_Y = 40, 44

# Mid-lightness palette. Every colour must clear 3:1 against BOTH #ffffff and
# #0d1117, which is what lets one file serve light and dark mode.
C_CELL = "#6e7f99"
C_FILL = "#4f8f9c"
C_PATH = "#cf7a45"
C_TEXT = "#7b8a9e"

NAME = "ulzhan khamidolla"
SUB = "cs + mcb, berkeley '29"


def srgb_to_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def needleman_wunsch(a, b):
    """Global alignment with linear gaps. Returns (score, traceback, strings).

    Traceback is a list of (col, row) matrix coordinates from origin to corner,
    where col indexes `a` and row indexes `b`.
    """
    n, m = len(a), len(b)
    score = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = i * GAP
    for j in range(1, m + 1):
        score[0][j] = j * GAP

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub = MATCH if a[i - 1] == b[j - 1] else MISMATCH
            score[i][j] = max(
                score[i - 1][j - 1] + sub,
                score[i - 1][j] + GAP,
                score[i][j - 1] + GAP,
            )

    # Walk back from the corner, preferring diagonal on ties so the path reads
    # as an alignment rather than a staircase.
    i, j = n, m
    cells, top, bot = [(n, m)], [], []
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            sub = MATCH if a[i - 1] == b[j - 1] else MISMATCH
            if score[i][j] == score[i - 1][j - 1] + sub:
                top.append(a[i - 1]); bot.append(b[j - 1]); i, j = i - 1, j - 1
            elif score[i][j] == score[i - 1][j] + GAP:
                top.append(a[i - 1]); bot.append("-"); i -= 1
            else:
                top.append("-"); bot.append(b[j - 1]); j -= 1
        elif i > 0:
            top.append(a[i - 1]); bot.append("-"); i -= 1
        else:
            top.append("-"); bot.append(b[j - 1]); j -= 1
        cells.append((i, j))
    cells.reverse()
    return score[n][m], cells, ("".join(reversed(top)), "".join(reversed(bot)))


def build():
    cols, rows = len(SEQ_A) + 1, len(SEQ_B) + 1
    best, cells, (top, bot) = needleman_wunsch(SEQ_A, SEQ_B)
    path_cells = set(cells)

    out = []
    add = out.append
    add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 220" '
        'width="900" height="220" role="img" '
        f'aria-label="{NAME}, {SUB}">')

    # The delight, for anyone who opens view-source: the picture is honest.
    # This lives in <desc> rather than a comment because the aligned strings
    # contain runs of "--", which XML comments are not allowed to hold.
    add("<desc>")
    add("The path is the real Needleman-Wunsch traceback for")
    add(f"  {SEQ_A}  vs  {SEQ_B}")
    add(f"match {MATCH:+d}, mismatch {MISMATCH:+d}, gap {GAP:+d}, "
        f"optimal score {best:+d}")
    add(f"  {top}")
    add(f"  {bot}")
    add("Computed by tools/make_header.py, not drawn by hand.")
    add("</desc>")

    add("<style>")
    add(".c{opacity:1}")
    add(".p{stroke-dashoffset:0}")
    add(".t{clip-path:inset(0 0 0 0)}")
    add("@keyframes f{from{opacity:0}to{opacity:1}}")
    add("@keyframes d{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}")
    add("@keyframes y{from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}")
    add(".c{animation:f .45s ease-out both}")
    add(".p{animation:d 1.1s 1.25s ease-in-out both}")
    add(".t{animation:y .7s 2.1s steps(22,end) both}")
    add(".t2{animation-delay:2.55s}")
    for k in range(rows + cols - 1):
        add(f".w{k}{{animation-delay:{k * 0.035:.3f}s}}")
    add("@media(prefers-reduced-motion:reduce){.c,.p,.t{animation:none}}")
    add("</style>")

    add('<g>')
    for r in range(rows):
        for c in range(cols):
            x, y = GRID_X + c * PITCH, GRID_Y + r * PITCH
            on_path = (c, r) in path_cells
            add(f'<rect class="c w{r + c}" x="{x}" y="{y}" width="{CELL}" '
                f'height="{CELL}" rx="2" '
                f'fill="{C_FILL if on_path else C_CELL}" '
                f'fill-opacity="{"0.55" if on_path else "0.20"}"/>')
    add("</g>")

    pts = [(GRID_X + c * PITCH + CELL / 2, GRID_Y + r * PITCH + CELL / 2)
           for c, r in cells]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    add(f'<path class="p" d="{d}" fill="none" stroke="{C_PATH}" '
        'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" '
        'pathLength="1" stroke-dasharray="1"/>')

    fam = ("ui-monospace,SFMono-Regular,SF Mono,Menlo,Consolas,"
           "DejaVu Sans Mono,monospace")
    add(f'<text class="t" x="486" y="104" font-family="{fam}" font-size="34" '
        f'font-weight="600" fill="{C_TEXT}" textLength="352" '
        f'lengthAdjust="spacingAndGlyphs">{NAME}</text>')
    add(f'<text class="t t2" x="486" y="140" font-family="{fam}" '
        f'font-size="30" fill="{C_TEXT}" fill-opacity="0.75" '
        f'textLength="330" lengthAdjust="spacingAndGlyphs">{SUB}</text>')

    add("</svg>")
    return "\n".join(out) + "\n", (best, top, bot, cols, rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="header.svg")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()

    svg, (best, top, bot, cols, rows) = build()
    with open(args.out, "w") as fh:
        fh.write(svg)
    if args.quiet:
        raise SystemExit(0)

    print(f"wrote {args.out}: {len(svg.encode()):,} bytes (budget 40,960)")
    print(f"matrix {cols} x {rows} = {cols * rows} cells")
    print(f"alignment score {best:+d}")
    print(f"  {top}")
    print(f"  {bot}")
    print("\ncontrast (need >= 3.0 against both themes):")
    for name, col in (("cell", C_CELL), ("fill", C_FILL),
                      ("path", C_PATH), ("text", C_TEXT)):
        lt, dk = contrast(col, "#ffffff"), contrast(col, "#0d1117")
        print(f"  {'OK  ' if min(lt, dk) >= 3.0 else 'FAIL'} {name:5s} {col} "
              f" light {lt:4.2f}  dark {dk:4.2f}")
    print("\nmobile scaling:")
    for w in (390, 360):
        s = w / 900
        print(f"  {w}px -> scale {s:.3f}; 34px -> {34 * s:.1f}px; "
              f"2.5px stroke -> {2.5 * s:.2f}px")
