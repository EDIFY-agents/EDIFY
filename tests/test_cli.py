"""The CLI end to end: init, the queries, resolution, scoping, doctor, check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edify import skills as skills_index
from edify.cli import main
from edify.paths import Layout


def run(repo: Path, *args: str) -> int:
    return main(["--repo", str(repo), *args])


def run_json(capsys: pytest.CaptureFixture[str], repo: Path, *args: str):
    code = main(["--repo", str(repo), "--json", *args])
    out = capsys.readouterr().out
    return code, json.loads(out) if out.strip() else None


# -- init ------------------------------------------------------------------


def test_init_writes_the_installed_tree(installed: Path) -> None:
    layout = Layout(installed)
    assert layout.nodes.is_file()
    assert layout.edges.is_file()
    assert layout.meta.is_file()
    assert layout.skills_index.is_file()
    assert layout.mcp.is_file()
    assert layout.conventions.is_file()
    assert layout.claude_md.is_file()
    assert (layout.commands_dir / "spec.md").is_file()
    assert (layout.formats_dir / "tasks.example.md").is_file()


def test_init_installs_an_entry_for_every_part_of_the_stack(installed: Path) -> None:
    names = {p.stem for p in Layout(installed).skills_dir.glob("*.md")}
    # The fixture is genuinely polyglot — TypeScript, Python, SQL, express, postgres.
    assert {"implementer-node", "implementer-postgres", "implementer-python"} <= names
    # Nothing in it is Go or React, so neither entry is installed.
    assert "implementer-go" not in names
    assert "implementer-react" not in names
    # Every repository needs the role entries that apply regardless of stack.
    assert {"planner", "adversary", "verifier", "debugger"} <= names


def test_a_single_stack_repository_gets_only_its_own_entries(tmp_path: Path) -> None:
    """A Python API repository does not receive the React implementer.

    Every unused skill file is context cost and, for anything sourced from outside,
    attack surface.
    """
    root = tmp_path / "api"
    (root / "app").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "api"\ndependencies = ["fastapi", "sqlalchemy"]\n', encoding="utf-8"
    )
    for name in ("main", "models", "routes"):
        (root / "app" / f"{name}.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    assert run(root, "--quiet", "init") == 0
    names = {p.stem for p in Layout(root).skills_dir.glob("*.md")}
    assert "implementer-python" in names
    assert names.isdisjoint({"implementer-node", "implementer-react", "implementer-go"})


def test_claude_md_is_short_and_points_at_the_graph(installed: Path) -> None:
    text = Layout(installed).claude_md.read_text(encoding="utf-8")
    assert ".edify/graph/" in text
    assert "edify graph where" in text
    body = [line for line in text.splitlines() if line.strip() and not line.startswith("<!--")]
    assert len(body) <= 20


def test_init_merges_into_an_existing_instruction_file(repo: Path) -> None:
    (repo / "CLAUDE.md").write_text("# Our house rules\nSomebody wrote this on purpose.\n", encoding="utf-8")
    assert run(repo, "--quiet", "init") == 0

    text = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Our house rules" in text
    assert "Somebody wrote this on purpose." in text
    assert ".edify/graph/" in text


def test_re_running_init_replaces_only_the_edify_block(repo: Path) -> None:
    (repo / "CLAUDE.md").write_text("# Ours\nkeep me\n", encoding="utf-8")
    run(repo, "--quiet", "init")
    first = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    run(repo, "--quiet", "init", "--force")
    second = (repo / "CLAUDE.md").read_text(encoding="utf-8")

    assert second.count("<!-- edify:begin -->") == 1
    assert "keep me" in second
    assert first.count("<!-- edify:begin -->") == 1


def test_init_writes_host_command_pointers(installed: Path) -> None:
    pointer = installed / ".claude" / "commands" / "spec.md"
    assert pointer.is_file()
    text = pointer.read_text(encoding="utf-8")
    assert ".edify/commands/spec.md" in text
    # A pointer carries no methodology, so it cannot go stale.
    assert len(text.splitlines()) < 10


def test_conventions_are_scraped_from_the_config_files(installed: Path) -> None:
    text = Layout(installed).conventions.read_text(encoding="utf-8")
    assert "vitest" in text
    assert "strict on" in text
    assert "npm run test" in text
    assert "No model produced any line here" in text


# -- queries ---------------------------------------------------------------


def test_graph_where_prints_a_file_and_line(capsys: pytest.CaptureFixture[str], installed: Path) -> None:
    assert run(installed, "graph", "where", "generate") == 0
    assert "src/auth/tokens.ts:3" in capsys.readouterr().out


def test_graph_where_reports_a_miss_without_inventing_one(
    capsys: pytest.CaptureFixture[str], installed: Path
) -> None:
    assert run(installed, "graph", "where", "definitelyNotHere") == 1
    assert "nothing named" in capsys.readouterr().out


def test_json_output_is_machine_readable(capsys: pytest.CaptureFixture[str], installed: Path) -> None:
    code, payload = run_json(capsys, installed, "graph", "where", "MemberService")
    assert code == 0
    assert payload[0]["file"] == "src/api/members.ts"
    assert payload[0]["kind"] == "symbol"


def test_overlap_exits_non_zero_when_sets_intersect(installed: Path) -> None:
    assert run(installed, "graph", "overlap", "src/auth/tokens.ts", "src/api/members.ts") == 1
    assert run(installed, "graph", "overlap", "src/tools.py", "src/api/router.ts") == 0


# -- resolution and scoping ------------------------------------------------


def test_skills_resolve_returns_one_path(capsys: pytest.CaptureFixture[str], installed: Path) -> None:
    assert run(installed, "skills", "resolve", "implementer", "4") == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert out[0].endswith(".md")


def test_resolution_prefers_the_stack_then_any(installed: Path) -> None:
    layout = Layout(installed)
    assert skills_index.resolve(layout, "implementer", "4", "typescript").name == "implementer-node"
    assert skills_index.resolve(layout, "implementer", "4", "cobol").name == "implementer-general"
    assert skills_index.resolve(layout, "verifier", "7").name == "verifier"


def test_a_role_with_no_skill_fails_rather_than_guessing(installed: Path) -> None:
    from edify.errors import EdifyError

    with pytest.raises(EdifyError):
        skills_index.resolve(Layout(installed), "archaeologist", "3")


def test_mcp_scoping_is_exact(capsys: pytest.CaptureFixture[str], installed: Path) -> None:
    assert run(installed, "mcp", "for", "implementer", "4") == 0
    assert "docs" in capsys.readouterr().out

    assert run(installed, "mcp", "for", "planner", "0") == 0
    assert "none" in capsys.readouterr().out


# -- check and doctor ------------------------------------------------------


def test_check_on_a_fresh_install_reports_nothing(
    capsys: pytest.CaptureFixture[str], installed: Path
) -> None:
    assert run(installed, "check") == 0
    assert "0 errors" in capsys.readouterr().out


def test_check_never_blocks_unless_asked(installed: Path) -> None:
    feature = installed / "specs" / "broken"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text("# spec — broken\n\nnothing here\n", encoding="utf-8")

    assert run(installed, "check") == 0                 # reports, does not block
    assert run(installed, "check", "--exit-code") == 2  # the customer's own gate


def test_doctor_reports_each_part(capsys: pytest.CaptureFixture[str], installed: Path) -> None:
    assert run(installed, "doctor") == 0
    out = capsys.readouterr().out
    for part in ("install", "extractor", "graph", "skills", "CLAUDE.md", "license"):
        assert part in out


def test_doctor_is_red_before_init(capsys: pytest.CaptureFixture[str], repo: Path) -> None:
    assert run(repo, "doctor") == 1
    assert "edify init" in capsys.readouterr().out


def test_a_command_needing_the_graph_says_so_before_init(
    capsys: pytest.CaptureFixture[str], repo: Path
) -> None:
    assert run(repo, "graph", "where", "generate") == 4
    assert "edify graph build" in capsys.readouterr().err


def test_upgrade_is_not_gated(capsys: pytest.CaptureFixture[str], installed: Path) -> None:
    # 1, not 7: the command ran on the free plan and failed on its own terms.
    assert run(installed, "upgrade", "--archive", "nope.zip") == 1
    assert "is not a file" in capsys.readouterr().err


def test_version_needs_no_repository(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert main(["--repo", str(tmp_path), "version"]) == 0
    assert "edify" in capsys.readouterr().out


# -- the command line itself ------------------------------------------------


def _every_handler(parser):
    """`(name, func)` for every leaf command in the parser."""
    import argparse

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                func = sub.get_default("func")
                if func is not None:
                    yield name, func
                yield from _every_handler(sub)


def test_every_handler_names_a_function_that_exists() -> None:
    """The dispatch table is strings; a typo in one would only show when that command
    ran. So every one is resolved here."""
    import importlib

    from edify.cli import build_parser

    handlers = list(_every_handler(build_parser()))
    assert len(handlers) > 40
    for name, func in handlers:
        if func.__name__ == "_version":
            continue
        module, fn = func.__qualname__.split(".")
        target = importlib.import_module(f"edify.commands.{module}")
        assert callable(getattr(target, fn)), f"{name}: edify.commands.{module}.{fn}"


@pytest.mark.parametrize(
    "argv",
    [
        ["graph", "where", "x", "--kind", "symbol"],
        ["--repo", "R", "--json", "-q", "graph", "dependents", "x", "--depth", "2"],
        ["--repo=R", "skills", "resolve", "implementer", "3", "python"],
        ["--no-anim", "--no-color", "init", "--yes", "--agents", "all"],
        ["init", "new", "here", "--no-interview"],
        ["mcp", "for", "implementer", "3"],
        ["swarm", "claim", "feat"],
        ["feedback", "show", "2"],
        ["doctor"],
    ],
)
def test_a_parser_built_for_one_command_parses_it_exactly_as_the_whole_one(argv) -> None:
    from edify.cli import _command_of, build_parser

    only = _command_of(argv)
    assert only is not None
    partial, full = vars(build_parser(only).parse_args(argv)), vars(build_parser().parse_args(argv))
    assert partial.keys() == full.keys()
    for key, value in full.items():
        if key == "func":
            assert partial[key].__qualname__ == value.__qualname__
        else:
            assert partial[key] == value, key


@pytest.mark.parametrize("argv", [[], ["-h"], ["--version"], ["--js", "graph"], ["--repo"], ["--quiet"]])
def test_the_whole_parser_is_built_whenever_the_command_is_not_certain(argv) -> None:
    from edify.cli import _command_of

    assert _command_of(argv) is None


def test_an_unknown_command_still_lists_every_choice(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_:
        main(["bogus"])
    assert exit_.value.code == 2
    err = capsys.readouterr().err
    assert "'graph'" in err and "'doctor'" in err


def test_importing_the_cli_loads_nothing_but_itself() -> None:
    """Startup is interface: an agent runs `edify` dozens of times per task."""
    import os
    import subprocess
    import sys

    probe = (
        "import sys, edify.cli; "
        "print(sorted(m for m in sys.modules if m.startswith('edify')), 'argparse' in sys.modules)"
    )
    src = str(Path(__file__).resolve().parent.parent / "src")
    out = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True,
        env={**os.environ, "PYTHONPATH": src},
    ).stdout.strip()
    assert out == "['edify', 'edify.cli'] False"


def test_version_answers_before_the_parser_exists(capsys: pytest.CaptureFixture[str]) -> None:
    from edify import __version__

    assert main(["version"]) == 0
    assert capsys.readouterr().out == f"edify {__version__}\n"


def test_an_agent_gets_one_error_line_and_one_hint(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, repo: Path
) -> None:
    monkeypatch.setenv("EDIFY_AGENT", "1")
    assert run(repo, "graph", "where", "generate") == 4
    assert capsys.readouterr().err.splitlines() == ["error: no graph on disk", "hint: run `edify graph build`"]

    with pytest.raises(SystemExit) as exit_:
        main(["graph", "where"])
    assert exit_.value.code == 2
    err = capsys.readouterr().err.splitlines()
    assert len(err) == 2 and err[0].startswith("error: ") and err[1].startswith("hint: ")


def test_json_failure_carries_the_error_and_exit_code(capsys: pytest.CaptureFixture[str], repo: Path) -> None:
    code, payload = run_json(capsys, repo, "graph", "where", "generate")
    assert code == 4
    assert payload == {"error": "no graph on disk", "hint": "run `edify graph build`", "exit_code": 4}


# -- doctor's newer rows ----------------------------------------------------


def _doctor(capsys: pytest.CaptureFixture[str], root: Path) -> dict[str, dict]:
    code, rows = run_json(capsys, root, "doctor")
    assert code in (0, 1)
    return {row["name"]: row for row in rows}


def _vcs(root: Path, *args: str) -> None:
    import subprocess

    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=root, check=True, capture_output=True
    )


needs_vcs = pytest.mark.skipif(__import__("shutil").which("git") is None, reason="git is not installed")


def test_doctor_leaves_out_the_repository_rows_outside_one(
    capsys: pytest.CaptureFixture[str], installed: Path
) -> None:
    rows = _doctor(capsys, installed)
    assert "graph hooks" not in rows and ".edify/run" not in rows
    assert rows["skill mirror"]["state"] == "ok"
    assert rows[".mcp.json"]["state"] == "ok"


@needs_vcs
def test_doctor_names_a_stale_graph_and_the_cheap_fix(capsys: pytest.CaptureFixture[str], installed: Path) -> None:
    _vcs(installed, "init", "-q")
    _vcs(installed, "add", "-A")
    _vcs(installed, "commit", "-qm", "one")
    assert run(installed, "--quiet", "graph", "build") == 0
    (installed / "later.py").write_text("x = 1\n", encoding="utf-8")
    _vcs(installed, "add", "-A")
    _vcs(installed, "commit", "-qm", "two")
    capsys.readouterr()

    rows = _doctor(capsys, installed)
    assert rows["graph"]["state"] == "degraded"
    assert "edify graph update --changed" in rows["graph"]["detail"]
    assert rows["graph hooks"]["state"] == "degraded"
    # init creates .edify/run/ with its own `*` .gitignore, so it is ignored at once.
    assert rows[".edify/run"]["detail"] == "ignored by the repository"
    (installed / ".edify" / "run" / ".gitignore").unlink()
    assert _doctor(capsys, installed)[".edify/run"]["state"] == "degraded"
    (installed / ".gitignore").write_text(".edify/run/\n", encoding="utf-8")
    assert _doctor(capsys, installed)[".edify/run"]["detail"] == "ignored by the repository"

    hooks = installed / ".git" / "hooks"
    for name in ("post-commit", "post-merge", "post-checkout", "post-rewrite"):
        (hooks / name).write_text("#!/bin/sh\n# edify:graph-hook\n", encoding="utf-8")
    assert _doctor(capsys, installed)["graph hooks"]["state"] == "ok"


def test_doctor_recognises_what_graph_hook_writes() -> None:
    from edify.commands import doctor_cmd, graph_cmd

    assert doctor_cmd.GRAPH_HOOK_MARKER in graph_cmd._HOOK


def test_doctor_warns_when_mcp_json_loads_a_scoped_server_everywhere(
    capsys: pytest.CaptureFixture[str], installed: Path
) -> None:
    from edify.formats import mcp as mcp_format

    registry = mcp_format.parse(Layout(installed).mcp)
    scoped = [s.name for s in registry.servers if not ("any" in s.roles and "any" in s.phases)]
    if not scoped:
        pytest.skip("the default registry scopes nothing")
    (installed / ".mcp.json").write_text(json.dumps({"mcpServers": {scoped[0]: {"command": "x"}}}), encoding="utf-8")
    row = _doctor(capsys, installed)[".mcp.json"]
    assert row["state"] == "degraded" and scoped[0] in row["detail"] and "edify mcp config" in row["detail"]


def test_doctor_notices_a_skill_that_was_never_mirrored(capsys: pytest.CaptureFixture[str], installed: Path) -> None:
    import shutil

    shutil.rmtree(installed / ".claude" / "skills" / "planner", ignore_errors=True)
    (installed / ".claude" / "agents" / "planner.md").unlink(missing_ok=True)
    row = _doctor(capsys, installed)["skill mirror"]
    assert row["state"] == "degraded" and "edify skills sync" in row["detail"]


def test_init_makes_the_run_directory_ignore_itself(installed) -> None:
    marker = installed / ".edify" / "run" / ".gitignore"
    assert marker.is_file() and marker.read_text(encoding="utf-8").splitlines()[-1] == "*"


@pytest.mark.parametrize("family", ["graph", "swarm", "skills", "mcp", "governance", "license", "self"])
def test_a_bare_family_prints_its_help_and_exits_2(family, capsys) -> None:
    assert main([family]) == 2
    assert "usage:" in capsys.readouterr().out


def test_version_outside_a_terminal_takes_the_fast_path(capsys) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip().startswith("edify ")
