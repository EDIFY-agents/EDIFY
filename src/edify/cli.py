"""The `edify` binary.

A pure function over files. Every command reads files and writes files; none holds
state, opens a socket, or calls out to a network except `edify upgrade`, which
pulls a skill library, and `edify self update`, which builds a wheel and may fetch
its build backend. Both say so in their own docstrings, and both have an offline
mode that fails cleanly rather than reaching out.

Deterministic where it decides. `edify` may be invoked by a model; no `edify`
command lets a model decide what is installed, indexed, or resolved.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from . import __version__

if TYPE_CHECKING:
    import argparse

# Startup is part of the interface: an agent calls `edify graph where` dozens of times
# a task. So this module imports nothing at the top but the version, and everything
# else — argparse, the context, the command modules — when it is first needed.

USAGE = """edify — three documents and a map

lifecycle
  edify init new [PATH]               a folder from zero, for every agent — asks first
  edify setup [PATH] [--fresh]        install everything into one folder, root pinned there
  edify init [--yes] [--skills ...]   detect · extract · choose skills · write CLAUDE.md
  edify check [--fix] [--exit-code]   format check over specs, tasks, and skill files
  edify upgrade                       pull a newer skill library and re-index

graph — on a big repository: map once, context per task
  edify graph build                   full extraction, then MAP.md
  edify graph map                     communities, hubs, bridges → .edify/graph/MAP.md
  edify graph context "<task>"        the slice one task needs, under a token budget
  edify graph explain <name>          one node: community, fan-in, every edge, confidence
  edify graph path <a> <b>            how two things connect, hop by hop
  edify graph update --changed        re-extract what git says changed (or <dir>...)
  edify graph hook [--remove]         git hooks that keep the graph current
  edify graph where <name>            file:line and signature (lists: --limit N --offset K)
  edify graph dependents <symbol>     everything that breaks if this changes
  edify graph references <name>       who calls or imports this
  edify graph defines <file>          what this file exports
  edify graph overlap <a> <b>         do these file sets intersect, dependents included
  edify graph stat                    what is in the map

skills
  edify skills list                   what is installed, with provenance and license
  edify skills resolve <role> <phase> [tech]
  edify skills index                  re-sort the lookup table
  edify skills add <path>             install one entry
  edify skills sync                   mirror the library into .claude/ — skills/<name>/SKILL.md,
                                      agents/<name>.md by `kind`

harvest (EDIFY's own repository only)
  edify harvest pick [--source N]     which source to draw from, and what not to gather again
  edify harvest stage --url ... --name ... --content PATH
  edify harvest screen [ID...]        licence · duplicate · injection, fail-closed
  edify harvest propose ID --file PATH --case "..."
  edify harvest admit ID --by NAME    the human door — never unattended
  edify harvest reject ID --reason "..."
  edify harvest status                the ledger, and the yield rows for sources.md

governance
  edify governance list               every file edify installed, and where it came from
  edify governance verify             the ledger against what is on disk
  edify governance rebuild            re-baseline after a deliberate change

swarm — many agents, many people, one task list
  edify swarm board [feature]         every task: ready · leased · done · blocked
  edify swarm claim [feature]         lease the next ready task no live lease overlaps
  edify swarm prompt <task>           the whole spawn payload: skill, task, slice, servers
  edify swarm done <task>             record the done-check passed, release the lease
                                      --status partial|failed|needs_input --reason "...": a block
  edify swarm release <task>          give a lease back without finishing (another's: --force)
  edify swarm status [feature]        one line per agent: holds what, since when, expiring soon
  edify swarm merge [--apply]         done swarm/<id> branches in a safe order; --apply lands them
  (--git: leases live on origin's `edify-swarm` branch, for people on other machines)

servers
  edify mcp list                      the registry, with what each entry is scoped to
  edify mcp check                     each server responds and its version matches the pin
  edify mcp for <role> <phase>        what a spawn in this position would load
  edify mcp config <role> <phase>     write only those servers to a spawn's MCP config

ship
  edify doctor                        does the install work here
  edify self where                    which edify is this, and where did it come from
  edify self update [--from PATH]     put an edited checkout behind the `edify` binary
  edify license status|activate|deactivate
  edify feedback [list|show|off|on]   four questions, written to a file on this machine
  edify version
"""


def _lazy(module: str, fn: str):
    """A handler that imports its command module only when it runs."""

    def handler(ctx):
        import importlib

        return getattr(importlib.import_module(f".commands.{module}", __package__), fn)(ctx)

    handler.__qualname__ = handler.__name__ = f"{module}.{fn}"
    return handler


class _Skip:
    """Stands in for the parser of a command argv does not name: accepts every
    `add_argument`, `add_parser` and `set_defaults` and builds nothing."""

    def __getattr__(self, name: str):
        return self._ignore

    def _ignore(self, *args, **kwargs):
        return self


_SKIP = _Skip()

#: The global options, so `_command_of` can step over them to the command.
_GLOBAL_FLAGS = frozenset(("--json", "--no-color", "--quiet", "-q", "--no-anim"))


def _command_of(argv: list[str]) -> str | None:
    """The command argv names, when that is certain from the tokens alone.

    `None` — build the whole parser — for anything else: no command, `-h` or
    `--version` before one, an abbreviated or unknown option. Only then does
    `--help`, or an error listing every choice, need every command.
    """
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--repo":
            i += 2
        elif token.startswith("--repo=") or token in _GLOBAL_FLAGS:
            i += 1
        elif token.startswith("-"):
            return None
        else:
            return token
    return None


def build_parser(only: str | None = None) -> argparse.ArgumentParser:
    """The whole command line — or, given `only`, the global options and that one
    command, which parses that command's argv identically at an eighth of the cost.
    An `only` that names no command gets the whole parser."""
    import argparse

    # Read from the table rather than typed out, so help text and behaviour cannot drift.
    from .agents import ALL_IDS

    _AGENT_IDS = ", ".join(ALL_IDS)

    class Parser(argparse.ArgumentParser):
        """argparse, except a usage error read by an agent is one line and a hint —
        not the whole usage block, which costs tokens and says nothing new. Exit 2,
        as argparse has always exited. Subparsers inherit the class."""

        def error(self, message: str):  # type: ignore[override]
            from .ui import agent_mode

            if not agent_mode():
                super().error(message)
            self.exit(2, f"error: {message}\nhint: `{self.prog} --help` lists what it takes\n")

    parser = Parser(
        prog="edify",
        description="A harness that makes an AI coding agent work reliably on large codebases.",
    )
    parser.add_argument("--repo", metavar="PATH", help="the repository root (default: search upward from cwd)")
    parser.add_argument("--json", action="store_true", help="machine-readable output on stdout")
    parser.add_argument("--no-color", action="store_true", help="never emit ANSI colour")
    parser.add_argument("--quiet", "-q", action="store_true", help="answers only, no notes")
    parser.add_argument("--no-anim", action="store_true",
                        help="no banner and no animation; static lines instead")
    parser.add_argument("--version", action="version", version=f"edify {__version__}")

    class Commands(argparse._SubParsersAction):
        def add_parser(self, name, **kwargs):
            if only is not None and name != only:
                return _SKIP
            return super().add_parser(name, **kwargs)

    sub = parser.add_subparsers(dest="command", action=Commands)

    # -- lifecycle -------------------------------------------------------
    # `setup` takes the same flags as `init` because it *is* `init` with the root
    # pinned to one folder and force on. Anything accepted by one is accepted by both.
    p_setup = sub.add_parser("setup", help="install everything into one folder, root pinned there")
    p_setup.add_argument("path", nargs="?", default=".", help="the folder to install into (created if missing)")
    p_setup.add_argument("--fresh", action="store_true",
                         help="remove edify's own files first — .edify/, its host pointers, its CLAUDE.md block")
    p_setup.add_argument("--stack", default="auto", help="`auto`, or explicit tech ids to add to what was detected")
    p_setup.add_argument("--no-graph", action="store_true", help="skip extraction (run `edify graph build` later)")
    p_setup.add_argument("--extractor", default="builtin", choices=("builtin", "ctags"))
    p_setup.add_argument("--host", default="claude", choices=("claude", "none"),
                         help="write the host runtime's command and skill pointers")
    p_setup.add_argument("--agents", default="", metavar="all|none|IDS",
                         help=f"which agent runtimes to write files for ({_AGENT_IDS}); default: --host")
    p_setup.add_argument("--skills", default="all", metavar="ask|all|none|NAMES",
                         help="which library entries to install (default: all — setup means everything)")
    p_setup.add_argument("--yes", "-y", action="store_true", help="take every default answer, ask nothing")
    p_setup.add_argument("--force", action="store_true", help="implied — setup always installs over its own files")
    p_setup.set_defaults(func=_lazy("setup_cmd", "run"))

    p_init = sub.add_parser("init", help="install the harness into this repository")
    p_init.add_argument("--stack", default="auto", help="`auto`, or explicit tech ids to add to what was detected")
    p_init.add_argument("--force", action="store_true", help="overwrite files init would otherwise keep")
    p_init.add_argument("--no-graph", action="store_true", help="skip extraction (run `edify graph build` later)")
    p_init.add_argument("--extractor", default="builtin", choices=("builtin", "ctags"))
    p_init.add_argument("--host", default="claude", choices=("claude", "none"),
                        help="write thin command pointers for a host runtime")
    p_init.add_argument("--skills", default="auto", metavar="ask|all|none|NAMES",
                        help="which library entries to install (default: ask when there is a terminal)")
    p_init.add_argument("--yes", "-y", action="store_true",
                        help="take every default answer — install the whole matched set, ask nothing")
    p_init.add_argument("--agents", default="", metavar="all|none|IDS",
                        help=f"which agent runtimes to write files for ({_AGENT_IDS}); default: --host")
    p_init.set_defaults(func=_lazy("init_cmd", "run"))

    # `init new` — the from-nothing install. It is a subcommand of `init` rather than
    # a command of its own because it is the same install: one root, every runtime,
    # and the questions detection cannot answer.
    init_sub = p_init.add_subparsers(dest="init_command")
    p_new = init_sub.add_parser(
        "new", help="set a folder up from zero, for every agent, after asking what it is for"
    )
    p_new.add_argument("path", nargs="?", default=".", help="the folder to install into (created if missing)")
    p_new.add_argument("--agents", default="all", metavar="all|none|IDS",
                       help=f"which agent runtimes to write files for ({_AGENT_IDS})")
    p_new.add_argument("--stack", default="auto", help="`auto`, or explicit tech ids to add to what was detected")
    p_new.add_argument("--skills", default="all", metavar="ask|all|none|NAMES",
                       help="which library entries to install (default: all — `new` means everything)")
    p_new.add_argument("--no-interview", action="store_true",
                       help="install without asking anything; keeps an existing .edify/profile.md")
    p_new.add_argument("--keep", action="store_true",
                       help="do not clear edify's own files first — reinstall over what is there")
    p_new.add_argument("--no-graph", action="store_true", help="skip extraction (run `edify graph build` later)")
    p_new.add_argument("--extractor", default="builtin", choices=("builtin", "ctags"))
    p_new.add_argument("--host", default="claude", choices=("claude", "none"),
                       help="kept for symmetry with `init`; `--agents` is what decides here")
    p_new.add_argument("--yes", "-y", action="store_true", help="take every default answer, ask nothing")
    p_new.add_argument("--force", action="store_true", help="implied — `new` always installs over its own files")
    p_new.set_defaults(func=_lazy("init_new_cmd", "run"))

    p_check = sub.add_parser("check", help="report what is wrong with the documents")
    p_check.add_argument("--fix", action="store_true", help="apply the mechanical repairs only")
    p_check.add_argument("--exit-code", action="store_true", help="exit non-zero when there are errors (for CI)")
    p_check.add_argument("--strict", action="store_true", help="with --exit-code, treat warnings as errors")
    p_check.set_defaults(func=_lazy("check_cmd", "run"))

    p_upgrade = sub.add_parser("upgrade", help="pull a newer skill library and re-index")
    p_upgrade.add_argument("--channel", default="stable")
    p_upgrade.add_argument("--archive", metavar="PATH", help="install from a local archive instead of the network")
    p_upgrade.add_argument("--check", action="store_true", help="report what is available and change nothing")
    p_upgrade.add_argument("--skills", default="auto", metavar="ask|all|none|NAMES",
                           help="which entries in the archive to install (default: ask when there is a terminal)")
    p_upgrade.add_argument("--yes", "-y", action="store_true", help="install every valid entry, ask nothing")
    p_upgrade.set_defaults(func=_lazy("upgrade_cmd", "run"))

    # -- graph -----------------------------------------------------------
    p_graph = sub.add_parser("graph", help="build and query the map")

    def _paged(parser, default):
        what = "connected nodes" if default is None else "hits"
        parser.add_argument("--limit", type=int, default=default,
                            help=f"{what} per page (default {default or 'the budget'}; 0: all)")
        parser.add_argument("--offset", type=int, default=0, help="skip this many first")

    graph_sub = p_graph.add_subparsers(dest="graph_command")

    g_build = graph_sub.add_parser("build", help="full extraction")
    g_build.add_argument("--extractor", default="builtin", choices=("builtin", "ctags"))
    g_build.set_defaults(func=_graph_build)

    g_update = graph_sub.add_parser("update", help="re-extract one or more directories")
    g_update.add_argument("dirs", nargs="*")
    g_update.add_argument("--changed", action="store_true", help="re-extract what changed since the graph's commit")
    g_update.add_argument("--extractor", default="builtin", choices=("builtin", "ctags"))
    g_update.set_defaults(func=_graph_update)

    g_where = graph_sub.add_parser("where", help="file:line and kind for a name")
    g_where.add_argument("name")
    g_where.add_argument("--kind", choices=("file", "module", "symbol", "route", "table", "package", "doc-section"))
    _paged(g_where, 50)
    g_where.set_defaults(func=_graph_where)

    g_dep = graph_sub.add_parser("dependents", help="everything that breaks if this changes")
    g_dep.add_argument("symbol")
    g_dep.add_argument("--depth", type=int, default=1)
    _paged(g_dep, 50)
    g_dep.set_defaults(func=_graph_dependents)

    g_ref = graph_sub.add_parser("references", help="who calls or imports this")
    g_ref.add_argument("name")
    _paged(g_ref, 50)
    g_ref.set_defaults(func=_graph_references)

    g_def = graph_sub.add_parser("defines", help="what this file exports")
    g_def.add_argument("file")
    _paged(g_def, 50)
    g_def.set_defaults(func=_graph_defines)

    g_ov = graph_sub.add_parser("overlap", help="do these two file sets intersect")
    g_ov.add_argument("a")
    g_ov.add_argument("b")
    g_ov.add_argument("--depth", type=int, default=1)
    g_ov.set_defaults(func=_graph_overlap)

    g_stat = graph_sub.add_parser("stat", help="what is in the map")
    g_stat.set_defaults(func=_graph_stat)

    g_map = graph_sub.add_parser("map", help="communities, hubs and bridges → .edify/graph/MAP.md")
    g_map.set_defaults(func=_lazy("graph_cmd", "map_"))

    g_ctx = graph_sub.add_parser("context", help="the slice of the graph one task needs")
    g_ctx.add_argument("query", nargs="+")
    g_ctx.add_argument("--budget", type=int, default=2000, help="tokens, roughly (default 2000)")
    g_ctx.add_argument("--depth", type=int, default=1)
    _paged(g_ctx, None)
    g_ctx.set_defaults(func=_lazy("graph_cmd", "context"))

    g_exp = graph_sub.add_parser("explain", help="one node, its community, and every edge")
    g_exp.add_argument("name", help="a name, or file::name to pin one")
    _paged(g_exp, 25)
    g_exp.set_defaults(func=_lazy("graph_cmd", "explain"))

    g_path = graph_sub.add_parser("path", help="the shortest path between two nodes")
    g_path.add_argument("a")
    g_path.add_argument("b")
    g_path.add_argument("--max-hops", type=int, default=8)
    g_path.set_defaults(func=_lazy("graph_cmd", "path"))

    g_hook = graph_sub.add_parser("hook", help="git hooks that keep the graph current")
    g_hook.add_argument("--remove", action="store_true")
    g_hook.set_defaults(func=_lazy("graph_cmd", "hook"))

    # -- swarm -----------------------------------------------------------
    p_swarm = sub.add_parser("swarm", help="lease tasks to many agents and people at once")
    p_swarm.add_argument("--git", action="store_true", help="keep leases on origin's edify-swarm branch")
    swarm_sub = p_swarm.add_subparsers(dest="swarm_command")

    w_board = swarm_sub.add_parser("board", help="every task and its state")
    w_board.add_argument("feature", nargs="?")
    w_board.set_defaults(func=_lazy("swarm_cmd", "board"))

    w_claim = swarm_sub.add_parser("claim", help="lease the next ready, non-overlapping task")
    w_claim.add_argument("feature", nargs="?")
    w_claim.add_argument("--agent", default="", help="who holds the lease (default: $EDIFY_AGENT, user@host)")
    w_claim.add_argument("--task", default="", help="claim this task id rather than the next ready one")
    w_claim.add_argument("--ttl", type=int, default=120, help="minutes before an unrenewed lease expires")
    w_claim.add_argument("--worktree", action="store_true", help="also create a git worktree on swarm/<task>")
    w_claim.set_defaults(func=_lazy("swarm_cmd", "claim"))

    w_prompt = swarm_sub.add_parser("prompt", help="the full spawn payload for one task")
    w_prompt.add_argument("task")
    w_prompt.add_argument("feature", nargs="?")
    w_prompt.add_argument("--budget", type=int, default=1500)
    w_prompt.set_defaults(func=_lazy("swarm_cmd", "prompt"))

    for name, fn, text in (
        ("done", "done", "record a hand-back: completed is a done, anything else a block"),
        ("release", "release", "give a lease back unfinished"),
        ("renew", "renew", "extend a lease you hold"),
        ("block", "block", "mark a task blocked, with the reason"),
    ):
        w = swarm_sub.add_parser(name, help=text)
        w.add_argument("task")
        w.add_argument("feature", nargs="?")
        w.add_argument("--agent", default="")
        w.add_argument("--reason", default="")
        w.add_argument("--ttl", type=int, default=120)
        if name == "done":
            w.add_argument("--status", default="completed", choices=("completed", "partial", "failed", "needs_input"),
                           help="the typed hand-back; anything but completed records a block")
        if name in ("release", "block"):
            w.add_argument("--force", action="store_true", help="act on a live lease another agent holds")
        w.set_defaults(func=_lazy("swarm_cmd", fn))

    w_status = swarm_sub.add_parser("status", help="one line per agent: what it holds, since when, expiry")
    w_status.add_argument("feature", nargs="?")
    w_status.add_argument("--soon", type=int, default=15, help="minutes left that count as expiring")
    w_status.set_defaults(func=_lazy("swarm_cmd", "status"))

    w_merge = swarm_sub.add_parser("merge", help="done tasks' swarm/<id> branches in a safe merge order")
    w_merge.add_argument("feature", nargs="?")
    w_merge.add_argument("--apply", action="store_true", help="git merge --no-ff each, stopping at the first conflict")
    w_merge.set_defaults(func=_lazy("swarm_cmd", "merge"))

    # -- skills ----------------------------------------------------------
    p_skills = sub.add_parser("skills", help="the installed library and the spawn lookup")
    skills_sub = p_skills.add_subparsers(dest="skills_command")

    s_list = skills_sub.add_parser("list", help="what is installed, with provenance and licence")
    s_list.set_defaults(func=_lazy("skills_cmd", "list_"))

    s_resolve = skills_sub.add_parser("resolve", help="the one file a spawn in this position loads")
    s_resolve.add_argument("role")
    s_resolve.add_argument("phase")
    s_resolve.add_argument("tech", nargs="?")
    s_resolve.set_defaults(func=_lazy("skills_cmd", "resolve"))

    s_index = skills_sub.add_parser("index", help="re-sort the lookup table")
    s_index.set_defaults(func=_lazy("skills_cmd", "index"))

    s_add = skills_sub.add_parser("add", help="install one entry from a local file")
    s_add.add_argument("path")
    s_add.set_defaults(func=_lazy("skills_cmd", "add"))

    s_sync = skills_sub.add_parser("sync", help="mirror the library into each runtime's skill directory")
    s_sync.add_argument("--host", default="claude", choices=("claude", "none"))
    s_sync.add_argument("--agents", default="", metavar="all|none|IDS",
                        help=f"which agent runtimes to mirror into ({_AGENT_IDS}); default: the ones set up here")
    s_sync.set_defaults(func=_lazy("skills_cmd", "sync"))

    # -- harvest ---------------------------------------------------------
    # Four steps that run unattended and one that never does.
    p_harvest = sub.add_parser("harvest", help="turn a public capability into a library entry")
    harvest_sub = p_harvest.add_subparsers(dest="harvest_command")

    h_pick = harvest_sub.add_parser("pick", help="which source to draw from, and what not to gather again")
    h_pick.add_argument("--count", type=int, default=5, help="how many new candidates this run is aiming for")
    h_pick.add_argument("--source", default="", metavar="NAME",
                        help="draw from this row instead of the best-scoring one")
    h_pick.add_argument("--all", action="store_true", help="print every row with its score, not just the choice")
    h_pick.set_defaults(func=_lazy("harvest_cmd", "pick"))

    h_stage = harvest_sub.add_parser("stage", help="record one gathered artifact, or refuse a repeat")
    h_stage.add_argument("--url", required=True, help="where it came from")
    h_stage.add_argument("--name", required=True, help="the entry name it would take, [a-z0-9-]+")
    h_stage.add_argument("--content", required=True, metavar="PATH", help="the raw bytes, already on disk")
    h_stage.add_argument("--commit", default="", help="the commit hash it was read at")
    h_stage.add_argument("--license", default="", help="the licence as found, or nothing — which means NONE-FOUND")
    h_stage.add_argument("--source", default="", help="which row of sources.md this came from")
    h_stage.set_defaults(func=_lazy("harvest_cmd", "stage"))

    h_screen = harvest_sub.add_parser("screen", help="licence, duplicate, injection — mechanical and fail-closed")
    h_screen.add_argument("ids", nargs="*", help="candidates to screen (default: everything staged)")
    h_screen.set_defaults(func=_lazy("harvest_cmd", "screen"))

    h_propose = harvest_sub.add_parser("propose", help="present a rewrite for admission")
    h_propose.add_argument("id")
    h_propose.add_argument("--file", required=True, metavar="PATH", help="the rewritten entry")
    h_propose.add_argument("--case", required=True, help="one line: the scenario nothing in the library serves")
    h_propose.set_defaults(func=_lazy("harvest_cmd", "propose"))

    h_admit = harvest_sub.add_parser("admit", help="a person read it and says yes")
    h_admit.add_argument("id")
    h_admit.add_argument("--by", required=True, help="who read it")
    h_admit.set_defaults(func=_lazy("harvest_cmd", "admit"))

    h_reject = harvest_sub.add_parser("reject", help="a person read it and says no")
    h_reject.add_argument("id")
    h_reject.add_argument("--reason", required=True, help="why — this is what makes the next run cheap")
    h_reject.add_argument("--by", default="", help="who read it")
    h_reject.set_defaults(func=_lazy("harvest_cmd", "reject"))

    h_status = harvest_sub.add_parser("status", help="the ledger, by state and by source")
    h_status.set_defaults(func=_lazy("harvest_cmd", "status"))

    # -- governance ------------------------------------------------------
    p_gov = sub.add_parser("governance", help="what edify installed here, and whether it is unchanged")
    gov_sub = p_gov.add_subparsers(dest="governance_command")

    v_list = gov_sub.add_parser("list", help="every governed file, with origin and licence")
    v_list.set_defaults(func=_lazy("governance_cmd", "list_"))

    v_verify = gov_sub.add_parser("verify", help="the ledger against what is on disk")
    v_verify.add_argument("--exit-code", action="store_true",
                          help="exit non-zero when a governed file is missing, modified, or unrecorded")
    v_verify.set_defaults(func=_lazy("governance_cmd", "verify"))

    v_rebuild = gov_sub.add_parser("rebuild", help="re-baseline the ledger after a deliberate change")
    v_rebuild.set_defaults(func=_lazy("governance_cmd", "rebuild"))

    # -- mcp -------------------------------------------------------------
    p_mcp = sub.add_parser("mcp", help="the server registry")
    mcp_sub = p_mcp.add_subparsers(dest="mcp_command")

    m_list = mcp_sub.add_parser("list", help="the registry, with what each entry is scoped to")
    m_list.set_defaults(func=_lazy("mcp_cmd", "list_"))

    m_check = mcp_sub.add_parser("check", help="each server responds and its version matches the pin")
    m_check.set_defaults(func=_lazy("mcp_cmd", "check"))

    m_for = mcp_sub.add_parser("for", help="what a spawn in this position would load")
    m_for.add_argument("role")
    m_for.add_argument("phase")
    m_for.set_defaults(func=_lazy("mcp_cmd", "for_"))

    m_cfg = mcp_sub.add_parser("config", help="write only the servers this spawn needs to an MCP config")
    m_cfg.add_argument("role")
    m_cfg.add_argument("phase")
    m_cfg.add_argument("--out", default="", help="where to write (default .edify/run/mcp-<role>-<phase>.json)")
    m_cfg.set_defaults(func=_lazy("mcp_cmd", "config"))

    # -- ship ------------------------------------------------------------
    p_doctor = sub.add_parser("doctor", help="does the install work here")
    p_doctor.set_defaults(func=_lazy("doctor_cmd", "run"))

    # `self` is the binary talking about itself. Not `upgrade`, which pulls a newer
    # skill library — two different things, kept under two names on purpose.
    p_self = sub.add_parser("self", help="the `edify` binary itself: where it is, and updating it")
    self_sub = p_self.add_subparsers(dest="self_command")

    sf_where = self_sub.add_parser("where", help="which edify is this, and where did it come from")
    sf_where.set_defaults(func=_lazy("self_cmd", "where"))

    sf_update = self_sub.add_parser("update", help="reinstall the CLI from a source checkout")
    sf_update.add_argument("--from", dest="from_path", metavar="PATH",
                           help="the checkout to install from (default: the one this code came from)")
    sf_update.add_argument("--manager", default="", choices=("", "uv", "pipx", "pip"),
                           help="override the detected installer; `edify self where` prints what was detected")
    sf_update.add_argument("--editable", action="store_true",
                           help="install in place, so later edits need no reinstall")
    sf_update.add_argument("--offline", action="store_true",
                           help="never reach the network; fails cleanly when the build backend is not cached")
    sf_update.add_argument("--dry-run", action="store_true",
                           help="print the install command and change nothing")
    sf_update.set_defaults(func=_lazy("self_cmd", "update"))

    p_license = sub.add_parser("license", help="what this machine is entitled to")
    license_sub = p_license.add_subparsers(dest="license_command")
    l_status = license_sub.add_parser("status", help="plan, entitlements, and limits")
    l_status.set_defaults(func=_lazy("license_cmd", "status"))
    l_activate = license_sub.add_parser("activate", help="install a licence token")
    l_activate.add_argument("token", help="the token itself, or a path to a file containing it")
    l_activate.set_defaults(func=_lazy("license_cmd", "activate"))
    l_deactivate = license_sub.add_parser("deactivate", help="remove the licence from this machine")
    l_deactivate.set_defaults(func=_lazy("license_cmd", "deactivate"))

    p_feedback = sub.add_parser("feedback", help="how this is going — written to a file on this machine")
    p_feedback.add_argument("--message", "-m", help="one line instead of the four questions")
    p_feedback.set_defaults(func=_lazy("feedback_cmd", "new"))
    feedback_sub = p_feedback.add_subparsers(dest="feedback_command")
    f_list = feedback_sub.add_parser("list", help="what you have written, and where it is")
    f_list.set_defaults(func=_lazy("feedback_cmd", "list_"))
    f_show = feedback_sub.add_parser("show", help="print one entry")
    f_show.add_argument("which", nargs="?", help="the entry's number (default: the last one)")
    f_show.set_defaults(func=_lazy("feedback_cmd", "show"))
    f_off = feedback_sub.add_parser("off", help="never show the invitation again")
    f_off.set_defaults(func=_lazy("feedback_cmd", "off"))
    f_on = feedback_sub.add_parser("on", help="show the invitation again")
    f_on.set_defaults(func=_lazy("feedback_cmd", "on"))

    p_version = sub.add_parser("version", help="print the version")
    p_version.set_defaults(func=_version)

    if only is not None and only not in sub.choices:
        return build_parser()  # not a command: argparse's error should list them all
    return parser


# -- dispatch ---------------------------------------------------------------
# The graph block's handlers, by name. Kept as aliases so that block's parser lines
# stay exactly as they are; each one imports `graph_cmd` only when it runs.
_graph_build = _lazy("graph_cmd", "build")
_graph_update = _lazy("graph_cmd", "update")
_graph_where = _lazy("graph_cmd", "where")
_graph_dependents = _lazy("graph_cmd", "dependents")
_graph_references = _lazy("graph_cmd", "references")
_graph_defines = _lazy("graph_cmd", "defines")
_graph_overlap = _lazy("graph_cmd", "overlap")
_graph_stat = _lazy("graph_cmd", "stat")


def _version(ctx):
    ctx.out.data({"version": __version__})
    ctx.out.line(f"edify {__version__}")
    return 0


# ---------------------------------------------------------------------------


def _invite(ctx, args) -> None:
    """The one line asking how this is going, printed as the CLI opens.

    Silent unless there is a real terminal, and at most once per released version.
    It never asks anything here — a command that stops to interview you before doing
    what you typed is a command people learn to avoid.
    """
    # `interactive` is the first thing `maybe_invite` asks; asking it here as well
    # keeps every pipeline, CI job and agent from importing `feedback` at all.
    if getattr(args, "command", None) == "feedback" or not ctx.out.interactive:
        return
    from . import feedback

    try:
        feedback.maybe_invite(ctx.out)
    except OSError:
        pass  # a feedback prompt is never a reason for a command to fail


#: Families that print their own help when named with no subcommand.
_FAMILIES = ("graph", "swarm", "skills", "harvest", "governance", "mcp", "license", "self")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # The question scripts ask most, answered before argparse is even imported. Same
    # bytes and same exit as the full path: argparse's version action exits 0.
    if argv == ["--version"]:
        print(f"edify {__version__}")
        raise SystemExit(0)
    # `edify version` takes the same shortcut except at a real terminal, where the
    # full path runs so the once-per-version feedback invite can still appear.
    if argv == ["version"] and not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(f"edify {__version__}")
        return 0

    parser = build_parser(_command_of(argv))
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        # A family named with no subcommand prints that family's help — more useful
        # than the top-level usage — and exits 2: nothing ran, and a script or an
        # agent has to be able to tell that apart from success.
        if getattr(args, "command", None) in _FAMILIES:
            try:
                parser.parse_args([args.command, "--help"])
            except SystemExit:
                pass
            return 2
        print(USAGE)
        return 0 if getattr(args, "command", None) is None else 2

    from .context import build_context
    from .errors import EXIT_INTERRUPTED, EdifyError

    ctx = build_context(args)
    _invite(ctx, args)
    try:
        return args.func(ctx) or 0
    except EdifyError as exc:
        ctx.out.fail(exc.message, exc.hint, exc.exit_code)
        return exc.exit_code
    except KeyboardInterrupt:
        ctx.out.error("interrupted")
        return EXIT_INTERRUPTED
    except BrokenPipeError:
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
