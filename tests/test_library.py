"""The shipped methodology tree checks itself.

Everything EDIFY asks of a customer's repository, it has to satisfy in its own: the
skill files are valid and under budget, the command files are short, the worked
examples parse against the formats they calibrate, and the default registry is
pinned and scoped.
"""

from __future__ import annotations

import pytest

from edify import assets
from edify.formats import mcp as mcp_format
from edify.formats import skill as skill_format
from edify.formats import tasks as tasks_format
from edify.formats.document import parse_document

SKILLS = sorted(assets.subtree("skills").glob("*.md"))
COMMANDS = sorted(assets.subtree("commands").glob("*.md"))


def test_the_library_is_not_empty() -> None:
    assert len(SKILLS) >= 10
    assert {p.stem for p in COMMANDS} == {"spec", "plan", "tasks", "verify"}


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.stem)
def test_every_skill_is_valid_and_under_budget(path) -> None:
    skill = skill_format.parse(path, path.name)
    problems = skill_format.validate(skill)
    assert problems == [], problems
    assert skill.name == path.stem, "the filename and the `name` field have to agree"


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.stem)
def test_no_skill_commands_or_claims_an_identity(path) -> None:
    """P5: instructions explain, they do not command."""
    text = path.read_text(encoding="utf-8")
    body = text.split("---", 2)[-1]
    for banned in ("MUST ", "YOU MUST", "NEVER FORGET", "You are an expert", "As an expert"):
        assert banned not in body, f"{path.name} contains `{banned}`"


@pytest.mark.parametrize("path", COMMANDS, ids=lambda p: p.stem)
def test_every_command_file_is_short(path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 100, f"{path.name} is {len(lines)} lines; the budget is 100"


def test_every_role_has_at_least_one_entry() -> None:
    roles = {skill_format.parse(p, p.name).role for p in SKILLS}
    assert set(skill_format.ROLES) <= roles


def test_the_worked_spec_example_is_a_clean_instance_of_its_format(tmp_path) -> None:
    """The spec example is the same feature as the tasks example, and checks clean.

    It carries spec-kit's sections (user stories with Given/When/Then, key entities,
    success criteria, assumptions) on top of the five `edify check` requires, and every
    id the task list discharges exists in it.
    """
    from edify.formats import check as check_format
    from edify.formats import spec as spec_format

    source = assets.subtree("formats") / "spec.example.md"
    text = source.read_text(encoding="utf-8")
    assert "worked example for `spec.format.md`" in text.lower()
    spec = spec_format.parse(source, source.name)
    assert [f for f in check_format.check_spec(spec) if f.level.name == "ERROR"] == []
    for section in ("User stories", "Key entities", "Success criteria", "Assumptions"):
        assert spec.doc.section(section) is not None, section
    assert "**Given**" in text and "**Then**" in text

    tasks = tasks_format.parse(assets.subtree("formats") / "tasks.example.md")
    known = spec.requirement_ids() | spec.assertion_ids() | spec.checklist_ids()
    for task in tasks.tasks:
        assert set(task.discharges) <= known, (task.id, set(task.discharges) - known)


def test_every_design_file_has_a_worked_example() -> None:
    formats = assets.subtree("formats")
    for name in ("research", "data-model", "contracts", "quickstart"):
        example = formats / f"{name}.example.md"
        assert example.is_file(), name
        assert "design.format.md" in example.read_text(encoding="utf-8"), name
    assert (formats / "constitution.format.md").is_file()
    assert (formats / "README.md").is_file()


def test_the_worked_tasks_example_parses_completely() -> None:
    source = assets.subtree("formats") / "tasks.example.md"
    parsed = tasks_format.parse(source)

    assert len(parsed.tasks) == 16
    assert len(parsed.phases) == 8
    assert len(parsed.coverage) == 13

    for task in parsed.tasks:
        assert task.phase is not None, f"{task.id} has no phase"
        assert task.discharges, f"{task.id} discharges nothing"
        assert task.steps, f"{task.id} has no steps"
        assert task.done_when, f"{task.id} has no done-check"

    phase_two = parsed.in_phase(2)
    assert phase_two
    for task in phase_two:
        assert task.verification, f"{task.id} names no verification kinds"
        assert any("fail" in check.lower() for check in task.done_when)


def test_the_worked_tasks_example_has_no_whole_file_edits() -> None:
    parsed = tasks_format.parse(assets.subtree("formats") / "tasks.example.md")
    for task in parsed.tasks:
        for ref in task.edits:
            assert ref.has_range, f"{task.id} edits {ref.path} with no line range"


def test_the_worked_plan_example_obeys_its_format() -> None:
    from edify.formats import plan as plan_format

    parsed = plan_format.parse(assets.subtree("formats") / "plan.example.md")
    keys = {s.key for s in parsed.doc.sections}
    for name in plan_format.EXPECTED_SECTIONS:
        assert any(k.startswith(name) for k in keys), f"no `## {name}` section"
    assert parsed.milestones and parsed.decisions and parsed.seeds
    for decision in parsed.decisions:
        assert decision.version[:1].isdigit(), f"{decision.id} has no exact version"
    assert all(seed.has_range for seed in parsed.seeds)
    assert parsed.verification_budget


def test_the_default_registry_is_scoped() -> None:
    registry = mcp_format.parse(assets.subtree("mcp") / "default-registry.md")
    assert len(registry.servers) == 1
    docs = registry.get("docs")
    assert docs is not None
    assert docs.roles and docs.phases
    # A phase 0 foundation task loads nothing; a phase 4 implementer loads docs.
    assert not docs.scoped_to("planner", "0")
    assert docs.scoped_to("implementer", "4")


def test_the_manifest_declares_what_it_pins() -> None:
    manifest = assets.manifest()
    assert manifest["edify"]
    assert manifest["graph-schema"] == "1"
    assert manifest["extractor"] == "builtin"


def test_the_version_has_one_source_and_two_readers() -> None:
    """`__init__` holds the version; `pyproject.toml` and the manifest read the same one.

    A release where they disagree ships a wheel whose `edify version` and whose
    `pip show` are different numbers, and every governance row it writes is stamped
    with the wrong one.
    """
    import re
    from pathlib import Path

    from edify import __version__

    root = Path(__file__).resolve().parent.parent
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^dynamic = \["version"\]', text, re.M), "pyproject.toml does not read the version"
    assert 'path = "src/edify/__init__.py"' in text
    assert assets.manifest()["edify"] == __version__
