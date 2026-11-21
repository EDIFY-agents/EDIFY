"""`edify doctor` — does the install work here.

A row per check and a green/amber/red line, where amber means "this works but
degraded, and here is which part". Every check reads files; git is asked at most
twice (HEAD and the hooks directory in one call, the ignore rule in another), so the
whole thing stays fast on a large repository.

The rows that only mean something in a git repository — graph hooks, `.edify/run/`
ignored — are left out of one that is not, rather than reported as amber.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .. import __version__, agents, assets, governance, host, skills as skills_index
from ..commands.init_cmd import _instruction_body
from ..context import Context
from ..detect import detect
from ..formats import mcp as mcp_format
from ..formats import skill as skill_format
from ..graph.langs import ctags

GREEN, AMBER, RED = "ok", "degraded", "broken"


@dataclass
class Check:
    name: str
    state: str
    detail: str


#: What `edify graph hook` writes, and the line it puts in each (`graph_cmd._HOOK`).
GRAPH_HOOKS = ("post-commit", "post-merge", "post-checkout", "post-rewrite")
GRAPH_HOOK_MARKER = "edify:graph-hook"


def run(ctx: Context) -> int:
    vcs = _Vcs.probe(ctx.layout.root)
    entries = skill_format.load_all(ctx.layout.skills_dir, ctx.layout.root)
    checks = [
        _install(ctx),
        _extractor(ctx),
        _graph(ctx, vcs),
        _hooks(vcs),
        _index(ctx, entries),
        _mirror(ctx, entries),
        _mcp_json(ctx),
        _run_ignored(ctx, vcs),
        _governance(ctx),
        _claude(ctx),
        _license(ctx),
    ]
    checks = [c for c in checks if c is not None]
    ctx.out.data([c.__dict__ for c in checks])

    for check in checks:
        kind = {GREEN: "pass", AMBER: "advisory", RED: "blocked"}[check.state]
        ctx.out.line(f"{ctx.out.state(check.state, kind, 9)} {check.name.ljust(12)} {check.detail}")

    ctx.out.line("")
    if any(c.state == RED for c in checks):
        ctx.out.line(ctx.out.c("red — something here does not work", "blocked"))
        return 1
    if any(c.state == AMBER for c in checks):
        ctx.out.line(ctx.out.c("amber — this works, degraded, in the places named above", "advisory"))
        return 0
    ctx.out.line(ctx.out.c("green", "signal"))
    return 0


# ---------------------------------------------------------------------------


def _install(ctx: Context) -> Check:
    if not ctx.layout.installed():
        return Check("install", RED, f"no .edify/ under {ctx.layout.root} — run `edify init`")
    try:
        root = assets.asset_root()
    except Exception as exc:  # the methodology tree is missing from the install
        return Check("install", RED, str(exc))
    count = len(list((root / "skills").glob("*.md")))
    return Check("install", GREEN, f"edify {__version__} · library of {count} skill entries")


def _extractor(ctx: Context) -> Check:
    external = ctags.available()
    if external:
        return Check("extractor", GREEN, f"{ctags.version()} · syntax-tree parsing")
    return Check(
        "extractor",
        AMBER,
        "built-in backend: Python is parsed exactly, everything else is scanned"
        " — install Universal Ctags for parse-grade precision on the rest",
    )


def _graph(ctx: Context, vcs: _Vcs) -> Check:
    if not ctx.store.exists():
        return Check("graph", RED, "no graph on disk — run `edify graph build`")
    problems = ctx.store.verify_checksums()
    if problems:
        return Check("graph", RED, problems[0])

    meta = ctx.store.meta
    detail = f"{meta.get('nodes', '?')} nodes · {meta.get('edges', '?')} edges"
    uncovered = meta.get("languages_uncovered", "-")
    if uncovered not in ("-", ""):
        detail += f" · no nodes for {uncovered}"
    if meta.get("truncated_at"):
        return Check("graph", AMBER, detail + f" · truncated at {meta['truncated_at']} (free plan)")

    recorded = meta.get("commit", "-")
    if vcs.head and recorded not in ("-", "") and vcs.head != recorded:
        return Check(
            "graph",
            AMBER,
            detail + f" · built at {recorded[:8]}, HEAD is {vcs.head[:8]}"
            " — `edify graph update --changed` re-extracts only what moved",
        )
    if uncovered not in ("-", ""):
        return Check("graph", AMBER, detail)
    return Check("graph", GREEN, detail)


def _hooks(vcs: _Vcs) -> Check | None:
    """The hooks that keep the graph current between builds."""
    if vcs.hooks is None:
        return None
    ours, missing = [], []
    for name in GRAPH_HOOKS:
        text = _read(vcs.hooks / name)
        # A hook somebody already had, with the update line added by hand, counts:
        # `edify graph hook` tells them to do exactly that rather than overwrite it.
        (ours if GRAPH_HOOK_MARKER in text or "edify graph update" in text else missing).append(name)
    if not ours:
        return Check(
            "graph hooks", AMBER,
            "none — `edify graph hook` keeps the graph current after each commit, merge and checkout",
        )
    if missing:
        return Check("graph hooks", AMBER, f"missing {', '.join(missing)} — run `edify graph hook`")
    return Check("graph hooks", GREEN, ", ".join(ours) + " refresh the graph")


def _index(ctx: Context, entries: list) -> Check:
    if not entries:
        return Check("skills", RED, "no skills installed — run `edify init`")
    if not ctx.layout.skills_index.is_file():
        return Check("skills", RED, "no index.tsv — run `edify skills index`")

    roles = {s.role for s in entries if s.role}
    unresolvable = []
    for role in sorted(roles):
        try:
            skills_index.resolve(ctx.layout, role, "3")
        except Exception:
            unresolvable.append(role)
    if unresolvable:
        return Check("skills", RED, "these roles do not resolve: " + ", ".join(unresolvable))

    over = [s.rel for s in entries if s.over_budget]
    if over:
        return Check("skills", AMBER, f"{len(entries)} entries · over budget: {', '.join(over[:3])}")
    return Check("skills", GREEN, f"{len(entries)} entries · every role resolves")


def _mirror(ctx: Context, entries: list) -> Check | None:
    """Every installed entry has its pointer in each runtime set up here, and no
    pointer is left standing for an entry that is gone."""
    if not entries:
        return None  # `skills` is already red, and says why
    targets = [t for t in agents.present_targets(ctx.layout.root) if t.skills or t.agents]
    if not targets:
        return Check(
            "skill mirror", GREEN,
            "no runtime skill directory here — the library is read through `edify skills resolve`",
        )
    missing = outdated = expected = 0
    for target in targets:
        for path, body, _kind, _name in host.library_pointers(ctx.layout, target, entries):
            expected += 1
            text = _read(path)
            if not text:
                missing += 1
            elif text != body and host.written_by_edify(path):
                outdated += 1
    stale = host.stale(ctx.layout, entries)
    dirs = ", ".join(sorted({d for t in targets for d in (t.skills, t.agents) if d}))
    problems = []
    if missing:
        problems.append(f"{missing} of {expected} not mirrored")
    if outdated:
        problems.append(f"{outdated} out of date")
    if stale:
        problems.append(f"{len(stale)} stale ({ctx.layout.rel(stale[0])})")
    if problems:
        return Check("skill mirror", AMBER, " · ".join(problems) + f" in {dirs} — run `edify skills sync`")
    return Check("skill mirror", GREEN, f"{expected} pointers in {dirs} · each current")


def _mcp_json(ctx: Context) -> Check:
    """A server in the project's `.mcp.json` loads into every session, which undoes
    the scoping the registry exists for."""
    path = ctx.layout.root / ".mcp.json"
    if not path.is_file():
        return Check(".mcp.json", GREEN, "none in the project — no server loads into every session")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers") or data.get("servers") or {}
    except (OSError, UnicodeDecodeError, ValueError, AttributeError):
        return Check(".mcp.json", AMBER, "not a readable JSON object — the runtime will reject it too")
    if not isinstance(servers, dict):
        servers = {}
    registry = mcp_format.parse(ctx.layout.mcp)
    scoped = []
    for name in servers:
        entry = registry.get(name)
        if entry is not None and not ("any" in entry.roles and "any" in entry.phases):
            scoped.append(name)
    if scoped:
        return Check(
            ".mcp.json",
            AMBER,
            f"loads {', '.join(scoped)} into every session though the registry scopes "
            + ("it" if len(scoped) == 1 else "them")
            + " — move the definitions to .edify/mcp.pool.json and spawn with `edify mcp config <role> <phase>`",
        )
    return Check(".mcp.json", GREEN, f"{len(servers)} server(s), none of them scoped by the registry")


def _run_ignored(ctx: Context, vcs: _Vcs) -> Check | None:
    """`.edify/run/` holds leases and per-spawn MCP configs: machine state, never history."""
    ignored = vcs.ignored(".edify/run/probe")
    if ignored is None:
        return None
    if ignored:
        return Check(".edify/run", GREEN, "ignored by the repository")
    if not (ctx.layout.edify / "run").is_dir():
        return Check(".edify/run", GREEN, "not created yet — add `.edify/run/` to .gitignore before it is")
    return Check(
        ".edify/run", AMBER,
        "not ignored — leases and spawn configs would be committed; add `.edify/run/` to .gitignore",
    )


def _governance(ctx: Context) -> Check:
    """Amber, never red. A ledger that disagrees with the disk is information."""
    if not ctx.layout.governance.is_file():
        return Check("governance", AMBER, "no ledger — run `edify governance rebuild`")
    try:
        recorded = governance.load(ctx.layout)
        problems = governance.verify(ctx.layout)
    except Exception as exc:  # an unreadable ledger is a real fault, not a nuance
        return Check("governance", RED, str(exc))

    serious = [p for p in problems if p.serious]
    if serious:
        first = serious[0]
        return Check(
            "governance",
            AMBER,
            f"{len(recorded)} files recorded · {len(serious)} differ — {first.path} is {first.state}",
        )
    detail = f"{len(recorded)} files recorded · each with an origin, a licence, and a hash"
    edited = len(problems) - len(serious)
    if edited:
        detail += f" · {edited} edited by this repository, which is allowed"
    return Check("governance", GREEN, detail)


def _claude(ctx: Context) -> Check:
    """Every instruction file on disk, not only Claude's.

    A folder set up by `edify init new` has five or six of them and they all carry the
    same block, so one of them going stale — a command renamed, the graph section
    edited away — is the same failure whichever file it happened in. The check is named
    for `CLAUDE.md` because that is the one every install has.
    """
    present = [p for p in ctx.layout.instruction_files() if p.is_file()]
    if not present:
        return Check("CLAUDE.md", RED, "missing — run `edify init`")

    expected = _instruction_body(ctx, detect(ctx.layout.root))
    wanted = [line for line in expected.splitlines() if line.strip().startswith("/")]
    for path in present:
        rel = ctx.layout.rel(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if ".edify/graph/" not in text:
            return Check("CLAUDE.md", AMBER, f"{rel} does not point at the graph, which is the one thing it is for")
        if [line for line in wanted if line not in text]:
            return Check("CLAUDE.md", AMBER, f"{rel} does not list every command `edify init` would write")

    named = ", ".join(ctx.layout.rel(p) for p in present)
    return Check("CLAUDE.md", GREEN, f"{len(present)} instruction file(s) · {named} · each points at the graph")


def _license(ctx: Context) -> Check:
    ent = ctx.entitlement
    if ent.problem:
        return Check("license", AMBER, f"running free — {ent.problem}")
    if ent.warning and ent.license:
        return Check("license", AMBER, f"{ent.plan} · expires in {ent.license.days_left} days")

    if ent.paid:
        return Check("license", GREEN, f"{ent.plan} · team edition licensed")
    return Check("license", GREEN, "public edition · uncapped")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


@dataclass
class _Vcs:
    """What doctor needs from version control, asked once. `hooks is None`: no repository."""

    root: Path
    head: str = ""
    hooks: Path | None = None

    @classmethod
    def probe(cls, root: Path) -> _Vcs:
        # One call for both. With no commits yet `HEAD` fails the whole call, so the
        # hooks path is asked again alone — the rare case pays for the second spawn.
        lines = _vcs(root, "rev-parse", "--git-path", "hooks", "HEAD")
        if lines is None:
            lines = _vcs(root, "rev-parse", "--git-path", "hooks")
            if lines is None:
                return cls(root)
        hooks = (root / lines[0]).resolve() if lines and lines[0] else None
        return cls(root, head=lines[1] if len(lines) > 1 else "", hooks=hooks)

    def ignored(self, rel: str) -> bool | None:
        if self.hooks is None:
            return None
        try:
            out = subprocess.run(
                [_BIN, "check-ignore", "-q", rel], cwd=str(self.root),
                capture_output=True, timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return {0: True, 1: False}.get(out.returncode)


_BIN = "git"


def _vcs(root: Path, *args: str) -> list[str] | None:
    try:
        out = subprocess.run(
            [_BIN, *args], cwd=str(root), capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip().splitlines() if out.returncode == 0 else None
