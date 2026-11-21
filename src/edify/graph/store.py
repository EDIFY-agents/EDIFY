"""Reading and writing `.edify/graph/`.

nodes.tsv, edges.tsv, meta, plus the derived communities.tsv. Sorted and
checksummed, so a rebuild on unchanged source is byte-identical and a graph diff
is a structural diff of the codebase.
"""

from __future__ import annotations

import hashlib
import mmap
from pathlib import Path
from typing import Callable, Iterable, Sequence, TypeVar

from .. import GRAPH_SCHEMA
from ..errors import GraphMissing
from ..paths import Layout
from ..tsv import read_kv, sha256_file, unescape, write_kv
from .model import Edge, Node

NODE_HEADER = ("id", "kind", "file", "line", "name", "fingerprint")
REV_HEADER = ("to", "relation", "from")
EDGE_HEADER = ("from", "relation", "to")
#: Relations that mean "this code uses that code". `defines`, `documents` and
#: `migrates` are structure, not use.
CODE_RELATIONS = ("references", "imports", "exposes")

T = TypeVar("T")
_SPECIAL = ("\\", "\t", "\n", "\r")


class GraphStore:
    """The graph on disk, loaded lazily, indexed once.

    Nodes and edges are read on first use; every index (by name, id, file, edge
    direction, file adjacency) is built on first use and kept for the life of one
    command. `write` drops them all.
    """

    def __init__(self, layout: Layout):
        self.layout = layout
        self._nodes: list[Node] | None = None
        self._edges: list[Edge] | None = None
        self._memo: dict[str, object] = {}

    # -- presence --------------------------------------------------------

    def exists(self) -> bool:
        return self.layout.nodes.exists()

    def require(self) -> None:
        if not self.exists():
            raise GraphMissing()

    # -- loading ---------------------------------------------------------

    @property
    def nodes(self) -> list[Node]:
        if self._nodes is None:
            self.require()
            self._nodes = [_node(r) for r in _read(self.layout.nodes)]
        return self._nodes

    @property
    def edges(self) -> list[Edge]:
        if self._edges is None:
            self.require()
            self._edges = [Edge(*r) if len(r) == 3 else Edge.from_row(r) for r in _read(self.layout.edges)]
        return self._edges

    def cached(self, key: str, build: Callable[[], T]) -> T:
        """Memoise a derived structure until the next `write`."""
        if key not in self._memo:
            self._memo[key] = build()
        return self._memo[key]  # type: ignore[return-value]

    @property
    def by_name(self) -> dict[str, list[Node]]:
        def build() -> dict[str, list[Node]]:
            index: dict[str, list[Node]] = {}
            for n in self.nodes:
                index.setdefault(n.name, []).append(n)
                # The last segment too, so `where accept` finds `Service.accept`.
                tail = n.name.rsplit(".", 1)[-1]
                if tail != n.name:
                    index.setdefault(tail, []).append(n)
            return index

        return self.cached("by_name", build)

    @property
    def by_id(self) -> dict[str, Node]:
        return self.cached("by_id", lambda: {n.id: n for n in self.nodes})

    @property
    def by_file(self) -> dict[str, list[Node]]:
        def build() -> dict[str, list[Node]]:
            index: dict[str, list[Node]] = {}
            for n in self.nodes:
                index.setdefault(n.file, []).append(n)
            return index

        return self.cached("by_file", build)

    @property
    def out_edges(self) -> dict[str, list[tuple[str, str]]]:
        """node id → [(relation, dst)], every relation, in file order."""
        return self._directed()[0]

    @property
    def in_edges(self) -> dict[str, list[tuple[str, str]]]:
        """node id → [(relation, src)], every relation, in file order."""
        return self._directed()[1]

    def _directed(self) -> tuple[dict[str, list[tuple[str, str]]], dict[str, list[tuple[str, str]]]]:
        def build():
            out: dict[str, list[tuple[str, str]]] = {}
            inc: dict[str, list[tuple[str, str]]] = {}
            for s, r, d in self.edges:
                out.setdefault(s, []).append((r, d))
                inc.setdefault(d, []).append((r, s))
            return out, inc

        return self.cached("directed", build)

    # -- point lookups: one node's edges without loading the rest ----------

    def edges_out(self, node_id: str) -> list[tuple[str, str]]:
        """[(relation, dst)] for one node, in file order.

        Served from memory when the edges are already loaded; otherwise a binary
        search over `edges.tsv`, which is sorted by source — so `explain` on a
        million-edge graph reads a few kilobytes instead of the whole file.
        """
        if self._edges is not None or "directed" in self._memo:
            return self.out_edges.get(node_id, [])
        mm = self._mapped(self.layout.edges)
        if mm is None:
            return self.out_edges.get(node_id, [])
        return [(r[1], r[2]) for r in _block(mm, node_id) if len(r) >= 3]

    def edges_in(self, node_id: str) -> list[tuple[str, str]]:
        """[(relation, src)] for one node, in the same order `in_edges` gives."""
        if self._edges is not None or "directed" in self._memo:
            return self.in_edges.get(node_id, [])
        mm = self._mapped(self.edges_rev_path)
        if mm is None or self.meta.get("edges_rev_sha256", "") == "":
            return self.in_edges.get(node_id, [])
        rows = [(r[2], r[1], r[0]) for r in _block(mm, node_id) if len(r) >= 3]
        rows.sort(key=_line)  # edges.tsv order: by the rendered (src, relation, dst) line
        return [(r, s) for s, r, _ in rows]

    @property
    def edges_rev_path(self) -> Path:
        return self.layout.graph_dir / "edges.rev.tsv"

    def _mapped(self, path: Path):
        key = "mmap:" + path.name
        if key not in self._memo:
            mm = None
            try:
                with open(path, "rb") as fh:
                    if fh.seek(0, 2) > 0:
                        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            except (OSError, ValueError):
                mm = None
            self._memo[key] = mm
        return self._memo[key]

    @property
    def file_edges(self) -> list[tuple[str, str, bool]]:
        """(src file, dst file, dst is a package) for every cross-file code edge.

        One entry per edge, so a count is a weight. The base of file adjacency and
        the file-level dependents walk.
        """

        def build() -> list[tuple[str, str, bool]]:
            by_id = self.by_id
            out: list[tuple[str, str, bool]] = []
            for s, r, d in self.edges:
                if r not in CODE_RELATIONS:
                    continue
                sn, dn = by_id.get(s), by_id.get(d)
                if sn is None or dn is None or sn.file == dn.file:
                    continue
                out.append((sn.file, dn.file, dn.kind == "package"))
            return out

        return self.cached("file_edges", build)

    @property
    def meta(self) -> dict[str, str]:
        return read_kv(self.layout.meta)

    def line_count(self, file: str) -> int | None:
        """Lines up to the last non-blank one, or None when the file cannot be read."""
        counts: dict[str, int | None] = self.cached("line_counts", dict)
        if file not in counts:
            try:
                data = (self.layout.root / file).read_bytes()
            except OSError:
                counts[file] = None
            else:
                counts[file] = data.rstrip().count(b"\n") + 1 if data.strip() else 0
        return counts[file]

    # -- writing ---------------------------------------------------------

    def write(self, nodes: list[Node], edges: list[Edge], meta: dict[str, str]) -> dict[str, str]:
        """Write all three files and return the meta actually recorded."""
        self.layout.graph_dir.mkdir(parents=True, exist_ok=True)
        seen_nodes: dict[str, Node] = {}
        for n in nodes:
            # First writer wins on a duplicate id, which makes the result
            # independent of directory iteration order.
            seen_nodes.setdefault(n.id, n)
        node_rows = sorted((_line(n.row()), n) for n in seen_nodes.values())
        edge_rows = sorted((_line(e), e) for e in {Edge(*e) for e in edges})

        self._close_maps()
        nodes_sha = _write(self.layout.nodes, [r for r, _ in node_rows], NODE_HEADER)
        edges_sha = _write(self.layout.edges, [r for r, _ in edge_rows], EDGE_HEADER)
        # The same edges sorted by destination, so `edges_in` is a binary search too.
        rev_sha = _write(self.edges_rev_path, sorted(_line((d, r, s)) for _, (s, r, d) in edge_rows), REV_HEADER)
        full = dict(meta)
        full.update(
            {
                "schema": str(GRAPH_SCHEMA),
                "nodes": str(len(node_rows)),
                "edges": str(len(edge_rows)),
                "nodes_sha256": nodes_sha,
                "edges_sha256": edges_sha,
                "edges_rev_sha256": rev_sha,
            }
        )
        write_kv(self.layout.meta, full)
        self._nodes = [n for _, n in node_rows]
        self._edges = [e for _, e in edge_rows]
        self._memo = {}
        return full

    def _close_maps(self) -> None:
        for key in [k for k in self._memo if k.startswith("mmap:")]:
            mm = self._memo.pop(key)
            if mm is not None:
                mm.close()

    def signature(self) -> str:
        """Identifies this graph's content; derived files record it to detect staleness."""
        m = self.meta
        return f"{m.get('nodes_sha256', '-')[:16]}.{m.get('edges_sha256', '-')[:16]}"

    # -- integrity -------------------------------------------------------

    def verify_checksums(self) -> list[str]:
        """Complaints, one line each. Empty means the files match their meta."""
        problems: list[str] = []
        meta = self.meta
        pairs = [(self.layout.nodes, "nodes_sha256"), (self.layout.edges, "edges_sha256")]
        if "edges_rev_sha256" in meta:
            pairs.append((self.edges_rev_path, "edges_rev_sha256"))
        for path, key in pairs:
            recorded = meta.get(key)
            if not recorded:
                problems.append(f"{path.name}: no checksum recorded in meta")
                continue
            actual = sha256_file(path)
            if actual != recorded:
                problems.append(f"{path.name}: content does not match its recorded checksum")
        if meta.get("schema") and meta["schema"] != str(GRAPH_SCHEMA):
            problems.append(
                f"graph schema is {meta['schema']}, this edify writes {GRAPH_SCHEMA}"
                " — run `edify graph build`"
            )
        return problems


def load(layout: Layout) -> GraphStore:
    return GraphStore(layout)


def graph_paths(root: Path) -> tuple[Path, Path, Path]:
    base = root / ".edify" / "graph"
    return base / "nodes.tsv", base / "edges.tsv", base / "meta"


# ---------------------------------------------------------------------------
# TSV, fast path. Same bytes as `edify.tsv`; escaping only runs on the rare field
# that needs it, which is what makes a million-row read take a second, not a minute.
# ---------------------------------------------------------------------------


def _esc(value: str) -> str:
    if "\\" in value or "\t" in value or "\n" in value or "\r" in value:
        return value.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
    return value


def _line(row: Sequence[str]) -> str:
    line = "\t".join(row)
    # One C-level scan instead of four per field: only a row with a backslash,
    # newline, carriage return or an embedded tab needs field-by-field escaping.
    if "\\" in line or "\n" in line or "\r" in line or line.count("\t") != len(row) - 1:
        return "\t".join([_esc(c) for c in row])
    return line


def _write(path: Path, lines: list[str], header: Sequence[str]) -> str:
    """Pre-sorted lines → file; returns its sha256."""
    body = ("#" + "\t".join(header) + "\n" + "".join(line + "\n" for line in lines)).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def write_table(path: Path, rows: Iterable[Sequence[str]], header: Sequence[str]) -> str:
    """Sort rendered rows and write them, as `tsv.write_rows` does."""
    return _write(path, sorted(_line(r) for r in rows), header)


def _block(mm, key: str) -> list[list[str]]:
    """Rows whose first field is `key`, from a file sorted by rendered line."""
    prefix = (_esc(key) + "\t").encode("utf-8")
    start = mm.find(b"\n") + 1 if mm[:1] == b"#" else 0
    lo, hi, end = start, len(mm), len(mm)
    while lo < hi:
        mid = (lo + hi) // 2
        ls = max(start, mm.rfind(b"\n", start, mid) + 1)
        le = mm.find(b"\n", ls)
        le = end if le == -1 else le
        if mm[ls:le] < prefix:
            lo = le + 1
        else:
            hi = ls
    rows: list[list[str]] = []
    pos = lo
    while pos < end:
        le = mm.find(b"\n", pos)
        le = end if le == -1 else le
        line = mm[pos:le]
        if not line.startswith(prefix):
            break
        text = line.decode("utf-8", errors="replace").rstrip("\r")
        rows.append([unescape(c) for c in text.split("\t")] if "\\" in text else text.split("\t"))
        pos = le + 1
    return rows


def _read(path: Path) -> list[list[str]]:
    """Rows of a TSV, comment lines skipped."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[list[str]] = []
    for line in text.split("\n"):
        if not line or line[0] == "#":
            continue
        if line[-1] == "\r":
            line = line.rstrip("\r")
        if "\\" in line:
            out.append([unescape(c) for c in line.split("\t")])
        else:
            out.append(line.split("\t"))
    return out


def read_table(path: Path) -> list[list[str]]:
    return _read(path)


def _node(row: list[str]) -> Node:
    if len(row) == 6:
        try:
            return Node(row[0], row[1], row[2], int(row[3]), row[4], row[5])
        except ValueError:
            pass
    return Node.from_row(row)
