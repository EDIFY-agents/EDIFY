"""Typed hand-backs, lease ownership, the orchestrator's status view, and the cost
of reading leases."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from edify import swarm
from edify.cli import main
from edify.graph import extract, queries
from edify.graph.store import GraphStore
from edify.paths import Layout

from test_swarm import TASKS, claimed, feature, run  # noqa: F401  (fixture)


def board(root: Path, capsys) -> dict[str, dict]:
    capsys.readouterr()
    main(["--repo", str(root), "--json", "swarm", "board", "demo"])
    return {r["task"]: r for r in json.loads(capsys.readouterr().out)}


@pytest.mark.parametrize("status", ["partial", "failed", "needs_input"])
def test_a_non_completed_handback_is_a_block_never_a_done(feature: Path, capsys, status: str) -> None:
    assert claimed(feature, capsys, "--agent", "a") == "T-1"
    # A non-completed hand-back must say why.
    assert run(feature, "swarm", "done", "T-1", "demo", "--agent", "a", "--status", status) == 2
    assert run(feature, "swarm", "done", "T-1", "demo", "--agent", "a", "--status", status,
               "--reason", "fixture missing") == 0
    rows = board(feature, capsys)
    assert rows["T-1"]["state"] == "blocked"
    assert rows["T-1"]["status"] == status
    assert rows["T-1"]["why"] == "fixture missing"
    assert "Status — **done**" not in (feature / "specs" / "demo" / "tasks.md").read_text(encoding="utf-8")
    # Nothing downstream unblocked.
    assert claimed(feature, capsys, "--agent", "b") is None


def test_completed_is_the_default_and_shows_on_the_board(feature: Path, capsys) -> None:
    assert claimed(feature, capsys, "--agent", "a") == "T-1"
    assert run(feature, "swarm", "done", "T-1", "demo", "--agent", "a", "--status", "partial", "--reason", "half") == 0
    # A later completed hand-back clears the block.
    assert run(feature, "swarm", "done", "T-1", "demo", "--agent", "a") == 0
    rows = board(feature, capsys)
    assert rows["T-1"]["state"] == "done" and rows["T-1"]["status"] == "completed"


def test_handback_is_fenced_like_done(feature: Path, capsys) -> None:
    assert claimed(feature, capsys, "--agent", "a") == "T-1"
    assert run(feature, "swarm", "done", "T-1", "demo", "--agent", "b", "--status", "failed", "--reason", "x") == 1
    assert board(feature, capsys)["T-1"]["state"] == "leased"


def test_release_by_a_non_holder_needs_force(feature: Path, capsys) -> None:
    assert claimed(feature, capsys, "--agent", "a") == "T-1"
    assert run(feature, "swarm", "release", "T-1", "demo", "--agent", "b") == 1
    assert board(feature, capsys)["T-1"]["state"] == "leased"
    assert run(feature, "swarm", "release", "T-1", "demo", "--agent", "b", "--force") == 0
    assert board(feature, capsys)["T-1"]["state"] == "ready"
    assert run(feature, "swarm", "release", "T-1", "demo", "--agent", "a") == 1  # nothing left to release


def test_holder_releases_and_a_lapsed_lease_is_anyones_to_release(feature: Path, capsys) -> None:
    assert claimed(feature, capsys, "--agent", "a") == "T-1"
    assert run(feature, "swarm", "release", "T-1", "demo", "--agent", "a") == 0
    assert claimed(feature, capsys, "--agent", "a", "--ttl", "0") == "T-1"
    assert run(feature, "swarm", "release", "T-1", "demo", "--agent", "b") == 0


def test_renew_respects_ownership(feature: Path, capsys) -> None:
    assert claimed(feature, capsys, "--agent", "a", "--ttl", "0") == "T-1"
    # A lapsed lease nobody took is renewable by its holder...
    assert run(feature, "swarm", "renew", "T-1", "demo", "--agent", "a", "--ttl", "30") == 0
    assert run(feature, "swarm", "renew", "T-1", "demo", "--agent", "b") == 1
    # ...but once it lapses and someone else claims it, the old holder cannot renew over them.
    assert run(feature, "swarm", "renew", "T-1", "demo", "--agent", "a", "--ttl", "0") == 0
    assert claimed(feature, capsys, "--agent", "b") == "T-1"
    assert run(feature, "swarm", "renew", "T-1", "demo", "--agent", "a") == 1
    assert board(feature, capsys)["T-1"]["agent"] == "b"


def test_block_by_a_non_holder_needs_force(feature: Path, capsys) -> None:
    assert claimed(feature, capsys, "--agent", "a") == "T-1"
    assert run(feature, "swarm", "block", "T-1", "demo", "--agent", "b", "--reason", "r") == 1
    assert run(feature, "swarm", "block", "T-1", "demo", "--agent", "b", "--reason", "r", "--force") == 0


def test_status_is_one_line_per_agent(feature: Path, capsys) -> None:
    assert claimed(feature, capsys, "--agent", "alice", "--ttl", "5") == "T-1"
    capsys.readouterr()
    assert main(["--repo", str(feature), "--json", "swarm", "status", "demo", "--soon", "10"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [a["agent"] for a in data["agents"]] == ["alice"]
    assert data["agents"][0]["tasks"] == ["T-1"] and data["agents"][0]["flag"] == "expiring"
    assert data["done"] == 0 and data["total"] == 4

    assert run(feature, "swarm", "done", "T-1", "demo", "--agent", "alice") == 0
    assert claimed(feature, capsys, "--agent", "carol") == "T-2"
    assert claimed(feature, capsys, "--agent", "bob", "--ttl", "0") == "T-4"
    capsys.readouterr()
    assert main(["--repo", str(feature), "swarm", "status", "demo"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].startswith("demo: 2 agents · 2 leased (0 expiring, 1 lapsed) · 0 blocked · 1/4 done")
    bob = next(line for line in lines if line.startswith("bob"))
    assert "lapsed" in bob and "reclaimable" in bob
    assert any(line.startswith("carol") and "expires in" in line for line in lines)


def test_lease_survives_a_round_trip_with_status_and_a_multiline_reason() -> None:
    lease = swarm.Lease("T-9", "a", 1, 2, ["x.py"], "line one\nline two", "needs_input")
    back = swarm.Lease.load(lease.dump())
    assert back.status == "needs_input" and back.reason == "line one line two" and back.files == ["x.py"]
    # A lease written before `status` existed still loads.
    assert swarm.Lease.load("task=T-1\nagent=a\nsince=1\nexpires=2\nfiles=\nreason=\n").status == ""


def test_blast_radius_matches_dependent_files(repo: Path) -> None:
    layout = Layout(repo)
    layout.edify.mkdir(parents=True, exist_ok=True)
    extract.build(layout)
    graph = GraphStore(layout)
    blast = swarm.BlastRadius(graph)
    files = sorted({n.file for n in graph.nodes if n.file})
    assert len(files) >= 3
    for f in files:
        assert blast.of([f]) == queries.dependent_files(graph, [f], depth=1)
    assert blast.of(files[:2]) == queries.dependent_files(graph, files[:2], depth=1)
    # The import chain is really there, so the comparison is not vacuous.
    assert blast.of(["src/auth/tokens.ts"]) > {"src/auth/tokens.ts"}


def test_board_scans_the_edges_once(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from edify.formats import tasks as tasks_format

    layout = Layout(repo)
    layout.edify.mkdir(parents=True, exist_ok=True)
    extract.build(layout)
    graph = GraphStore(layout)
    path = repo / "tasks.md"
    path.write_text(TASKS, encoding="utf-8")
    parsed = tasks_format.parse(path, "tasks.md")
    leases = swarm._empty()
    leases["leased"]["T-1"] = swarm.Lease("T-1", "a", 0, 2**40, ["src/contract.py"])

    reads = 0
    edges = GraphStore.edges

    def counting(self):
        nonlocal reads
        reads += 1
        return edges.fget(self)

    monkeypatch.setattr(GraphStore, "edges", property(counting))
    swarm.board(parsed, leases, graph)
    assert reads == 1


def test_git_store_costs_one_fetch_per_claim(feature: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                             capsys) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-q"], cwd=feature, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=feature, check=True)

    calls: list[str] = []
    real = swarm._git

    def spy(root, *args, **kw):
        calls.append(args[0])
        return real(root, *args, **kw)

    monkeypatch.setattr(swarm, "_git", spy)
    capsys.readouterr()
    main(["--repo", str(feature), "--json", "swarm", "--git", "claim", "demo", "--agent", "alice"])
    assert json.loads(capsys.readouterr().out)["claimed"] == "T-1"
    assert calls.count("fetch") == 1 and calls.count("push") == 1

    calls.clear()
    assert run(feature, "swarm", "--git", "done", "T-1", "demo", "--agent", "alice") == 0
    # One read, one atomic move leased → done.
    assert calls.count("fetch") == 1 and calls.count("push") == 1
    store = swarm.GitStore(feature, "demo")
    monkeypatch.setattr(swarm, "_git", real)
    state = store.all()
    assert "T-1" in state["done"] and not state["leased"]
    assert state["done"]["T-1"].status == "completed"
