"""The map of the map: communities, hubs, slices, paths.

A million-line repository has a graph no agent can read whole. These answer the
questions that come before `where`: which subsystems exist, what everything flows
through, what slice of the graph a task needs, and how two things connect.

Deterministic and model-free, like every other query. Communities come from label
propagation over the file graph, seeded by directory, so the same tree gives the
same partition on every machine. They are written to `communities.tsv` with the
graph's checksum, so `context` and `explain` read them instead of recomputing.
"""

from __future__ import annotations

import math
import re
from collections import Counter, deque
from dataclasses import dataclass, field

from .model import Node
from .queries import line_range_for, where
from .store import CODE_RELATIONS, GraphStore, read_table, write_table

#: `references` edges are resolved by name after the walk; everything else is read
#: directly from the source. The tag says which, so a reader can weigh a path.
INFERRED = ("references",)
COMMUNITY_HEADER = ("file", "community", "label")
_HUB_KINDS = ("symbol", "route", "table", "module")
_KIND_RANK = {"symbol": 0, "route": 1, "table": 2, "doc-section": 3, "module": 4, "file": 5}
_SEEDS = 12
_FAN_CANDIDATES = 400
_SEEDS_PER_FILE = 3
_STOP = set(
    "the a an and or of to in on for with from by at is are be this that it as add fix "
    "make use new update change when should into all any not can get set via per each".split()
)


def confidence(relation: str) -> str:
    return "INFERRED" if relation in INFERRED else "EXTRACTED"


# ---------------------------------------------------------------------------
# communities
# ---------------------------------------------------------------------------


@dataclass
class Community:
    id: str
    label: str
    files: list[str]
    hubs: list[Node] = field(default_factory=list)


def file_adjacency(store: GraphStore) -> dict[str, Counter]:
    """Undirected, weighted file graph over code edges; packages excluded. Cached."""

    def build() -> dict[str, Counter]:
        adj: dict[str, Counter] = {}
        for s, d, package in store.file_edges:
            if package:
                continue
            adj.setdefault(s, Counter())[d] += 1
            adj.setdefault(d, Counter())[s] += 1
        return adj

    return store.cached("file_adjacency", build)


def communities(store: GraphStore, min_size: int = 3) -> list[Community]:
    """The partition, computed once per store."""
    return store.cached(f"communities:{min_size}", lambda: _communities(store, min_size))


def _communities(store: GraphStore, min_size: int) -> list[Community]:
    files = sorted(f for f, nodes in store.by_file.items() if any(n.kind == "file" for n in nodes))
    adj = file_adjacency(store)
    label = {f: _parent(f) for f in files}
    nbrs = {f: [(g, w) for g, w in adj[f].items() if g in label] for f in files if f in adj}

    for _ in range(10):
        changed = False
        for f in files:
            own = label[f]
            near = nbrs.get(f)
            if not near:
                continue
            weights: dict[str, int] = {own: 1}
            for g, w in near:
                lab = label[g]
                weights[lab] = weights.get(lab, 0) + w
            best = max(sorted(weights), key=lambda k: (weights[k], k == own))
            if best != own:
                label[f], changed = best, True
        if not changed:
            break

    groups: dict[str, list[str]] = {}
    for f, lab in label.items():
        groups.setdefault(lab, []).append(f)

    # Fold a fragment into the neighbour it talks to most, or into its top-level
    # directory when it talks to nothing — a thousand two-file communities is not a map.
    for lab in sorted(groups, key=lambda k: (len(groups[k]), k)):
        members = groups.get(lab)
        if not members or len(members) >= min_size:
            continue
        votes: Counter = Counter()
        for f in members:
            for g, w in adj.get(f, {}).items():
                if label[g] != lab:
                    votes[label[g]] += w
        target = max(sorted(votes), key=lambda k: votes[k]) if votes else _top(members[0])
        if target == lab:
            continue
        groups.setdefault(target, []).extend(members)
        for f in members:
            label[f] = target
        del groups[lab]

    fan = fan_in(store)
    out: list[Community] = []
    for lab, members in groups.items():
        members.sort()
        hubs = sorted(
            (n for f in members for n in store.by_file.get(f, []) if n.kind in _HUB_KINDS),
            key=lambda n: (-fan.get(n.id, 0), n.file, n.line),
        )[:3]
        out.append(Community("", _name(members), members, hubs))
    out.sort(key=lambda c: (-len(c.files), c.label))
    seen: Counter = Counter(c.label for c in out)
    for c in out:
        if seen[c.label] > 1 and c.hubs:
            c.label = f"{c.label} · {c.hubs[0].name}"
    width = len(str(len(out)))
    for i, c in enumerate(out, 1):
        c.id = f"c{i:0{width}d}"
    return out


def write_communities(store: GraphStore, comms: list[Community] | None = None) -> None:
    """`communities.tsv`: file, community id, label — stamped with the graph checksum."""
    comms = communities(store) if comms is None else comms
    header = (*COMMUNITY_HEADER, f"graph={store.signature()}")
    write_table(_communities_path(store), ([f, c.id, c.label] for c in comms for f in c.files), header)


def community_of(store: GraphStore) -> dict[str, Community]:
    """file → its community. Read from `communities.tsv` when it matches this graph."""

    def build() -> dict[str, Community]:
        persisted = _read_communities(store)
        if persisted is not None:
            return persisted
        comms = communities(store)
        try:
            write_communities(store, comms)
        except OSError:
            pass
        return {f: c for c in comms for f in c.files}

    return store.cached("community_of", build)


def _read_communities(store: GraphStore) -> dict[str, Community] | None:
    path = _communities_path(store)
    try:
        with path.open("r", encoding="utf-8") as fh:
            first = fh.readline()
    except OSError:
        return None
    if not first.rstrip("\n").endswith(f"graph={store.signature()}"):
        return None
    by_id: dict[str, Community] = {}
    out: dict[str, Community] = {}
    for row in read_table(path):
        if len(row) < 3:
            return None
        c = by_id.get(row[1])
        if c is None:
            c = by_id[row[1]] = Community(row[1], row[2], [])
        c.files.append(row[0])
        out[row[0]] = c
    return out


def _communities_path(store: GraphStore):
    return store.layout.graph_dir / "communities.tsv"


# ---------------------------------------------------------------------------
# hubs and bridges
# ---------------------------------------------------------------------------


def fan_in(store: GraphStore) -> Counter:
    """Distinct files that reach each node — the honest measure of a hub. Cached."""

    def build() -> Counter:
        by_id = store.by_id
        seen: dict[str, set[str]] = {}
        for s, r, d in store.edges:
            if r in CODE_RELATIONS:
                sn = by_id.get(s)
                if sn is not None:
                    seen.setdefault(d, set()).add(sn.file)
        return Counter({k: len(v) for k, v in seen.items()})

    return store.cached("fan_in", build)


def fan_of(store: GraphStore, ids) -> dict[str, int]:
    """Fan-in for just these nodes: point lookups, unless the edges are loaded anyway."""
    if store._edges is not None or "fan_in" in store._memo:
        full = fan_in(store)
        return {i: full.get(i, 0) for i in ids}
    by_id = store.by_id
    out: dict[str, int] = {}
    for i in ids:
        out[i] = len({by_id[s].file for r, s in store.edges_in(i) if r in CODE_RELATIONS and s in by_id})
    return out


def hubs(store: GraphStore, limit: int = 20) -> list[tuple[Node, int]]:
    fan = fan_in(store)
    by_id = store.by_id
    ranked = [(by_id[k], v) for k, v in fan.items() if k in by_id and by_id[k].kind in _HUB_KINDS]
    ranked.sort(key=lambda p: (-p[1], p[0].file, p[0].line))
    return ranked[:limit]


def bridges(store: GraphStore, comms: list[Community], limit: int = 12) -> list[tuple[str, str, int]]:
    where_is = {f: c.id for c in comms for f in c.files}
    pairs: Counter = Counter()
    for f, nbrs in file_adjacency(store).items():
        a = where_is.get(f)
        if not a:
            continue
        for g, w in nbrs.items():
            b = where_is.get(g)
            if b and a < b:
                pairs[(a, b)] += w
    return [(a, b, w) for (a, b), w in pairs.most_common(limit)]


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------


def report(store: GraphStore, top: int = 40) -> str:
    """MAP.md's text. Also refreshes `communities.tsv`."""
    comms = communities(store)
    try:
        write_communities(store, comms)
    except OSError:
        pass
    meta = store.meta
    by_id = {c.id: c for c in comms}
    lines = [
        "# Graph map",
        "",
        f"Generated by `edify graph map` from commit `{meta.get('commit', '-')[:12]}` —"
        " do not edit. Read this first on an unfamiliar repository; then `edify graph context`.",
        "",
        f"{meta.get('nodes', len(store.nodes))} nodes · {meta.get('edges', len(store.edges))} edges"
        f" · {len(comms)} communities · covered: {meta.get('languages_covered', '-')}",
        "",
        "## Communities",
        "",
        "| id | label | files | hubs |",
        "|---|---|---|---|",
    ]
    for c in comms[:top]:
        hub = ", ".join(f"`{n.name}` {n.ref}" for n in c.hubs) or "—"
        lines.append(f"| {c.id} | {c.label} | {len(c.files)} | {hub} |")
    if len(comms) > top:
        rest = sum(len(c.files) for c in comms[top:])
        lines.append(f"| … | {len(comms) - top} smaller communities | {rest} | — |")

    lines += ["", "## Hubs — what everything flows through", "", "| node | kind | reached from | at |", "|---|---|---|---|"]
    for node, n in hubs(store):
        lines.append(f"| `{node.name}` | {node.kind} | {n} files | {node.ref} |")

    lines += [
        "",
        "## Bridges — the couplings parallel work collides on",
        "",
        "| a | b | edges |",
        "|---|---|---|",
    ]
    for a, b, w in bridges(store, comms):
        lines.append(f"| {a} {by_id[a].label} | {b} {by_id[b].label} | {w} |")
    lines += [
        "",
        "Two tasks in the same community, or across a heavy bridge, are a merge risk;"
        " `edify swarm claim` keeps them apart.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# context: the slice of the graph one task needs
# ---------------------------------------------------------------------------


@dataclass
class Slice:
    seeds: list[tuple[Node, float]]
    related: list[tuple[Node, float, str]]
    text: str
    #: file → matches dropped by the per-file seed cap
    folded: dict[str, int] = field(default_factory=dict)


def terms(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-z_][A-Za-z0-9_./-]*", text)
    out: list[str] = []
    for word in raw:
        parts = [word] + re.split(r"[_./-]|(?<=[a-z])(?=[A-Z])", word)
        for p in parts:
            p = p.lower().strip("._-/")
            if len(p) >= 3 and p not in _STOP and p not in out:
                out.append(p)
    return out


def context(
    store: GraphStore,
    query: str,
    budget: int = 2000,
    depth: int = 1,
    limit: int | None = None,
    offset: int = 0,
) -> Slice:
    """Rank nodes against the words of a task, expand one hop, render to a budget.

    Symbols outrank their module on the same match; one file contributes at most
    three seeds, so a single dominant file cannot crowd out the rest. `limit` and
    `offset` page the connected list.
    """
    ts = terms(query)
    explicit = {tok.strip("`,;()") for tok in query.split()}
    scored = _score(store, ts, explicit)
    # The hub bonus is small, so it only needs computing for the leading candidates.
    lead = sorted(scored, key=lambda i: (-scored[i], i))[:_FAN_CANDIDATES]
    fan = fan_of(store, lead)
    for nid in lead:
        bonus = 0.6 * math.log1p(fan[nid])
        scored[nid] += bonus * (0.75 if store.by_id[nid].kind == "module" else 1)

    ranked = sorted(scored.items(), key=lambda p: (-p[1], _KIND_RANK.get(store.by_id[p[0]].kind, 9), p[0]))
    seeds: list[tuple[str, float]] = []
    per_file: Counter = Counter()
    folded: Counter = Counter()
    for nid, s in ranked:
        node = store.by_id[nid]
        if per_file[node.file] and node.kind in ("module", "file"):
            continue  # the file is already on the list; its module node adds nothing
        if per_file[node.file] >= _SEEDS_PER_FILE:
            folded[node.file] += 1
            continue
        if len(seeds) >= _SEEDS:
            if per_file[node.file]:
                folded[node.file] += 1
            continue
        seeds.append((nid, s))
        per_file[node.file] += 1

    seed_ids = {i for i, _ in seeds}
    by_id = store.by_id
    related: dict[str, tuple[float, str]] = {}
    frontier = list(seeds)
    for hop in range(max(1, depth)):
        nxt = []
        for nid, s in frontier:
            name = by_id[nid].name
            for rel, dst in store.edges_out(nid):
                if rel in CODE_RELATIONS and dst not in seed_ids and dst in by_id:
                    score = s * 0.4 / (hop + 1)
                    if score > related.get(dst, (0, ""))[0]:
                        related[dst] = (score, f"{name} --{rel}--> it")
                        nxt.append((dst, score))
            for rel, src in store.edges_in(nid):
                if rel in CODE_RELATIONS and src not in seed_ids and src in by_id:
                    score = s * 0.35 / (hop + 1)
                    if score > related.get(src, (0, ""))[0]:
                        related[src] = (score, f"it --{rel}--> {name}")
                        nxt.append((src, score))
        frontier = nxt

    seed_nodes = [(by_id[i], s) for i, s in seeds]
    rel_nodes = sorted(
        ((by_id[k], v[0], v[1]) for k, v in related.items() if by_id[k].kind != "package"),
        key=lambda p: (-p[1], p[0].file, p[0].line),
    )
    missing = [n.id for n, _ in seed_nodes if n.id not in fan]
    if missing:
        fan.update(fan_of(store, missing))
    text = _render(store, query, seed_nodes, rel_nodes, budget, fan, dict(folded), limit, offset)
    return Slice(seed_nodes, rel_nodes, text, dict(folded))


def _score(store: GraphStore, ts: list[str], explicit: set[str]) -> dict[str, float]:
    # Path matches depend only on the file, so they are scored once per file.
    path_hits: dict[str, int] = {}
    for f in store.by_file:
        low = f.lower()
        path_hits[f] = sum(1 for t in ts if t in low)
    scored: dict[str, float] = {}
    for n in store.nodes:
        kind = n.kind
        if kind == "package":
            continue
        name = n.name
        hits = path_hits.get(n.file, 0)
        s = hits * (2 if kind == "file" else 1.5)
        if name in explicit or n.file in explicit:
            s += 12
        if kind == "file":
            # A file's name is its path; its "tail" would be the extension, which
            # is not a match worth anything.
            low = name.lower()
            s += sum(8 for t in ts if t == low)
        else:
            low = name.lower()
            tail = low.rsplit(".", 1)[-1]
            for t in ts:
                if t == tail or t == low:
                    s += 8
                elif t in tail:
                    s += 3
        if s:
            if kind == "module":
                s *= 0.75
            scored[n.id] = s
    return scored


def _render(store, query, seeds, related, budget, fan, folded, limit=None, offset=0) -> str:
    cap = budget * 4  # ~4 characters a token
    comm = community_of(store)
    lines = [f"# context: {query.strip()[:80]}", ""]
    if not seeds:
        lines.append("no node matches these words — try names from the code, or `edify graph map`")
        return "\n".join(lines)

    lines.append("## Read first (file:range)")
    files_seen: list[str] = []
    for node, _ in seeds:
        rng = line_range_for(store, node.file, node.name) if node.kind != "file" else None
        ref = f"{node.file}:{rng[0]}-{rng[1]}" if rng else node.ref
        c = comm.get(node.file)
        lines.append(f"- {ref}  {node.kind} `{node.name}`  ← {fan.get(node.id, 0)} files  [{c.id if c else '-'}]")
        if node.file not in files_seen:
            files_seen.append(node.file)
    more = [(f, n) for f, n in sorted(folded.items()) if f in files_seen]
    if more:
        extra = f", +{len(more) - 5} files" if len(more) > 5 else ""
        lines.append(
            "- also: " + ", ".join(f"{f} +{n}" for f, n in more[:5]) + extra + "  (`edify graph defines <file>`)"
        )

    lines += ["", "## Connected (one hop; INFERRED = resolved by name)"]
    used = sum(len(x) + 1 for x in lines)
    total = len(related)
    start = max(0, offset)
    stop = total if limit is None else min(total, start + max(0, limit))
    shown = 0
    for node, _, why in related[start:stop]:
        rel = why.split("--")[1] if "--" in why else ""
        row = f"- {node.ref}  {node.kind} `{node.name}`  {why}  [{confidence(rel)}]"
        if used + len(row) + 1 > cap:
            break
        lines.append(row)
        used += len(row) + 1
        shown += 1
    if start + shown < total:
        lines.append(f"- {paging(shown, total, start)}" + ("" if limit else " (or raise --budget)"))

    comms = sorted({comm[f].id + " " + comm[f].label for f in files_seen if f in comm})
    if comms:
        lines += ["", "## Communities touched", *[f"- {c}" for c in comms]]
    return "\n".join(lines)


def paging(shown: int, total: int, offset: int) -> str:
    """The one-line pager every truncated list ends with."""
    return f"showing {shown} of {total}; next: --offset {offset + shown}"


# ---------------------------------------------------------------------------
# explain and path
# ---------------------------------------------------------------------------


class Ambiguous(Exception):
    def __init__(self, candidates: list[Node]):
        super().__init__("ambiguous")
        self.candidates = candidates


def resolve_one(store: GraphStore, name: str) -> Node | None:
    """`file::name` pins a file; a bare name must be unique or it is refused."""
    if "::" in name:
        file, _, sym = name.partition("::")
        hits = [n for n in where(store, sym, limit=None) if n.file.endswith(file)]
    else:
        hits = where(store, name)
        exact = [n for n in hits if n.name == name or n.name.rsplit(".", 1)[-1] == name or n.file == name]
        hits = exact or hits
    if not hits:
        return None
    files = [n for n in hits if n.kind == "file"]
    if len(hits) > 1 and len(files) == 1 and files[0].file == name:
        return files[0]
    if len(hits) > 1:
        raise Ambiguous(hits[:10])
    return hits[0]


def explain(store: GraphStore, node: Node, limit: int = 25, offset: int = 0) -> dict[str, object]:
    """One node's edges, both directions, from the store's indexes — no edge scan."""
    by_id = store.by_id
    incoming = [(by_id[s], r) for r, s in store.edges_in(node.id) if s in by_id]
    outgoing = [(by_id[d], r) for r, d in store.edges_out(node.id) if d in by_id]
    c = community_of(store).get(node.file)
    start = max(0, offset)
    inc, out = incoming[start:start + limit], outgoing[start:start + limit]
    return {
        "node": node,
        "community": f"{c.id} {c.label}" if c else "-",
        "fan_in": fan_of(store, [node.id])[node.id],
        "incoming": inc,
        "outgoing": out,
        "incoming_total": len(incoming),
        "outgoing_total": len(outgoing),
        "more": max(0, len(incoming) - start - len(inc)) + max(0, len(outgoing) - start - len(out)),
    }


def path(store: GraphStore, a: Node, b: Node, max_hops: int = 8) -> list[tuple[Node, str, str, Node]] | None:
    """Shortest undirected path; each hop keeps its real direction and relation."""
    def around(cur: str) -> list[tuple[str, str, str]]:
        near = [(d, r, "->") for r, d in store.edges_out(cur)]
        near += [(s, r, "<-") for r, s in store.edges_in(cur)]
        return sorted(near)

    prev: dict[str, tuple[str, str, str]] = {a.id: ("", "", "")}
    q = deque([(a.id, 0)])
    while q:
        cur, d = q.popleft()
        if cur == b.id:
            break
        if d >= max_hops:
            continue
        for nxt, rel, arrow in around(cur):
            if nxt not in prev:
                prev[nxt] = (cur, rel, arrow)
                q.append((nxt, d + 1))
    if b.id not in prev:
        return None
    hops = []
    cur = b.id
    while cur != a.id:
        p, rel, arrow = prev[cur]
        hops.append((store.by_id[p], rel, arrow, store.by_id[cur]))
        cur = p
    return list(reversed(hops))


# ---------------------------------------------------------------------------


def _parent(f: str) -> str:
    return f.rsplit("/", 1)[0] if "/" in f else "."


def _top(f: str) -> str:
    return f.split("/", 1)[0] if "/" in f else "."


def _name(files: list[str]) -> str:
    """The deepest directory holding at least half the community."""
    counts: Counter = Counter()
    for f in files:
        parts = f.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            counts["/".join(parts[:i])] += 1
    if not counts:
        return "(root files)"
    half = len(files) / 2
    good = [d for d, n in counts.items() if n >= half]
    if good:
        return max(good, key=lambda d: (d.count("/"), counts[d])) + "/"
    top = max(counts, key=lambda d: (counts[d], d.count("/")))
    return f"{top}/ +{len({f.rsplit('/', 1)[0] for f in files if '/' in f}) - 1} dirs"
