#!/usr/bin/env python3
"""Check that header.svg survives GitHub's delivery path and both themes.

GitHub serves a README image from raw.githubusercontent.com under

    content-security-policy: default-src 'none'; style-src 'unsafe-inline'; sandbox

and renders it through an <img>, which the SVG Integration spec calls secure
animated mode. That combination permits declarative animation and inline CSS
and forbids basically everything else. These checks encode that, plus the
legibility constraints that let one file serve light and dark mode.

Run: python3 tools/lint_svg.py
"""

import re
import subprocess
import sys
import xml.dom.minidom

SVG = "header.svg"
GEN = "tools/make_header.py"
MAX_BYTES = 40960
MAX_VIEWBOX_W = 1000
MIN_CONTRAST = 3.0
THEMES = {"light": "#ffffff", "dark": "#0d1117"}

# Each of these is blocked or unreliable on GitHub's delivery path.
FORBIDDEN = {
    "<script": "scripts are blocked by sandbox and default-src 'none'",
    "foreignObject": "HTML in SVG does not render through <img>",
    "@import": "external references are disabled in secure animated mode",
    "url(": "no font-src or img-src, so every url() reference fails",
    "data:": "data URIs are blocked, there is no img-src on raw.githubusercontent",
    "prefers-color-scheme": "cannot see the host page theme, renders wrong half the time",
    "<image": "raster embedding needs img-src, which is not granted",
    "<a ": "links do not activate in secure animated mode",
}

failures = []


def fail(msg):
    failures.append(msg)


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


def main():
    try:
        raw = open(SVG, "rb").read()
    except FileNotFoundError:
        print(f"FAIL  {SVG} is missing")
        return 1
    text = raw.decode()

    # 1. well-formed XML. This is not pedantry: aligned sequences contain runs
    # of "--", which an XML comment may not hold, and that bug shipped once.
    try:
        xml.dom.minidom.parseString(text)
        print("ok    well-formed XML")
    except Exception as exc:
        fail(f"not well-formed XML: {exc}")

    # 2. nothing the sandbox will drop
    for token, why in FORBIDDEN.items():
        if token in text:
            fail(f"contains {token!r}: {why}")
    if not any(t in text for t in FORBIDDEN):
        print(f"ok    none of the {len(FORBIDDEN)} forbidden constructs present")

    # 3. inline style attributes are permitted but we avoid them, so that the
    # whole presentation lives in one auditable <style> block
    if re.search(r'\sstyle="', text):
        fail("inline style= attribute present, keep presentation in <style>")
    else:
        print("ok    no inline style attributes")

    # 4. motion safety
    if "prefers-reduced-motion" not in text:
        fail("no prefers-reduced-motion block")
    else:
        print("ok    prefers-reduced-motion honoured")

    # 5. a transparent ground is what lets one file serve both themes
    if re.search(r'<rect[^>]*\swidth="900"[^>]*\sheight="220"', text):
        fail("full-bleed background rect would break one of the two themes")
    else:
        print("ok    transparent background")

    # 6. size, because camo caches for a year and mobile pays for bytes
    if len(raw) > MAX_BYTES:
        fail(f"{len(raw)} bytes exceeds the {MAX_BYTES} budget")
    else:
        print(f"ok    {len(raw):,} bytes (budget {MAX_BYTES:,})")

    # 7. mobile legibility. GitHub injects max-width:100%, so a wide viewBox
    # shrinks text below readable size on a phone.
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', text)
    if not m:
        fail("no parseable viewBox")
    else:
        w, h = int(m.group(1)), int(m.group(2))
        if w > MAX_VIEWBOX_W:
            fail(f"viewBox width {w} > {MAX_VIEWBOX_W}, text would be unreadable at 360px")
        else:
            scale = 360 / w
            sizes = [int(s) for s in re.findall(r'font-size="(\d+)"', text)]
            smallest = min(sizes) * scale if sizes else 0
            if smallest < 11:
                fail(f"smallest text renders at {smallest:.1f}px on a 360px screen")
            else:
                print(f"ok    viewBox {w}x{h}, smallest text {smallest:.1f}px at 360px wide")

    # 8. every colour must read on both themes, since there is no theme switch
    bad = []
    for col in sorted(set(re.findall(r'#[0-9a-fA-F]{6}', text))):
        ratios = {k: contrast(col, v) for k, v in THEMES.items()}
        if min(ratios.values()) < MIN_CONTRAST:
            bad.append((col, ratios))
    if bad:
        for col, r in bad:
            fail(f"{col} contrast light {r['light']:.2f} dark {r['dark']:.2f}, "
                 f"need >= {MIN_CONTRAST} on both")
    else:
        print(f"ok    all colours clear {MIN_CONTRAST}:1 on both themes")

    # 9. the committed file must be exactly what the generator produces, so a
    # hand edit cannot silently diverge from the source of truth
    out = subprocess.run([sys.executable, GEN, "-o", "/tmp/_lint_header.svg", "-q"],
                         capture_output=True)
    if out.returncode != 0:
        fail(f"generator failed: {out.stderr.decode()[:200]}")
    elif open("/tmp/_lint_header.svg", "rb").read() != raw:
        fail(f"{SVG} differs from `python3 {GEN}` output, regenerate instead of hand editing")
    else:
        print("ok    byte-identical to generator output")

    print()
    if failures:
        for f in failures:
            print(f"FAIL  {f}")
        print(f"\n{len(failures)} problem(s)")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
