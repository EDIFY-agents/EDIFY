"""The two failure shapes the CLI has.

`EdifyError` is a condition the user can fix — a missing graph, an unreadable
registry, a licence that does not cover a command. It prints one line and exits
non-zero. Anything else is a bug and gets a traceback, because hiding one costs
more than it saves.
"""

from __future__ import annotations

from .distribution import CONTACT


class EdifyError(Exception):
    """A condition the person running the command can do something about."""

    exit_code = 1

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class NotInstalled(EdifyError):
    """`.edify/` is absent — the repository has never been initialised."""

    exit_code = 3

    def __init__(self, root: str) -> None:
        super().__init__(
            f"no .edify/ directory under {root}",
            hint="run `edify init` in the repository root",
        )


class GraphMissing(EdifyError):
    """The graph has not been extracted yet, or was removed."""

    exit_code = 4

    def __init__(self) -> None:
        super().__init__(
            "no graph on disk",
            hint="run `edify graph build`",
        )


class TierRequired(EdifyError):
    """A team or partner licence is needed. Stated plainly, with both doors.

    There is no price and no purchase: a licence is issued on request, and this is
    the one sentence that says how to ask for one. Every refusal and every soft
    cap reuses it rather than retyping it.

    No new exit code: 7 still means "this needs a licence", and a second one would
    have to be documented in three places to buy nothing.
    """

    exit_code = 7

    def __init__(self, feature: str, plan: str = "team") -> None:
        super().__init__(
            f"{feature} needs a team or partner licence",
            hint=f"have a token? edify license activate <token>   ·   ask for one: {CONTACT}",
        )
