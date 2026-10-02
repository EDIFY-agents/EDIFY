"""An older edify meeting what a newer one wrote: warn, never crash, never fail a build.

A team shares one repository across machines that do not upgrade on the same day.
Whatever 0.2.0 finds that a later version wrote — a ledger origin it has never heard
of, a frontmatter key it does not know, a `.edify/team/` folder with no team package
to read it — is reported as something it cannot judge, and the exit code stays 0.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from edify import governance
from edify.cli import main
from edify.paths import Layout
from edify.tsv import write_rows


def run(repo: Path, *args: str) -> int:
    return main(["--repo", str(repo), *args])


def test_a_newer_ledger_origin_is_reported_and_not_serious(installed: Path) -> None:
    layout = Layout(installed)
    rows = governance.load(layout)
    changed = dataclasses.replace(rows[0], origin="team-v9")
    rows = [changed, *rows[1:]]
    write_rows(layout.governance, [r.row() for r in rows], governance.LEDGER_HEADER)

    problems = governance.verify(layout)
    assert [(p.path, p.state) for p in problems] == [(changed.path, "unknown-origin")]
    assert not problems[0].serious
    assert "newer edify" in problems[0].detail
    assert run(installed, "governance", "verify", "--exit-code") == 0


def test_an_unknown_skill_field_is_a_warning(capsys, installed: Path) -> None:
    skill = installed / ".edify" / "skills" / "planner.md"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    skill.write_text("---\nserves: O-1\n" + text[len("---\n"):], encoding="utf-8")
    capsys.readouterr()

    assert run(installed, "check", "--exit-code") == 0
    assert "skill-unknown-field" in capsys.readouterr().out


def test_a_team_folder_without_the_team_package_is_left_alone(installed: Path) -> None:
    team = installed / ".edify" / "team"
    (team / "journal").mkdir(parents=True)
    (team / "goal.md").write_text("# Goal\n\nShip the thing.\n", encoding="utf-8")
    (team / "journal" / "2026-09-28-ada.md").write_text("- started on the thing\n", encoding="utf-8")

    assert run(installed, "check", "--exit-code") == 0
    assert run(installed, "governance", "verify", "--exit-code") == 0
