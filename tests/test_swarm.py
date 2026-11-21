"""Swarm leases: one claimant wins, phases gate, overlapping tasks never run at once."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from edify.cli import main

TASKS = """---
feature: demo
status: approved
---

# tasks — demo

## Phase 1 · Contracts

### T-1 · Freeze the contract
Phase 1 · Role implementer · Skill implementer-general · Size s
Discharges REQ-1
Depends on — · Parallel with —

Files

| path | range | action |
|---|---|---|
| src/contract.py | — | new |

Done when
- `pytest -q` passes

## Phase 3 · Core

### T-2 · Build part A
Phase 3 · Role implementer · Skill implementer-general · Size s
Discharges REQ-2
Depends on T-1 · Parallel with T-4

Files

| path | range | action |
|---|---|---|
| src/shared.py | 1-10 | edit |

Done when
- `pytest -q` passes

### T-3 · Build part B, same file as A
Phase 3 · Role implementer · Skill implementer-general · Size s
Discharges REQ-3
Depends on T-1 · Parallel with —

Files

| path | range | action |
|---|---|---|
| src/shared.py | 12-20 | edit |

Done when
- `pytest -q` passes

### T-4 · Build part C, elsewhere
Phase 3 · Role implementer · Skill implementer-general · Size s
Discharges REQ-4
Depends on T-1 · Parallel with T-2

Files

| path | range | action |
|---|---|---|
| src/other.py | — | new |

Done when
- `pytest -q` passes

## Decisions

| # | decision | why | binds |
|---|---|---|---|
"""


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def feature(installed: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    (installed / "specs" / "demo").mkdir(parents=True)
    (installed / "specs" / "demo" / "tasks.md").write_text(TASKS, encoding="utf-8")
    monkeypatch.setenv("EDIFY_SWARM_DIR", str(tmp_path / "leases"))
    return installed


def run(root: Path, *args: str) -> int:
    return main(["--repo", str(root), "--quiet", *args])


def claimed(root: Path, capsys, *args: str) -> str | None:
    capsys.readouterr()
    main(["--repo", str(root), "--json", "swarm", "claim", "demo", *args])
    return json.loads(capsys.readouterr().out)["claimed"]


def test_phase_gate_then_parallel_claims_avoid_overlap(feature: Path, capsys) -> None:
    assert claimed(feature, capsys, "--agent", "a") == "T-1"
    # Every phase-3 task waits on T-1.
    assert claimed(feature, capsys, "--agent", "b") is None
    assert run(feature, "swarm", "done", "T-1", "demo", "--agent", "a") == 0

    first = claimed(feature, capsys, "--agent", "a")
    second = claimed(feature, capsys, "--agent", "b")
    assert {first, second} == {"T-2", "T-4"}
    # T-3 edits the file T-2 holds: it waits rather than colliding.
    assert claimed(feature, capsys, "--agent", "c") is None

    holder = "a" if first == "T-2" else "b"
    assert run(feature, "swarm", "done", "T-2", "demo", "--agent", holder) == 0
    assert claimed(feature, capsys, "--agent", "c") == "T-3"


def test_done_writes_the_status_line_once(feature: Path) -> None:
    assert run(feature, "swarm", "claim", "demo", "--agent", "a") == 0
    assert run(feature, "swarm", "done", "T-1", "demo", "--agent", "a") == 0
    assert run(feature, "swarm", "done", "T-1", "demo", "--agent", "a") == 0
    text = (feature / "specs" / "demo" / "tasks.md").read_text(encoding="utf-8")
    assert text.count("Status — **done**") == 1


def test_expired_lease_is_reclaimable_and_fenced(feature: Path, capsys) -> None:
    assert claimed(feature, capsys, "--agent", "a", "--ttl", "0") == "T-1"
    assert claimed(feature, capsys, "--agent", "b") == "T-1"
    # The worker that lost its lease cannot record done over the new holder.
    assert run(feature, "swarm", "done", "T-1", "demo", "--agent", "a") == 1
    assert run(feature, "swarm", "done", "T-1", "demo", "--agent", "b") == 0


def test_block_needs_a_reason_and_frees_the_task(feature: Path, capsys) -> None:
    assert run(feature, "swarm", "claim", "demo") == 0
    assert run(feature, "swarm", "block", "T-1", "demo") == 2
    assert run(feature, "swarm", "block", "T-1", "demo", "--reason", "contract unclear") == 0
    capsys.readouterr()
    main(["--repo", str(feature), "--json", "swarm", "board", "demo"])
    rows = {r["task"]: r for r in json.loads(capsys.readouterr().out)}
    assert rows["T-1"]["state"] == "blocked"


def test_prompt_carries_skill_task_and_loop(feature: Path, capsys) -> None:
    capsys.readouterr()
    assert main(["--repo", str(feature), "swarm", "prompt", "T-2", "demo"]) == 0
    text = capsys.readouterr().out
    assert "implementer-general.md" in text
    assert "### T-2 · Build part A" in text
    assert "edify swarm done T-2 demo" in text


def test_git_store_lets_exactly_one_machine_claim(feature: Path, tmp_path: Path, capsys) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    _git(feature, "init", "-q")
    _git(feature, "remote", "add", "origin", str(remote))
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True, capture_output=True)
    (other / "specs" / "demo").mkdir(parents=True)
    (other / "specs" / "demo" / "tasks.md").write_text(TASKS, encoding="utf-8")
    (other / ".edify").mkdir()

    capsys.readouterr()
    main(["--repo", str(feature), "--json", "swarm", "--git", "claim", "demo", "--agent", "alice"])
    assert json.loads(capsys.readouterr().out)["claimed"] == "T-1"
    main(["--repo", str(other), "--json", "swarm", "--git", "claim", "demo", "--agent", "bob"])
    assert json.loads(capsys.readouterr().out)["claimed"] is None
