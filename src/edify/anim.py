"""An infinity, drawn while the install works.

`edify init` and `edify setup` do real work — extraction, skill install, host
mirroring — and until now printed nothing while doing it. This is the face of that
wait, and it is held to the same rules as every other line this CLI writes.

**Precomputed frames, not a live plotter** (plan D-3). `dependencies = []` is a hard
constraint, so there is no curses and no progress-bar library. The frames are a
tuple of strings built once at import, which also makes the animation *testable* —
frame count, uniform width, ASCII-safety — rather than something only a human can
check by squinting at a terminal.

**A lemniscate of Gerono** (D-4), `x = cos t`, `y = sin(2t)/2`. It is bounded and
evenly parameterised, so a head moving at constant `t` moves at roughly constant
speed on screen. The Bernoulli lemniscate crowds at the origin and reads as a
stutter, and a rotating unicode spinner is not an infinity at all.

**Two glyph sets, chosen by probing the stream** (D-5). `ui.py` already documents
that a cp1252 Windows console kills a `·`; a command that did its work and then
died printing its own decoration is the worst of both outcomes.

**Decoration is never load-bearing.** Any exception inside the painter disables the
animation and the command carries on, which is the rule `_invite` already follows
in `cli.py`. The cursor is restored in a `finally` and again at `atexit`, so a
Ctrl-C never leaves a headless terminal behind.
"""

from __future__ import annotations

import atexit
import math
import os
import sys
import threading
import time
from typing import Any

from . import ui

# -- geometry ---------------------------------------------------------------

WIDTH = 31
HEIGHT = 7
FRAMES = 48
#: Samples along the curve. Dense enough that the drawn line has no gaps at this
#: resolution, which is a property of the grid rather than a number to tune.
SAMPLES = 480
#: How many samples behind the head still get the warm glyph. The trail is what
#: makes the motion readable; without it the head is a dot that appears to
#: teleport from one arm of the curve to the other.
TRAIL = 34

#: Head, trail, curve. Two sets: what a UTF-8 terminal renders, and what survives
#: a code page that has never heard of U+00B7.
UNICODE_GLYPHS = ("●", "○", "·")
ASCII_GLYPHS = ("O", "o", ".")

FPS = 14.0

#: How much of a spinner's label is shown. The label says what the wait is for;
#: past this it is a paragraph, and a terminal narrower than it wraps and breaks
#: the repaint.
LABEL = 60


def _point(t: float) -> tuple[float, float]:
    """Gerono at parameter `t`, in [-1, 1] x [-0.5, 0.5]."""
    return math.cos(t), math.sin(2.0 * t) / 2.0


def _cell(t: float) -> tuple[int, int]:
    """One curve point as a grid cell.

    x spans 2 units across WIDTH columns, y spans 1 unit across HEIGHT rows. The
    halved y in `_point` is the 2:1 aspect correction: a character is about twice
    as tall as it is wide, so an uncorrected plot of a symmetric curve comes out
    as a tall thin bow tie rather than an infinity.
    """
    x, y = _point(t)
    col = int(round((x + 1.0) / 2.0 * (WIDTH - 1)))
    row = int(round((0.5 - y) * (HEIGHT - 1)))
    return max(0, min(HEIGHT - 1, row)), max(0, min(WIDTH - 1, col))


def _build(glyphs: tuple[str, str, str]) -> tuple[str, ...]:
    """The whole animation, as `FRAMES` blocks of `HEIGHT` lines each `WIDTH` wide.

    Every frame draws the same static curve and moves a bright head along it, so
    the shape never flickers and only the highlight travels.
    """
    head_glyph, warm_glyph, curve_glyph = glyphs

    curve: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for i in range(SAMPLES):
        t = 2.0 * math.pi * i / SAMPLES
        cell = _cell(t)
        if cell not in seen:
            seen.add(cell)
            curve.append(cell)

    frames: list[str] = []
    for f in range(FRAMES):
        grid = [[" "] * WIDTH for _ in range(HEIGHT)]
        for row, col in curve:
            grid[row][col] = curve_glyph

        # Painted tail first, so the head always wins its cell.
        lead = int(SAMPLES * f / FRAMES)
        for back in range(TRAIL, 0, -1):
            row, col = _cell(2.0 * math.pi * ((lead - back) % SAMPLES) / SAMPLES)
            grid[row][col] = warm_glyph
        row, col = _cell(2.0 * math.pi * lead / SAMPLES)
        grid[row][col] = head_glyph
        frames.append("\n".join("".join(row) for row in grid))
    return tuple(frames)


def _tones() -> tuple[dict[tuple[int, int], int], ...]:
    """For every frame, each lit cell's age: 0 is the head, `TRAIL` the oldest.

    The same walk `_build` makes, kept apart from the glyphs so a frame's text is
    unchanged by colour. The painter reads the age to shade the trail from the
    bright head into the deeper ink, the way a drop thins as it spreads.
    """
    table = []
    for f in range(FRAMES):
        lead = int(SAMPLES * f / FRAMES)
        ages: dict[tuple[int, int], int] = {}
        for back in range(TRAIL, -1, -1):
            ages[_cell(2.0 * math.pi * ((lead - back) % SAMPLES) / SAMPLES)] = back
        table.append(ages)
    return tuple(table)


#: Built once, at import. Two tuples of `FRAMES` strings — deterministic, and so
#: assertable in a test rather than only visible to a person.
UNICODE_FRAMES: tuple[str, ...] = _build(UNICODE_GLYPHS)
ASCII_FRAMES: tuple[str, ...] = _build(ASCII_GLYPHS)
TONES = _tones()

#: The wordmark. Pure ASCII by construction, because it survives a pipe, a CI log,
#: and a code page — it is printed even when the animation is not.
BANNER = (
    "   ___ ___ ___ ___ __   __",
    "  | __|   \\_ _| __|\\ \\ / /   the infinite loop, made finite",
    "  | _|| |) | || _|  \\ V /    three documents and a map",
    "  |___|___/___|_|    |_|",
)

#: The wordmark a person at a terminal sees: the site's heavy sans, in half blocks.
#: Three rows, so it is a mark and not a poster.
WORDMARK = (
    "█▀▀▀ █▀▀▄ █ █▀▀▀ █   █",
    "█▀▀  █  █ █ █▀▀   ▀█▀ ",
    "▀▀▀▀ ▀▀▀  ▀ ▀      ▀  ",
)

#: The readout under the wordmark, as wide as the clips' corner readouts sit apart.
READOUT_WIDTH = 46

#: The ink pool. Where it comes to rest (a column of the wordmark), how wide it is
#: on each row — uneven, so it reads as liquid and not as a highlighter — and how
#: long it takes to arrive: `--d-el`, the site's single-element entrance.
POOL_REST = 9.0
POOL_HALF = (4.5, 5.5, 3.5)
POOL_MS = 420
POOL_FRAMES = 12


# -- glyph selection --------------------------------------------------------


def frames_for(stream: Any = None) -> tuple[str, ...]:
    """The frame table this stream can actually print.

    Probes `stream.encoding` rather than assuming, mirroring the degradation
    `ui._emit` already performs. A stream with no encoding, or one that cannot
    round-trip the glyphs, gets the ASCII table.
    """
    stream = stream if stream is not None else sys.stderr
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return ASCII_FRAMES
    try:
        "".join(UNICODE_GLYPHS).encode(encoding)
    except (UnicodeEncodeError, LookupError, TypeError):
        return ASCII_FRAMES
    return UNICODE_FRAMES


# -- terminal control -------------------------------------------------------

_HIDE = "\033[?25l"
_SHOW = "\033[?25h"
_UP = "\033[F"
_CLEAR_LINE = "\033[2K"

#: Set the first time a painter hides the cursor. The `atexit` backstop checks it,
#: so a run that never animated — every test, every pipe, every CI job — does not
#: emit a stray escape sequence into somebody's captured output.
_hid_cursor = False


def _restore_cursor() -> None:
    """The backstop. Registered at `atexit` so a hard exit still shows a cursor."""
    global _hid_cursor
    if not _hid_cursor:
        return
    _hid_cursor = False
    try:
        sys.stderr.write(_SHOW)
        sys.stderr.flush()
    except (OSError, ValueError):
        pass


atexit.register(_restore_cursor)


# -- the spinner ------------------------------------------------------------


class Spinner:
    """Paint the infinity to stderr while the block runs. A context manager.

    stderr, not stdout: `--json` output and every piped answer stay clean by
    construction rather than by remembering. The thread is a daemon, so an
    interpreter that is shutting down is never held open by decoration.

    Whether it paints at all is `Out.animated` — the one place tty, `--json`,
    `--quiet`, `--no-anim`, `EDIFY_NO_ANIM`, `CI` and `TERM=dumb` are decided,
    next to the existing `Out.interactive`. When it does not paint, the label is
    still printed as one static line, so a pipe and a CI log say what happened.
    """

    def __init__(self, out: Any, label: str = "", stream: Any = None) -> None:
        self.out = out
        self.label = label
        self.stream = stream if stream is not None else sys.stderr
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._painted = False
        self._start = time.monotonic()
        self._lines = HEIGHT + (1 if label else 0)

    # -- lifecycle ---------------------------------------------------

    def __enter__(self) -> "Spinner":
        self._start = time.monotonic()
        if not self._enabled():
            if self.label:
                self.out.note(self.label)
            return self
        try:
            self._thread = threading.Thread(target=self._paint, daemon=True)
            self._thread.start()
        except RuntimeError:
            # No threads available. Not a reason for the command to fail.
            self._thread = None
            if self.label:
                self.out.note(self.label)
        return self

    def __exit__(self, *exc: Any) -> bool:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=1.0)
        self._erase()
        return False  # never swallow the block's exception

    # -- internals ---------------------------------------------------

    def _enabled(self) -> bool:
        return bool(getattr(self.out, "animated", False))

    def _paint(self) -> None:
        """The painter. Every failure here disables the animation, silently."""
        global _hid_cursor
        frames = frames_for(self.stream)
        try:
            # The `atexit` backstop writes to the real stderr, so it only arms when
            # that is the stream being painted. A spinner pointed somewhere else
            # cleans up in its own `finally` and leaves the real terminal alone.
            if self.stream is sys.stderr:
                _hid_cursor = True
            self.stream.write(_HIDE)
            index = 0
            while not self._stop.is_set():
                self._write_frame(frames[index % len(frames)], index % len(frames))
                index += 1
                self._stop.wait(1.0 / FPS)
        except Exception:  # noqa: BLE001 — decoration is never load-bearing
            self._stop.set()
        finally:
            try:
                self.stream.write(_SHOW)
                self.stream.flush()
            except Exception:  # noqa: BLE001
                pass

    def _write_frame(self, frame: str, index: int = 0) -> None:
        colour = bool(getattr(self.out, "color_err", False))
        body = "\n".join("  " + row for row in inked(frame, index, colour).split("\n"))
        if self.label:
            # The clips carry a readout in their corners; the wait carries one too.
            took = f"{time.monotonic() - self._start:4.1f}s"
            said = f"  {self.label[:LABEL]}  {took}"
            if colour:
                said = f"  {ui.sgr('muted')}{self.label[:LABEL]}{ui.RESET}  {ui.sgr('faint')}{took}{ui.RESET}"
            body = body + "\n" + said
        if self._painted:
            self.stream.write(_UP * self._lines)
        chunks = []
        for line in body.split("\n"):
            chunks.append(_CLEAR_LINE + line + "\n")
        self.stream.write("".join(chunks))
        self.stream.flush()
        self._painted = True

    def _erase(self) -> None:
        """Take the region back off the screen and restore the cursor.

        In a `finally` on purpose: an exception in the wrapped block must not be
        the reason somebody's terminal has no cursor for the rest of the day.
        """
        if not self._painted:
            return
        self._painted = False
        try:
            self.stream.write(_UP * self._lines)
            for _ in range(self._lines):
                self.stream.write(_CLEAR_LINE + "\n")
            self.stream.write(_UP * self._lines)
            self.stream.write(_SHOW)
            self.stream.flush()
        except Exception:  # noqa: BLE001
            pass


class NullSpinner:
    """What a caller gets when it wants the shape without the animation."""

    def __enter__(self) -> "NullSpinner":
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


def spinner(out: Any, label: str = "") -> Any:
    """The one call site every command uses. Always safe, always a context manager."""
    try:
        return Spinner(out, label)
    except Exception:  # noqa: BLE001 — decoration is never load-bearing
        return NullSpinner()


# -- the banner -------------------------------------------------------------


def banner(out: Any, verb: str = "init") -> None:
    """The wordmark, once, as the install opens.

    Suppressed only by `--json` and `--quiet` — not by the absence of a tty. Off a
    terminal it is the static ASCII `BANNER`, so it survives a pipe and reads fine
    in a CI log, and a build log that says which tool wrote it is more useful than
    one that does not. At a terminal it is the site's wordmark, and the ink pours
    into it once.
    """
    if getattr(out, "json_mode", False) or getattr(out, "quiet", False):
        return
    if os.environ.get("EDIFY_NO_ANIM"):
        return
    if getattr(out, "no_anim", False):
        return
    try:
        if getattr(out, "animated", False) and ui.encodes("█▀▄─", sys.stderr):
            _wordmark(out, verb)
            return
        for line in BANNER:
            out.note(line)
        out.note("")
    except Exception:  # noqa: BLE001
        pass


def _ease(t: float) -> float:
    """`--e-edify`, cubic-bezier(.2,.8,.2,1), closely enough for twelve frames."""
    return 1.0 - (1.0 - t) ** 3


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def ink(row: int, line: str, centre: float, colour: bool) -> str:
    """One row of the wordmark with the pool at `centre`.

    Inside the pool a glyph takes the ink: bright at the heart, the deeper edge
    blue at the rim. Outside it keeps the terminal's own foreground — flat is the
    agent alone, the ink is EDIFY. A 16-colour terminal gets one blue.
    """
    if not colour:
        return line
    palette = ui.PALETTES[ui.theme()]
    bright, edge = ui.rgb(palette["signal"]), ui.rgb(palette["edge"])
    bits = ui.depth()
    half = POOL_HALF[row % len(POOL_HALF)]
    cells = []
    for col, glyph in enumerate(line):
        reach = abs(col - centre) / half
        if glyph == " " or reach > 1.0:
            cells.append(glyph)
            continue
        start = "\033[94m" if bits == 16 else ui.fg(_mix(bright, edge, reach ** 1.6), bits)
        cells.append(start + glyph + ui.RESET)
    return "".join(cells)


def inked(frame: str, index: int, colour: bool) -> str:
    """A frame of the infinity in ink: the head bright, the trail thinning into the
    deeper blue, the curve at rest in the faint tone. Text unchanged without colour."""
    if not colour:
        return frame
    palette = ui.PALETTES[ui.theme()]
    bright, edge = ui.rgb(palette["signal"]), ui.rgb(palette["edge"])
    faint, bits = ui.sgr("faint"), ui.depth()
    ages = TONES[index % len(TONES)]
    rows = []
    for r, row in enumerate(frame.split("\n")):
        cells = []
        for c, glyph in enumerate(row):
            if glyph == " ":
                cells.append(glyph)
                continue
            age = ages.get((r, c))
            if age is None:
                start = faint
            elif bits == 16:
                start = "\033[94m" if age == 0 else "\033[34m"
            else:
                start = ui.fg(_mix(bright, edge, age / TRAIL), bits)
            cells.append(start + glyph + ui.RESET)
        rows.append("".join(cells))
    return "\n".join(rows)


def readout(verb: str, colour: bool, width: int = READOUT_WIDTH) -> str:
    """`EDIFY / INIT ──────── 0.2.0` — the clips' corner readout, as one line."""
    from . import __version__

    left, right = f"EDIFY / {verb.upper()}", __version__
    rule = "─" * max(3, width - len(left) - len(right) - 2)
    if not colour:
        return f"{left} {rule} {right}"
    muted, faint = ui.sgr("muted"), ui.sgr("faint")
    return f"{muted}{left}{ui.RESET} {faint}{rule}{ui.RESET} {muted}{right}{ui.RESET}"


def _wordmark(out: Any, verb: str) -> None:
    """Paint the wordmark to stderr, pour the ink once, and leave it standing."""
    stream = sys.stderr
    colour = bool(getattr(out, "color_err", False))
    pad = "  "
    rows = len(WORDMARK)
    tail = [readout(verb, colour), ui.sgr("muted") + "three documents and a map" + ui.RESET if colour
            else "three documents and a map", ""]

    def paint(centre: float, first: bool) -> None:
        if not first:
            stream.write(_UP * rows)
        stream.write("".join(
            _CLEAR_LINE + pad + ink(r, WORDMARK[r], centre, colour) + "\n" for r in range(rows)
        ))
        stream.flush()

    if colour:
        start = -max(POOL_HALF) - 1.0
        stream.write(_HIDE)
        try:
            for f in range(POOL_FRAMES + 1):
                centre = start + (POOL_REST - start) * _ease(f / POOL_FRAMES)
                paint(centre, first=f == 0)
                if f < POOL_FRAMES:
                    time.sleep(POOL_MS / 1000.0 / POOL_FRAMES)
        finally:
            stream.write(_SHOW)
    else:
        paint(POOL_REST, first=True)
    for line in tail:
        stream.write(pad + line + "\n" if line else "\n")
    stream.flush()


def elapsed(start: float) -> str:
    """`2.4s` — what a spinner was covering for, said once after it stops."""
    return f"{max(0.0, time.monotonic() - start):.1f}s"
