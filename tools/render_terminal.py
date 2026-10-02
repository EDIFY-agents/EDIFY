#!/usr/bin/env python3
"""Render real terminal output into an SVG that looks like a terminal.

The README shows the product working. That evidence is only worth anything if it
is real, so these images are generated from captured output of the actual binary
rather than drawn by hand — and this script is committed so anyone can regenerate
them and check.

    python tools/render_terminal.py assets/specs/graph-where.txt assets/graph-where.svg

The input file is a transcript: lines beginning with `$ ` are prompts, everything
else is output. The first line may be `#! title — caption`, which becomes the
readout in the frame's top corners.

A transcript captured from a terminal keeps its colour. Output lines may carry the
SGR escapes the CLI wrote — the 16 basic colours, 256-colour and 24-bit — and they
are drawn as written, so the image is the CLI's own palette rather than a guess at
it. A line with no escapes is coloured by what it says (`ok`, `degraded`, `error`),
which is how older, plain transcripts still render.

The half blocks the wordmark is set in (`█ ▀ ▄`) are drawn as rectangles: a font
leaves a gap between rows, and the wordmark would come out striped.

No dependencies, like everything else here.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

# The site's tokens (`--ed-*`). Dark only: a terminal is dark, and a light-mode
# terminal screenshot reads as a mockup even when it is not.
BG = "#04060A"          # --ed-well: "terminal only"
CHROME = "#07090C"      # --ed-void: the readout band
RULE = "#1C1F24"        # --ed-line-2, 12% over the void
TICK = "#4A4D51"        # --ed-line-4: the corner ticks every clip carries
TEXT = "#C4C8CE"        # output: between --ed-text-1 and -2
DIM = "#6A6D71"         # --ed-text-3: readouts, comments
SIGNAL = "#7ABDFF"      # --ed-blue-bright: the prompt, a pass
AMBER = "#F2A359"       # --ed-amber-bright: degraded
OXIDE = "#EA6B62"       # --ed-oxide-bright: broken
WHITE = "#E8ECF2"       # --ed-text-1: the command the user typed

#: The basic colours, as the CLI's 16-colour fallback means them.
BASIC = {
    "30": "#07090C", "31": OXIDE, "32": SIGNAL, "33": AMBER, "34": "#2C6FD6",
    "35": "#B48CF2", "36": SIGNAL, "37": WHITE, "90": DIM, "91": OXIDE, "92": SIGNAL,
    "93": AMBER, "94": SIGNAL, "95": "#B48CF2", "96": SIGNAL, "97": WHITE,
}

FONT = ("'IBM Plex Mono', ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'DejaVu Sans Mono', monospace")

CH = 8.42               # character advance at 14px in this stack
LH = 22                 # line height
PAD_X = 24
PAD_TOP = 56            # below the readout band
PAD_BOT = 22
BAR = 34                # readout band height
BLOCKS = {"█": (0.0, 1.0), "▀": (0.0, 0.5), "▄": (0.5, 1.0)}

_SGR = re.compile(r"\x1b\[([0-9;]*)m")


def classify(line: str) -> str:
    """Which token colours a plain line. Order matters: first match wins."""
    stripped = line.strip()
    if line.startswith("$ "):
        return "prompt"
    if stripped.startswith("#"):
        return "comment"
    if stripped.startswith(("[x]", "ok ", "ok\t")):
        return "ok"
    if stripped.startswith(("[!]", "degraded", "warn")):
        return "warn"
    if stripped.startswith(("[-]", "error", "missing", "modified", "amber")):
        return "error"
    if stripped.startswith(("→", "->")):
        return "accent"
    return "text"


COLOURS = {
    "prompt": WHITE, "comment": DIM, "ok": SIGNAL, "warn": AMBER,
    "error": OXIDE, "accent": SIGNAL, "text": TEXT,
}


def _xterm(n: int) -> str:
    if n < 16:
        return BASIC.get(str(30 + n if n < 8 else 82 + n), TEXT)
    if n < 232:
        n -= 16
        steps = (0, 95, 135, 175, 215, 255)
        return "#%02X%02X%02X" % (steps[n // 36], steps[(n // 6) % 6], steps[n % 6])
    grey = 8 + (n - 232) * 10
    return "#%02X%02X%02X" % (grey, grey, grey)


def spans(line: str, default: str) -> list[tuple[str, str, bool]]:
    """`line` as (text, colour, bold) runs, following its SGR escapes."""
    out: list[tuple[str, str, bool]] = []
    colour, bold, at = default, False, 0
    for match in _SGR.finditer(line):
        if match.start() > at:
            out.append((line[at:match.start()], colour, bold))
        codes = [c for c in match.group(1).split(";") if c] or ["0"]
        i = 0
        while i < len(codes):
            code = codes[i]
            if code == "0":
                colour, bold = default, False
            elif code == "1":
                bold = True
            elif code == "2":
                colour = DIM
            elif code == "38" and i + 1 < len(codes) and codes[i + 1] == "2" and i + 4 < len(codes):
                colour = "#%02X%02X%02X" % tuple(int(v) for v in codes[i + 2:i + 5])
                i += 4
            elif code == "38" and i + 2 < len(codes) and codes[i + 1] == "5":
                colour = _xterm(int(codes[i + 2]))
                i += 2
            elif code in BASIC:
                colour = BASIC[code]
            i += 1
        at = match.end()
    if at < len(line):
        out.append((line[at:], colour, bold))
    return out


def visible(line: str) -> str:
    return _SGR.sub("", line)


def _text(x: float, y: float, runs: list[tuple[str, str, bool]]) -> str:
    parts = []
    for text, colour, bold in runs:
        weight = ' font-weight="600"' if bold else ""
        parts.append(f'<tspan fill="{colour}"{weight}>{html.escape(text)}</tspan>')
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="14" '
            f'xml:space="preserve">{"".join(parts)}</text>')


def _blocks(y_top: float, runs: list[tuple[str, str, bool]]) -> tuple[list[str], list[tuple[str, str, bool]]]:
    """Lift the half blocks out of a line as rectangles; leave spaces in their place."""
    rects: list[str] = []
    kept: list[tuple[str, str, bool]] = []
    col = 0
    for text, colour, bold in runs:
        chars = []
        for ch in text:
            if ch in BLOCKS:
                top, bottom = BLOCKS[ch]
                rects.append(
                    f'<rect x="{PAD_X + col * CH:.2f}" y="{y_top + top * LH:.2f}" '
                    f'width="{CH + 0.4:.2f}" height="{(bottom - top) * LH + 0.4:.2f}" fill="{colour}"/>'
                )
                chars.append(" ")
            else:
                chars.append(ch)
            col += 1
        kept.append(("".join(chars), colour, bold))
    return rects, kept


def render(lines: list[str], title: str) -> str:
    left, _, right = title.partition(" — ")
    left = left.upper().replace("EDIFY ", "EDIFY / ", 1)
    width = max([len(visible(l)) for l in lines] + [len(left) + len(right) + 8, 46])
    w = int(width * CH) + PAD_X * 2
    h = PAD_TOP + len(lines) * LH + PAD_BOT

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="Terminal: {html.escape(title)}">',
        f'<rect width="{w}" height="{h}" rx="2" fill="{BG}"/>',
        f'<rect width="{w}" height="{BAR}" rx="2" fill="{CHROME}"/>',
        f'<line x1="0" y1="{BAR}" x2="{w}" y2="{BAR}" stroke="{RULE}" stroke-width="1"/>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="2" '
        f'fill="none" stroke="{RULE}" stroke-width="1"/>',
    ]

    # The corner ticks and the readout: the frame every clip on the site carries.
    for x, y, dx, dy in ((8, BAR + 8, 1, 1), (w - 8, BAR + 8, -1, 1),
                         (8, h - 8, 1, -1), (w - 8, h - 8, -1, -1)):
        out.append(f'<path d="M{x} {y + 9 * dy} V{y} H{x + 9 * dx}" fill="none" '
                   f'stroke="{TICK}" stroke-width="1"/>')
    label = f'font-family="{FONT}" font-size="10.5" fill="{DIM}"'
    out.append(f'<text x="{PAD_X}" y="{BAR / 2 + 4}" {label} letter-spacing="1.6">'
               f'{html.escape(left)}</text>')
    if right:
        out.append(f'<text x="{w - PAD_X}" y="{BAR / 2 + 4}" {label} text-anchor="end" '
                   f'letter-spacing="0.4">{html.escape(right)}</text>')

    y = PAD_TOP + 4
    for line in lines:
        if line.startswith("$ "):
            out.append(_text(PAD_X, y, [("$ ", SIGNAL, False), (line[2:], WHITE, False)]))
        else:
            runs = spans(line, COLOURS[classify(visible(line))] if "\x1b[" not in line else TEXT)
            rects, runs = _blocks(y - 15.5, runs)
            out.extend(rects)
            if any(t.strip() for t, _, _ in runs):
                out.append(_text(PAD_X, y, runs))
        y += LH

    out.append("</svg>")
    return "\n".join(out)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    raw = src.read_text(encoding="utf-8").rstrip("\n").split("\n")

    title = raw[0][2:].strip() if raw and raw[0].startswith("#!") else src.stem
    body = raw[1:] if raw and raw[0].startswith("#!") else raw

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(render(body, title), encoding="utf-8")
    print(f"{dst}  ({len(body)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
