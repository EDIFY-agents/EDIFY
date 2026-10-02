"""The terminal look: the site's palette, its state marks, and the wordmark.

What matters for decoration is where it does *not* go. Every assertion that shows
the new look at a terminal has a partner that shows a pipe, `--no-color` or
`--json` getting exactly the plain text it got before.
"""

from __future__ import annotations

import io
import re
import sys

import pytest

from edify import anim, ui
from edify.cli import main
from edify.ui import Out

ESC = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class TTY(io.StringIO):
    """A terminal that prints UTF-8."""

    encoding = "utf-8"

    def isatty(self) -> bool:
        return True


def _terminal(monkeypatch: pytest.MonkeyPatch):
    """stdout and stderr both terminals, truecolor, nothing refusing colour.

    Called from inside the test body: pytest puts its own capture back on
    `sys.stdout` after fixtures run, so a fixture could not make this stick.
    """
    out, err = TTY(), TTY()
    for name in ("NO_COLOR", "CI", "EDIFY_NO_ANIM", "EDIFY_THEME", "COLORFGBG", "TERM"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("COLORTERM", "truecolor")
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    monkeypatch.setattr(anim.time, "sleep", lambda s: None)
    return out, err


# -- the palette ------------------------------------------------------------


def test_every_palette_defines_the_same_tokens() -> None:
    assert set(ui.PALETTES["night"]) == set(ui.PALETTES["day"])
    for palette in ui.PALETTES.values():
        assert all(re.fullmatch(r"#[0-9A-F]{6}", v) for v in palette.values())


def test_the_depth_follows_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("COLORTERM", "WT_SESSION", "TERM_PROGRAM", "TERM"):
        monkeypatch.delenv(name, raising=False)
    assert ui.depth() == 16
    monkeypatch.setenv("TERM", "xterm-256color")
    assert ui.depth() == 256
    monkeypatch.setenv("COLORTERM", "truecolor")
    assert ui.depth() == 24


def test_a_pass_is_blue_not_green(monkeypatch: pytest.MonkeyPatch) -> None:
    """The site's `[x] pass` is the enforced blue; `green` is kept as an alias of it."""
    monkeypatch.setenv("COLORTERM", "truecolor")
    monkeypatch.delenv("EDIFY_THEME", raising=False)
    monkeypatch.delenv("COLORFGBG", raising=False)
    assert ui.sgr("green") == ui.sgr("signal") == "\033[38;2;122;189;255m"


def test_a_light_terminal_gets_the_day_palette(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EDIFY_THEME", raising=False)
    monkeypatch.setenv("COLORFGBG", "0;15")
    assert ui.theme() == "day"
    monkeypatch.setenv("EDIFY_THEME", "night")
    assert ui.theme() == "night", "EDIFY_THEME overrides what the terminal reports"


def test_sixteen_colours_get_the_basic_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("COLORTERM", "WT_SESSION", "TERM_PROGRAM", "TERM"):
        monkeypatch.delenv(name, raising=False)
    assert ui.sgr("advisory") == "\033[33m"
    assert ui.sgr("nonsense") == ""


# -- the state device -------------------------------------------------------


def test_a_pipe_sees_the_plain_state_word(monkeypatch: pytest.MonkeyPatch) -> None:
    out = Out(color=False)
    assert out.state("ok", "pass", 9) == "ok       "
    assert out.rule(4) == "----"


def test_a_terminal_sees_the_site_s_marks(monkeypatch: pytest.MonkeyPatch) -> None:
    _terminal(monkeypatch)
    out = Out()
    assert out.fancy
    assert ESC.sub("", out.state("degraded", "advisory", 9)) == "[!] degraded "
    assert ESC.sub("", out.rule(3)) == "───"


def test_doctor_through_a_pipe_is_unchanged(installed, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--repo", str(installed), "doctor"])
    captured = capsys.readouterr().out
    assert "\033[" not in captured
    assert "[x]" not in captured and "[!]" not in captured
    assert re.search(r"^ok\s+install", captured, re.M)


def test_no_color_turns_off_stderr_colour_too(monkeypatch: pytest.MonkeyPatch) -> None:
    _terminal(monkeypatch)
    assert Out().color_err is True
    assert Out(color=False).color_err is False
    assert Out(json_mode=True).color_err is False


# -- the wordmark -----------------------------------------------------------


def test_the_wordmark_is_one_rectangle() -> None:
    assert len({len(row) for row in anim.WORDMARK}) == 1


def test_ink_never_changes_the_letters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLORTERM", "truecolor")
    for centre in (-5.0, 0.0, anim.POOL_REST, 30.0):
        for row, line in enumerate(anim.WORDMARK):
            assert ESC.sub("", anim.ink(row, line, centre, True)) == line
    assert anim.ink(0, anim.WORDMARK[0], anim.POOL_REST, False) == anim.WORDMARK[0]


def test_the_ink_comes_to_rest_inside_the_word(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLORTERM", "truecolor")
    inked = anim.ink(0, anim.WORDMARK[0], anim.POOL_REST, True)
    assert "\033[38;2;" in inked


def test_the_readout_names_the_verb_and_version() -> None:
    from edify import __version__

    line = anim.readout("init new", False)
    assert line.startswith("EDIFY / INIT NEW ") and line.endswith(__version__)
    assert len(line) == anim.READOUT_WIDTH


def test_a_terminal_gets_the_wordmark_and_a_pipe_the_ascii_banner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, err = _terminal(monkeypatch)
    anim.banner(Out(), "setup")
    painted = ESC.sub("", err.getvalue())
    assert anim.WORDMARK[0] in painted and "EDIFY / SETUP" in painted
    assert anim.BANNER[0] not in painted
    assert "\033[?25h" in err.getvalue(), "the cursor is shown again once the ink settles"

    monkeypatch.setattr(sys, "stderr", io.StringIO())
    anim.banner(Out(), "setup")
    assert anim.BANNER[0] in sys.stderr.getvalue(), "off a terminal: the ASCII banner"


def test_the_infinity_in_ink_is_the_same_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLORTERM", "truecolor")
    for i, frame in enumerate(anim.UNICODE_FRAMES[:6]):
        assert ESC.sub("", anim.inked(frame, i, True)) == frame
        assert anim.inked(frame, i, False) == frame


def test_every_frame_has_a_tone_for_its_head() -> None:
    assert len(anim.TONES) == anim.FRAMES
    assert all(0 in ages.values() for ages in anim.TONES)
