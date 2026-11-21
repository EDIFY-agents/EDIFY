"""The map of the map: communities, context slices, explain, path, incremental update."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from edify.cli import main
from edify.graph import extract, insight
from edify.graph.store import GraphStore
from edify.paths import Layout


def built(repo: Path) -> GraphStore:
    layout = Layout(repo)
    layout.edify.mkdir(parents=True, exist_ok=True)
    extract.build(layout)
    return GraphStore(layout)


def test_communities_cover_every_file_and_are_deterministic(repo: Path) -> None:
    store = built(repo)
    a = insight.communities(store)
    b = insight.communities(built(repo))
    files = {f for c in a for f in c.files}
    assert files == {n.file for n in store.nodes if n.kind == "file"}
    assert [(c.id, c.label, c.files) for c in a] == [(c.id, c.label, c.files) for c in b]


def test_report_names_hubs_and_communities(repo: Path) -> None:
    text = insight.report(built(repo))
    assert "## Communities" in text and "## Hubs" in text and "## Bridges" in text


def test_context_finds_the_symbol_a_task_names(repo: Path) -> None:
    sl = insight.context(built(repo), "change how tokens are verified", budget=500)
    assert sl.seeds
    assert any("tokens" in n.file for n, _ in sl.seeds)
    assert len(sl.text) <= 500 * 4 + 400


def test_explain_and_path_exit_codes(installed: Path, capsys) -> None:
    assert main(["--repo", str(installed), "--quiet", "graph", "build"]) == 0
    assert (installed / ".edify" / "graph" / "MAP.md").is_file()
    assert main(["--repo", str(installed), "graph", "explain", "no_such_thing_anywhere"]) == 4
    capsys.readouterr()
    assert main(["--repo", str(installed), "--json", "graph", "path", "src/api/router.ts", "src/auth/tokens.ts"]) in (0, 4)
    out = json.loads(capsys.readouterr().out)
    assert "hops" in out or out.get("path") is None


def test_update_changed_reextracts_only_what_git_reports(installed: Path, capsys) -> None:
    subprocess.run(["git", "init", "-q"], cwd=installed, check=True)
    subprocess.run(["git", "add", "-A"], cwd=installed, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"], cwd=installed, check=True
    )
    assert main(["--repo", str(installed), "--quiet", "graph", "build"]) == 0
    capsys.readouterr()
    assert main(["--repo", str(installed), "--json", "graph", "update", "--changed"]) == 0
    assert json.loads(capsys.readouterr().out) == {"changed": []}

    (installed / "src" / "auth" / "extra.py").write_text("def brand_new_helper():\n    return 1\n", encoding="utf-8")
    assert main(["--repo", str(installed), "--json", "graph", "update", "--changed"]) == 0
    assert json.loads(capsys.readouterr().out)["dirs"] == ["src/auth"]
    assert main(["--repo", str(installed), "--quiet", "graph", "where", "brand_new_helper"]) == 0
    # References out of the re-extracted directory still resolve.
    store = GraphStore(Layout(installed))
    assert any(e.relation in ("imports", "references") for e in store.edges)
