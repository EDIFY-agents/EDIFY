"""`edify swarm merge`: done branches in phase → wave → task order, landed with
`git merge --no-ff`, stopping cleanly at the first conflict."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from edify import swarm
from edify.cli import main
from edify.formats.tasks import Task

from test_swarm import feature, run  # noqa: F401  (fixture)

SHARED = "".join(f"line {i}\n" for i in range(1, 21))


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


def branch(root: Path, name: str, files: dict[str, str]) -> None:
    git(root, "checkout", "-q", "-b", name, "main")
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", name)
    git(root, "checkout", "-q", "main")


def edit(line: int, text: str) -> str:
    lines = SHARED.splitlines(keepends=True)
    lines[line - 1] = text + "\n"
    return "".join(lines)


@pytest.fixture
def swarm_repo(feature: Path, monkeypatch: pytest.MonkeyPatch) -> Path:  # noqa: F811
    for key in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{key}_NAME", "test")
        monkeypatch.setenv(f"GIT_{key}_EMAIL", "test@example.invalid")
    (feature / "src" / "shared.py").write_text(SHARED, encoding="utf-8")
    git(feature, "init", "-q", "-b", "main")
    git(feature, "add", "-A")
    git(feature, "commit", "-q", "-m", "base")
    return feature


def plan(root: Path, capsys, *args: str) -> tuple[int, dict]:
    capsys.readouterr()
    code = main(["--repo", str(root), "--json", "swarm", "merge", "demo", *args])
    return code, json.loads(capsys.readouterr().out)


def finish(root: Path, *ids: str) -> None:
    for task_id in ids:
        assert run(root, "swarm", "done", task_id, "demo", "--agent", "w") == 0


def test_order_is_phase_then_waves_and_apply_lands_every_branch(swarm_repo: Path, capsys) -> None:
    branch(swarm_repo, "swarm/T-1", {"src/contract.py": "X = 1\n"})
    branch(swarm_repo, "swarm/T-2", {"src/shared.py": edit(2, "A")})
    branch(swarm_repo, "swarm/T-3", {"src/shared.py": edit(18, "B")})
    branch(swarm_repo, "swarm/T-4", {"src/other.py": "Y = 2\n", "src/stray.py": "Z = 3\n"})
    finish(swarm_repo, "T-1", "T-2", "T-3", "T-4")

    code, data = plan(swarm_repo, capsys)
    assert code == 0
    order = [(s["task"], s["wave"], s["after"]) for s in data["order"]]
    # T-2 and T-4 share no radius: one wave. T-3 shares src/shared.py with T-2: after it.
    assert order == [("T-1", 0, []), ("T-2", 1, []), ("T-4", 1, []), ("T-3", 2, ["T-2"])]
    stray = next(s for s in data["order"] if s["task"] == "T-4")
    assert stray["undeclared"] == ["src/stray.py"]
    assert not any(s["merged"] for s in data["order"])

    code, data = plan(swarm_repo, capsys, "--apply")
    assert code == 0 and data["merged"] == ["T-1", "T-2", "T-4", "T-3"] and data["conflict"] is None
    shared = (swarm_repo / "src" / "shared.py").read_text(encoding="utf-8")
    assert "A\n" in shared and "B\n" in shared
    merges = git(swarm_repo, "log", "--merges", "--format=%s").splitlines()
    assert merges[0].startswith("swarm: merge T-3") and len(merges) == 4

    # Idempotent: a second run has nothing left to land.
    code, data = plan(swarm_repo, capsys, "--apply")
    assert code == 0 and data["merged"] == [] and all(s["merged"] for s in data["order"])


def test_apply_stops_at_the_first_conflict_and_names_task_and_files(swarm_repo: Path, capsys) -> None:
    branch(swarm_repo, "swarm/T-1", {"src/contract.py": "X = 1\n"})
    branch(swarm_repo, "swarm/T-2", {"src/shared.py": edit(5, "from A")})
    branch(swarm_repo, "swarm/T-3", {"src/shared.py": edit(5, "from B")})
    branch(swarm_repo, "swarm/T-4", {"src/other.py": "Y = 2\n"})
    finish(swarm_repo, "T-1", "T-2", "T-3", "T-4")

    code, data = plan(swarm_repo, capsys, "--apply")
    assert code == 1
    assert data["merged"] == ["T-1", "T-2", "T-4"]
    assert data["conflict"]["task"] == "T-3" and data["conflict"]["files"] == ["src/shared.py"]
    # The merge was aborted: no half-merged tree is left behind.
    assert subprocess.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=swarm_repo).returncode != 0
    assert "<<<<<<<" not in (swarm_repo / "src" / "shared.py").read_text(encoding="utf-8")

    capsys.readouterr()
    assert main(["--repo", str(swarm_repo), "swarm", "merge", "demo", "--apply"]) == 1
    err = capsys.readouterr().err
    assert "T-3 (swarm/T-3)" in err and "src/shared.py" in err


def test_only_done_tasks_with_branches_are_listed(swarm_repo: Path, capsys) -> None:
    branch(swarm_repo, "swarm/T-2", {"src/shared.py": edit(2, "A")})
    finish(swarm_repo, "T-1")  # done, but no branch
    code, data = plan(swarm_repo, capsys)
    assert code == 0 and data["order"] == [] and data["missing"] == ["T-1"]


def test_graph_dependents_serialise_tasks_with_disjoint_files() -> None:
    def task(tid: str, phase: int) -> Task:
        return Task(tid, tid, 1, 1, phase=phase)

    blast = swarm.BlastRadius(None)
    blast.incoming = {"lib.py": {"app.py"}}  # app.py imports lib.py
    items = [(task("T-1", 3), ["lib.py"]), (task("T-2", 3), ["app.py"]), (task("T-3", 3), ["docs.py"]),
             (task("T-0", 1), ["base.py"])]
    index = {"T-0": 0, "T-1": 1, "T-2": 2, "T-3": 3}
    steps = swarm.merge_order(items, blast, index)
    assert [(s.task.id, s.wave, s.after) for s in steps] == [
        ("T-0", 0, []), ("T-1", 1, []), ("T-3", 1, []), ("T-2", 2, ["T-1"]),
    ]
