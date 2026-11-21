"""Paging, persisted communities, range clamping and context ranking."""

from __future__ import annotations

import json
from pathlib import Path

from edify.cli import main
from edify.graph import extract, insight, queries
from edify.graph.store import GraphStore
from edify.paths import Layout


def built(repo: Path) -> GraphStore:
    layout = Layout(repo)
    layout.edify.mkdir(parents=True, exist_ok=True)
    extract.build(layout)
    return GraphStore(layout)


def _many_helpers(repo: Path, n: int = 5) -> None:
    for i in range(n):
        (repo / "src" / f"h{i}.py").write_text(f"def shared_helper():\n    return {i}\n", encoding="utf-8")


def test_where_pages_and_says_what_comes_next(installed: Path, capsys) -> None:
    _many_helpers(installed)
    assert main(["--repo", str(installed), "--quiet", "graph", "build"]) == 0
    capsys.readouterr()
    assert main(["--repo", str(installed), "graph", "where", "shared_helper", "--limit", "2"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len([line for line in out if "shared_helper" in line]) == 2
    assert out[-1] == "showing 2 of 5; next: --offset 2"

    assert main(["--repo", str(installed), "graph", "where", "shared_helper", "--limit", "2", "--offset", "4"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 1 and "src/h4.py:1" in out[0]

    assert main(["--repo", str(installed), "--json", "graph", "where", "shared_helper", "--limit", "3"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 3


def test_communities_are_persisted_deterministically(repo: Path) -> None:
    store = built(repo)
    insight.report(store)
    path = store.layout.graph_dir / "communities.tsv"
    first = path.read_bytes()
    assert first.startswith(b"#file\tcommunity\tlabel\tgraph=")

    again = built(repo)
    insight.report(again)
    assert path.read_bytes() == first

    # A reader trusts the file only while it matches the graph it came from.
    fresh = GraphStore(store.layout)
    persisted = insight.community_of(fresh)
    computed = {f: c for c in insight.communities(fresh) for f in c.files}
    assert {f: (c.id, c.label) for f, c in persisted.items()} == {f: (c.id, c.label) for f, c in computed.items()}
    path.write_text("#file\tcommunity\tlabel\tgraph=stale\nsrc/tools.py\tc9\tbogus\n", encoding="utf-8")
    assert insight.community_of(GraphStore(store.layout))["src/tools.py"].label != "bogus"


def test_last_symbol_range_stops_at_end_of_file(repo: Path) -> None:
    store = built(repo)
    lines = (repo / "src" / "tools.py").read_text(encoding="utf-8").rstrip().count("\n") + 1
    last = max((n for n in store.by_file["src/tools.py"] if n.kind == "symbol"), key=lambda n: n.line)
    start, end = queries.line_range_for(store, "src/tools.py", last.name)
    assert start == last.line
    assert end == min(last.line + 40, lines)


def test_context_caps_seeds_per_file_and_prefers_symbols(repo: Path) -> None:
    body = "".join(f"def ledger_entry_{i}():\n    return {i}\n\n" for i in range(8))
    (repo / "src" / "ledger.py").write_text(body, encoding="utf-8")
    (repo / "src" / "other_ledger.py").write_text("def ledger_total():\n    return 0\n", encoding="utf-8")
    sl = insight.context(built(repo), "ledger entry totals")
    files = [n.file for n, _ in sl.seeds]
    assert files.count("src/ledger.py") <= 3
    assert "src/other_ledger.py" in files
    assert sl.folded.get("src/ledger.py", 0) >= 5
    assert "also: src/ledger.py +" in sl.text
    kinds = [n.kind for n, _ in sl.seeds if n.file == "src/ledger.py"]
    assert kinds[0] == "symbol" and "module" not in kinds


def test_explain_reads_indexes_and_pages(repo: Path) -> None:
    store = built(repo)
    node = insight.resolve_one(store, "generate")
    info = insight.explain(store, node, limit=1)
    scanned_in = [e for e in store.edges if e.dst == node.id]
    assert info["incoming_total"] == len(scanned_in)
    assert len(info["incoming"]) == min(1, len(scanned_in))


def test_point_lookups_match_the_in_memory_index(repo) -> None:
    """edges_out/edges_in from the sorted files give exactly what the full load gives."""
    from edify.graph import extract
    from edify.graph.store import GraphStore
    from edify.paths import Layout

    layout = Layout(repo)
    layout.edify.mkdir(parents=True, exist_ok=True)
    extract.build(layout)
    loaded = GraphStore(layout)
    loaded.edges  # force the full load
    lazy = GraphStore(layout)
    ids = [n.id for n in lazy.nodes]
    assert ids
    for i in ids:
        assert lazy.edges_out(i) == loaded.edges_out(i), i
        assert lazy.edges_in(i) == loaded.edges_in(i), i
    assert lazy._edges is None, "point lookups must not load every edge"
    assert lazy.verify_checksums() == []


def test_a_parallel_build_is_byte_identical_to_a_serial_one(repo, monkeypatch) -> None:
    from edify.graph import extract
    from edify.paths import Layout

    layout = Layout(repo)
    layout.edify.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("EDIFY_JOBS", "1")
    extract.build(layout)
    serial = (layout.nodes.read_bytes(), layout.edges.read_bytes())

    monkeypatch.setenv("EDIFY_JOBS", "2")
    monkeypatch.setattr(extract, "PARALLEL_MIN_FILES", 1)
    monkeypatch.setattr(extract, "_CHUNK", 1)
    extract.build(layout)
    assert (layout.nodes.read_bytes(), layout.edges.read_bytes()) == serial


def test_dependents_by_lookup_match_dependents_from_memory(repo) -> None:
    from edify.graph import extract, queries
    from edify.graph.store import GraphStore
    from edify.paths import Layout

    layout = Layout(repo)
    layout.edify.mkdir(parents=True, exist_ok=True)
    extract.build(layout)
    names = sorted({n.name for n in GraphStore(layout).nodes})
    for name in names:
        for depth in (1, 3):
            loaded = GraphStore(layout)
            loaded.edges
            lazy = GraphStore(layout)
            assert queries.dependents(lazy, name, depth) == queries.dependents(loaded, name, depth), (name, depth)
            assert lazy._edges is None
