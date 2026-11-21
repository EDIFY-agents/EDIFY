"""`edify graph` — build the map and ask it questions.

All mechanical, all deterministic. These are the commands `CLAUDE.md` points at,
and the only part of the CLI a model invokes routinely. On a huge repository the
order is: `map` once, `context` per task, `where`/`explain`/`path` for specifics.

Exit codes for `explain` and `path`: 0 answered, 3 ambiguous name, 4 no such node.
"""

from __future__ import annotations

from .. import anim
from ..context import Context
from ..graph import extract, insight, queries


def build(ctx: Context) -> int:
    ctx.layout.require_installed()
    with anim.spinner(ctx.out, "reading every file, building the map"):
        result = extract.build(ctx.layout, backend=ctx.args.extractor)

    ctx.out.data(result.as_dict())
    ctx.out.line(
        f"{result.nodes} nodes · {result.edges} edges · {result.files} files"
        f" · {result.backend}"
    )
    covered = ", ".join(f"{k} ({v})" for k, v in sorted(result.languages.items()))
    if covered:
        ctx.out.line(f"covered: {covered}")
    if result.uncovered:
        ctx.out.line(
            "not covered: "
            + ", ".join(f"{k} ({v} files)" for k, v in sorted(result.uncovered.items()))
        )
        ctx.out.note("a language the extractor does not handle has no nodes. That gap is stated, not filled.")
    _write_map(ctx)
    return 0


def update(ctx: Context) -> int:
    ctx.layout.require_installed()
    ctx.store.require()
    dirs = list(ctx.args.dirs or [])
    if ctx.args.changed:
        found = extract.changed_dirs(ctx.layout.root, ctx.store.meta.get("commit", "-"))
        if found is None:
            ctx.out.note("git cannot say what changed since the graph was built — rebuilding everything")
            found = ["."]
        if not found:
            ctx.out.data({"changed": []})
            ctx.out.line("graph is current — nothing changed since it was built")
            return 0
        dirs = found
    if not dirs:
        ctx.out.error("name the directories to re-extract, or pass --changed")
        return 2
    with anim.spinner(ctx.out, f"re-extracting {len(dirs)} director(ies)"):
        result = extract.build(
            ctx.layout,
            backend=ctx.args.extractor,
            subdirs=None if dirs == ["."] else dirs,
        )
    ctx.out.data({**result.as_dict(), "dirs": dirs})
    ctx.out.line(f"{result.nodes} nodes · {result.edges} edges (re-extracted {', '.join(dirs)[:120]})")
    _write_map(ctx)
    return 0


def map_(ctx: Context) -> int:
    ctx.store.require()
    text = _write_map(ctx)
    ctx.out.data({"path": ctx.layout.rel(ctx.layout.graph_dir / "MAP.md")})
    ctx.out.line(text)
    return 0


def context(ctx: Context) -> int:
    ctx.store.require()
    query = " ".join(ctx.args.query)
    sl = insight.context(
        ctx.store, query, budget=ctx.args.budget, depth=ctx.args.depth,
        limit=getattr(ctx.args, "limit", None) or None, offset=getattr(ctx.args, "offset", 0),
    )
    ctx.out.data(
        {
            "seeds": [_node(n) | {"score": round(s, 2)} for n, s in sl.seeds],
            "related": [_node(n) | {"score": round(s, 2), "why": w} for n, s, w in sl.related[:100]],
        }
    )
    ctx.out.line(sl.text)
    return 0 if sl.seeds else 4


def explain(ctx: Context) -> int:
    ctx.store.require()
    node = _one(ctx, ctx.args.name)
    if isinstance(node, int):
        return node
    info = insight.explain(
        ctx.store, node, limit=getattr(ctx.args, "limit", 25) or 10**9, offset=getattr(ctx.args, "offset", 0)
    )
    ctx.out.data(
        {
            "node": _node(node),
            "community": info["community"],
            "fan_in": info["fan_in"],
            "incoming_total": info["incoming_total"],
            "outgoing_total": info["outgoing_total"],
            "incoming": [_node(n) | {"relation": r, "confidence": insight.confidence(r)} for n, r in info["incoming"]],
            "outgoing": [_node(n) | {"relation": r, "confidence": insight.confidence(r)} for n, r in info["outgoing"]],
        }
    )
    ctx.out.line(f"{node.kind} `{node.name}`  {node.ref}")
    ctx.out.line(f"community {info['community']} · reached from {info['fan_in']} files")
    for n, r in info["outgoing"]:
        ctx.out.line(f"  --{r}--> {n.name}  {n.ref}  [{insight.confidence(r)}]")
    for n, r in info["incoming"]:
        ctx.out.line(f"  <--{r}-- {n.name}  {n.ref}  [{insight.confidence(r)}]")
    if info["more"]:
        shown = max(len(info["incoming"]), len(info["outgoing"]))
        total = max(info["incoming_total"], info["outgoing_total"])
        ctx.out.line("  " + insight.paging(shown, total, max(0, getattr(ctx.args, "offset", 0))))
    return 0


def path(ctx: Context) -> int:
    ctx.store.require()
    a = _one(ctx, ctx.args.a)
    if isinstance(a, int):
        return a
    b = _one(ctx, ctx.args.b)
    if isinstance(b, int):
        return b
    hops = insight.path(ctx.store, a, b, max_hops=ctx.args.max_hops)
    if hops is None:
        ctx.out.data({"path": None})
        ctx.out.line(f"no path within {ctx.args.max_hops} hops between `{a.name}` and `{b.name}`")
        return 4
    weakest = "INFERRED" if any(insight.confidence(r) == "INFERRED" for _, r, _, _ in hops) else "EXTRACTED"
    ctx.out.data(
        {
            "hops": [{"from": _node(s), "relation": r, "direction": d, "to": _node(t)} for s, r, d, t in hops],
            "confidence": weakest,
        }
    )
    ctx.out.line(f"{len(hops)} hop(s), confidence {weakest}:")
    for s, r, d, t in hops:
        arrow = f"--{r}-->" if d == "->" else f"<--{r}--"
        ctx.out.line(f"  {s.name} {arrow} {t.name}  {t.ref}")
    return 0


_HOOK = """#!/bin/sh
# edify:graph-hook — keeps .edify/graph current; remove with `edify graph hook --remove`
command -v edify >/dev/null 2>&1 && edify --quiet graph update --changed >/dev/null 2>&1 &
exit 0
"""


def hook(ctx: Context) -> int:
    """Git hooks that refresh the graph after commit, merge and checkout."""
    import subprocess
    from pathlib import Path

    out = subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks"], cwd=str(ctx.layout.root),
        capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        ctx.out.error("not a git repository")
        return 1
    hooks = (ctx.layout.root / out.stdout.strip()).resolve()
    hooks.mkdir(parents=True, exist_ok=True)
    done = []
    for name in ("post-commit", "post-merge", "post-checkout", "post-rewrite"):
        target = Path(hooks) / name
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        ours = "edify:graph-hook" in existing
        if ctx.args.remove:
            if ours:
                target.unlink()
                done.append(name)
            continue
        if existing and not ours:
            ctx.out.warn(f"{name} exists and is not ours — left alone; add `edify graph update --changed` to it")
            continue
        target.write_text(_HOOK, encoding="utf-8")
        target.chmod(0o755)
        done.append(name)
    ctx.out.data({"hooks": done, "removed": bool(ctx.args.remove)})
    ctx.out.line(("removed: " if ctx.args.remove else "installed: ") + (", ".join(done) or "nothing"))
    return 0


def _one(ctx: Context, name: str):
    try:
        node = insight.resolve_one(ctx.store, name)
    except insight.Ambiguous as amb:
        ctx.out.data({"ambiguous": [_node(n) for n in amb.candidates]})
        ctx.out.line(f"`{name}` names several nodes — pin one with `file::name`:")
        for n in amb.candidates:
            ctx.out.line(f"  {n.file}::{n.name}\t{n.kind}\t{n.ref}")
        return 3
    if node is None:
        ctx.out.data({"missing": name})
        ctx.out.line(f"nothing named `{name}` in the graph")
        return 4
    return node


def _write_map(ctx: Context) -> str:
    text = insight.report(ctx.store)
    (ctx.layout.graph_dir / "MAP.md").write_text(text, encoding="utf-8")
    return text


def where(ctx: Context) -> int:
    ctx.store.require()
    hits = queries.where(ctx.store, ctx.args.name, kind=ctx.args.kind, limit=None)
    page = _page(ctx, hits)
    ctx.out.data([_node(n) for n in page])
    if not hits:
        ctx.out.line(f"nothing named `{ctx.args.name}` in the graph")
        return 1
    for node in page:
        ctx.out.line(f"{node.ref}\t{node.kind}\t{node.name}")
    _pager(ctx, len(page), len(hits))
    return 0


def dependents(ctx: Context) -> int:
    ctx.store.require()
    hits = queries.dependents(ctx.store, ctx.args.symbol, depth=ctx.args.depth)
    page = _page(ctx, hits)
    ctx.out.data([_node(n) for n in page])
    if not hits:
        ctx.out.line(f"nothing in this repository depends on `{ctx.args.symbol}`")
        return 0
    for node in page:
        ctx.out.line(f"{node.ref}\t{node.kind}\t{node.name}")
    _pager(ctx, len(page), len(hits))
    return 0


def references(ctx: Context) -> int:
    ctx.store.require()
    hits = queries.references(ctx.store, ctx.args.name)
    page = _page(ctx, hits)
    ctx.out.data([_node(n) for n in page])
    for node in page:
        ctx.out.line(f"{node.ref}\t{node.kind}\t{node.name}")
    _pager(ctx, len(page), len(hits))
    if not hits:
        ctx.out.line(f"no references to `{ctx.args.name}` in this repository")
    return 0


def defines(ctx: Context) -> int:
    ctx.store.require()
    hits = queries.defines(ctx.store, ctx.args.file)
    page = _page(ctx, hits)
    ctx.out.data([_node(n) for n in page])
    if not hits:
        ctx.out.line(f"`{ctx.args.file}` defines nothing the graph indexes")
        return 0
    for node in page:
        ctx.out.line(f"{node.line}\t{node.kind}\t{node.name}")
    _pager(ctx, len(page), len(hits))
    return 0


def overlap(ctx: Context) -> int:
    ctx.store.require()
    a = _split(ctx.args.a)
    b = _split(ctx.args.b)
    result = queries.overlap(ctx.store, a, b, depth=ctx.args.depth)
    ctx.out.data(
        {
            "safe": result.safe,
            "overlapping": sorted(result.overlapping),
            "a_radius": sorted(result.a_radius),
            "b_radius": sorted(result.b_radius),
        }
    )
    if result.safe:
        ctx.out.line("disjoint — these may run in parallel")
        return 0
    ctx.out.line("overlapping:")
    for path in sorted(result.overlapping):
        ctx.out.line(f"  {path}")
    return 1


def stat(ctx: Context) -> int:
    ctx.store.require()
    meta = ctx.store.meta
    kinds: dict[str, int] = {}
    for node in ctx.store.nodes:
        kinds[node.kind] = kinds.get(node.kind, 0) + 1
    relations: dict[str, int] = {}
    for edge in ctx.store.edges:
        relations[edge.relation] = relations.get(edge.relation, 0) + 1

    ctx.out.data({"meta": meta, "kinds": kinds, "relations": relations})
    ctx.out.table(["kind", "count"], [[k, str(v)] for k, v in sorted(kinds.items())])
    ctx.out.line("")
    ctx.out.table(["relation", "count"], [[k, str(v)] for k, v in sorted(relations.items())])
    ctx.out.line("")
    for key in ("commit", "extractor", "extractor_version", "languages_covered", "languages_uncovered"):
        if key in meta:
            ctx.out.line(f"{key}: {meta[key]}")
    problems = ctx.store.verify_checksums()
    for problem in problems:
        ctx.out.warn(problem)
    return 0


def _page(ctx: Context, hits: list) -> list:
    """The `--offset`/`--limit` window of a hit list (limit 0: everything)."""
    offset = max(0, getattr(ctx.args, "offset", 0) or 0)
    limit = getattr(ctx.args, "limit", 0) or 0
    return hits[offset : offset + limit] if limit > 0 else hits[offset:]


def _pager(ctx: Context, shown: int, total: int) -> None:
    offset = max(0, getattr(ctx.args, "offset", 0) or 0)
    if offset + shown < total:
        ctx.out.line(insight.paging(shown, total, offset))


def _split(value: str) -> list[str]:
    return [p.strip() for p in value.replace(",", " ").split() if p.strip()]


def _node(node) -> dict[str, object]:
    return {
        "id": node.id,
        "kind": node.kind,
        "file": node.file,
        "line": node.line,
        "name": node.name,
        "ref": node.ref,
        "fingerprint": node.fingerprint,
    }
