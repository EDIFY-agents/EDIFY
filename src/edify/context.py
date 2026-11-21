"""What every command receives.

One object: where the repository is, how to write output, and what this machine is
entitled to. Nothing here holds state between invocations — the CLI is a pure
function over files.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from .paths import Layout, layout
from .ui import Out

# Each of these is loaded by the first command that asks for it, not by every command:
# `edify version` has no use for the graph, and `edify graph where` none for a licence.
if TYPE_CHECKING:
    from .graph.store import GraphStore
    from .interview import Profile
    from .licensing.tier import Entitlement


@dataclass
class Context:
    args: argparse.Namespace
    layout: Layout
    out: Out
    # What the person answered when `edify init new` asked, or None when nobody was
    # asked — which is every other command, and `init new` in a pipeline. Nothing
    # reads this without checking, because a question is never load-bearing.
    profile: "Profile | None" = None

    @cached_property
    def entitlement(self) -> Entitlement:
        from .licensing.tier import current

        return current()

    @cached_property
    def store(self) -> GraphStore:
        from .graph.store import GraphStore

        return GraphStore(self.layout)

    @property
    def root(self):
        return self.layout.root


def build_context(args: argparse.Namespace) -> Context:
    return Context(
        args=args,
        layout=layout(getattr(args, "repo", None)),
        out=Out(
            json_mode=getattr(args, "json", False),
            color=False if getattr(args, "no_color", False) else None,
            quiet=getattr(args, "quiet", False),
            anim=not getattr(args, "no_anim", False),
        ),
    )
