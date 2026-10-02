"""`edify license`: status, activate and deactivate, with no purchase and no price."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edify.cli import main


def run(repo: Path, *args: str) -> int:
    return main(["--repo", str(repo), *args])


def run_json(capsys: pytest.CaptureFixture[str], repo: Path, *args: str):
    code = main(["--repo", str(repo), "--json", *args])
    out = capsys.readouterr().out
    return code, json.loads(out) if out.strip() else None


def test_free_status_names_activate_and_no_price(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    assert run(tmp_path, "license", "status") == 0
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert "$" not in text
    assert "edify license activate" in text


def test_license_projects_is_gone(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        run(tmp_path, "license", "projects")
    assert exc.value.code == 2


def test_status_json_still_carries_the_retired_caps_as_null(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code, data = run_json(capsys, tmp_path, "license", "status")
    assert code == 0
    assert data["node_cap"] is None
    assert data["project_cap"] is None
