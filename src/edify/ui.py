"""Output. One place, so `--json` and `--no-color` are honoured everywhere.

Every command writes through here. Machine output goes to stdout as JSON when
`--json` is set; human notes and warnings go to stderr so a pipe stays clean.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

RESET = "\033[0m"

#: The site's tokens (`--ed-*` in the public site's DESIGN-TOKENS.md), as a
#: terminal can show them. Two sets, because the clips already come in two —
#: FOIL / NIGHT and FOIL / DAY — and a light terminal is a real place people read
#: this. Body text is never coloured: the terminal's own foreground is the one
#: colour guaranteed to read on the terminal's own background.
PALETTES = {
    "night": {
        "signal": "#7ABDFF",    # --ed-blue-bright: a pass, the next step
        "edge": "#2C6FD6",      # --ed-blue: the ink
        "advisory": "#F2A359",  # --ed-amber-bright: works, degraded
        "blocked": "#EA6B62",   # --ed-oxide-bright: does not work
        "muted": "#6A6D71",     # --ed-text-3 over the void: notes, labels
        "faint": "#4F5256",     # --ed-text-4: hairlines, the curve at rest
    },
    "day": {
        "signal": "#2C6FD6",    # --ed-blue holds 4.9:1 on paper
        "edge": "#0C3965",      # --ed-blue-deep
        "advisory": "#A8621C",  # amber, darkened until it reads on paper
        "blocked": "#C74B45",   # --ed-oxide
        "muted": "#6B6D72",     # --ed-ink-3
        "faint": "#A3A5AA",
    },
}

#: What a 16-colour terminal gets for each token.
_BASIC = {
    "signal": "94", "edge": "34", "advisory": "33", "blocked": "31",
    "muted": "2", "faint": "2",
}

#: The names call sites used before the palette existed. The brand's pass is blue,
#: not green: `[x] pass` on the site is the enforced blue.
_ALIASES = {
    "green": "signal", "blue": "signal", "cyan": "signal",
    "yellow": "advisory", "red": "blocked", "dim": "muted",
}

#: The site's state device, verbatim. ASCII, so no code page can break it.
MARKS = {"pass": "[x]", "advisory": "[!]", "blocked": "[-]", "uncovered": "[ ]"}

#: The label column of a report: wide enough for `conventions`, the longest one.
LABEL_WIDTH = 11

_TRUECOLOR_PROGRAMS =("vscode", "iTerm.app", "WezTerm", "ghostty")


def depth() -> int:
    """24, 256 or 16. Asked of the environment, because a terminal cannot be asked."""
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return 24
    if os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM") in _TRUECOLOR_PROGRAMS:
        return 24
    if "256" in os.environ.get("TERM", "") or os.environ.get("TERM_PROGRAM") == "Apple_Terminal":
        return 256
    return 16


def theme() -> str:
    """`night` unless told otherwise. `COLORFGBG` is `fg;bg`, and a bg of 7 or 15
    is a light terminal; `EDIFY_THEME=day|night` overrides both."""
    chosen = os.environ.get("EDIFY_THEME", "").lower()
    if chosen in PALETTES:
        return chosen
    bg = os.environ.get("COLORFGBG", "").split(";")[-1]
    return "day" if bg in ("7", "15") else "night"


def rgb(hexcode: str) -> tuple[int, int, int]:
    return int(hexcode[1:3], 16), int(hexcode[3:5], 16), int(hexcode[5:7], 16)


def _xterm256(colour: tuple[int, int, int]) -> int:
    """The nearest cell of the xterm 6x6x6 cube."""
    steps = (0, 95, 135, 175, 215, 255)
    index = [min(range(6), key=lambda i: abs(steps[i] - v)) for v in colour]
    return 16 + 36 * index[0] + 6 * index[1] + index[2]


def fg(colour: tuple[int, int, int], bits: int | None = None) -> str:
    """The foreground escape for an exact colour, at whatever depth is available."""
    bits = bits or depth()
    if bits == 24:
        return "\033[38;2;{};{};{}m".format(*colour)
    return f"\033[38;5;{_xterm256(colour)}m"


def sgr(style: str) -> str:
    """The escape that starts `style`, or `""` for a name nobody defined."""
    style = _ALIASES.get(style, style)
    if style == "bold":
        return "\033[1m"
    palette = PALETTES[theme()]
    if style not in palette:
        return ""
    bits = depth()
    if bits == 16:
        return f"\033[{_BASIC[style]}m"
    return fg(rgb(palette[style]), bits)


def encodes(text: str, stream: Any = None) -> bool:
    """Whether `stream` can print `text` — the same probe `anim.frames_for` makes."""
    stream = stream if stream is not None else sys.stdout
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return False
    try:
        text.encode(encoding)
    except (UnicodeEncodeError, LookupError, TypeError):
        return False
    return True


def _emit(text: str, stream: Any = None) -> None:
    """One `print`, for every channel, that a cp1252 console cannot kill.

    Windows consoles still default to a code page that has no `→` and no `·`, and
    a command that did its work and then died writing the sentence about it is the
    worst of both outcomes — the ledger is saved, the exit code says failure. So an
    unencodable character degrades to a replacement rather than a traceback.
    """
    stream = stream if stream is not None else sys.stdout
    try:
        print(text, file=stream)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
        print(text.encode(encoding, "replace").decode(encoding, "replace"), file=stream)


def _colour_stream(stream: Any) -> bool:
    """A terminal on `stream`, and nothing in the environment refusing colour."""
    try:
        tty = bool(stream.isatty())
    except (AttributeError, ValueError):  # a replaced or closed stream
        return False
    return tty and os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"


def _has_terminal() -> bool:
    """A person at both ends of this invocation. The one place that is decided."""
    try:
        return bool(sys.stdin.isatty()) and bool(sys.stderr.isatty())
    except (AttributeError, ValueError):  # a replaced stdin, a closed stream
        return False


class Out:
    """The output channel for one command invocation."""

    def __init__(
        self,
        json_mode: bool = False,
        color: bool | None = None,
        quiet: bool = False,
        anim: bool = True,
    ):
        self.json_mode = json_mode
        self.quiet = quiet
        # `--no-anim`. Kept as its own attribute rather than folded into `animated`
        # so `anim.banner` — which survives a pipe and a CI log, and so cannot ask
        # `animated` — has something to read.
        self.no_anim = not anim
        # stderr is asked separately: the wordmark and the infinity paint there, and
        # `edify init > log.txt` has a terminal on stderr that should still get ink.
        # `--no-color` (an explicit False) turns off both.
        self.color_err = color is not False and not json_mode and _colour_stream(sys.stderr)
        if color is None:
            color = _colour_stream(sys.stdout)
        self.color = bool(color) and not json_mode

    # -- styling ---------------------------------------------------------

    def c(self, text: str, style: str) -> str:
        if not self.color:
            return text
        start = sgr(style)
        return f"{start}{text}{RESET}" if start else text

    @property
    def fancy(self) -> bool:
        """Colour on, and a stdout that can print a hairline. Only then do rules
        become `─` and states carry the site's marks; a pipe keeps plain ASCII."""
        return self.color and encodes("─·")

    def state(self, word: str, kind: str, width: int = 0) -> str:
        """A state word as the site sets it: `[x] ok`, `[!] degraded`, `[-] broken`.

        The mark only at a terminal, so what a pipe or a script reads is unchanged.
        `kind` is a key of `MARKS`.
        """
        style = {"pass": "signal", "uncovered": "faint"}.get(kind, kind)
        padded = word.ljust(width)
        if not self.fancy:
            return self.c(padded, style)
        return f"{self.c(MARKS[kind], style)} {self.c(padded, style)}"

    def rule(self, width: int) -> str:
        """A hairline: the only separator the identity allows."""
        return self.c(("─" if self.fancy else "-") * width, "faint")

    # -- channels --------------------------------------------------------

    def line(self, text: str = "") -> None:
        """A line of the command's actual answer. Suppressed in JSON mode."""
        if self.json_mode or self.quiet:
            return
        _emit(text)

    def note(self, text: str) -> None:
        """Context for a human. Never part of the answer, so it goes to stderr."""
        if self.quiet:
            return
        _emit(self.c(text, "dim"), sys.stderr)

    def warn(self, text: str) -> None:
        _emit(f"{self.state('warning', 'advisory')} {text}", sys.stderr)

    def error(self, text: str, hint: str | None = None) -> None:
        _emit(f"{self.state('error', 'blocked')} {text}", sys.stderr)
        if hint:
            _emit(f"        {self.c(hint, 'dim')}", sys.stderr)

    def ok(self, text: str) -> None:
        if self.quiet:
            return
        _emit(f"{self.state('ok', 'pass')} {text}", sys.stderr)

    def field(self, label: str, value: str) -> None:
        """One line of a report: the label as a readout, the value in plain ink."""
        self.line(f"{self.c(label.ljust(LABEL_WIDTH), 'muted')} {value}")

    def next(self, text: str) -> None:
        """The step after this one. The site's boot log ends on it, in blue."""
        self.line(self.c(text, "signal"))

    def data(self, payload: Any) -> None:
        """The machine-readable form of the answer. Only emitted in JSON mode."""
        if not self.json_mode:
            return
        _emit(json.dumps(payload, indent=2, sort_keys=True, default=str))

    # -- asking ----------------------------------------------------------

    @property
    def interactive(self) -> bool:
        """Whether this invocation is allowed to ask a person a question.

        A prompt that appears inside a pipeline, a CI job, or a model's tool call is
        a hang rather than a question. So it takes a terminal at both ends, human
        output, and nothing in the environment saying otherwise. Every caller has a
        defined answer for when this is false — a question is never load-bearing.
        """
        if self.json_mode or self.quiet:
            return False
        if os.environ.get("EDIFY_ASSUME_YES") or os.environ.get("EDIFY_NO_PROMPT") or os.environ.get("CI"):
            return False
        return _has_terminal()

    @property
    def animated(self) -> bool:
        """Whether this invocation is allowed to paint over its own output.

        The one place tty, `--json`, `--quiet`, `--no-anim`, `EDIFY_NO_ANIM`, `CI`
        and `TERM=dumb` are decided, so no call site invents its own rule and the
        two disagree. Sitting beside `interactive` on purpose: both answer "is
        there a person watching this happen, right now?".

        stderr specifically, because that is where the animation paints. A piped
        stdout with a terminal on stderr still animates, which is what somebody
        running `edify graph build > out.txt` wants to see.
        """
        if self.json_mode or self.quiet or self.no_anim:
            return False
        if os.environ.get("EDIFY_NO_ANIM") or os.environ.get("CI"):
            return False
        if os.environ.get("TERM") == "dumb":
            return False
        try:
            return bool(sys.stderr.isatty())
        except (AttributeError, ValueError):  # a replaced or closed stream
            return False

    def prompt_line(self, text: str = "") -> None:
        """Part of a question — a menu row, a heading. Never part of the answer."""
        if self.json_mode or self.quiet:
            return
        _emit(text, sys.stderr)

    def ask(self, question: str, default: str = "") -> str:
        """One line of input, on stderr so a pipe on stdout stays clean."""
        if not self.interactive:
            return default
        suffix = f" [{default}]" if default else ""
        print(f"{self.c(question, 'bold')}{suffix} ", end="", file=sys.stderr, flush=True)
        try:
            answer = input().strip()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return default
        return answer or default

    # -- tables ----------------------------------------------------------

    def table(self, headers: list[str], rows: list[list[str]]) -> None:
        """A plain aligned table. No box drawing — it has to survive a pipe."""
        if self.json_mode or self.quiet:
            return
        if not rows:
            return
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(str(cell)))
        head = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
        _emit(self.c(head, "muted" if self.fancy else "bold"))
        _emit("  ".join(self.rule(w) for w in widths))
        for row in rows:
            _emit("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))
