"""The project ledger, retired in 0.2.0: nothing writes it, and nothing removes it.

`tests/test_projects.py` tested the fifth gate. The gate is gone, and each of its
tests is accounted for here rather than deleted silently:

    the cap, the refusal and the refused-install tests
        → A-5 (a tenth repository installs free) in the assertion suite
    the price and the purchase command named in the refusal
        → A-1 (buy is gone) and A-16 (the refusal names no price)
    `license projects` and `license projects forget`
        → `tests/test_license_cmd.py::test_license_projects_is_gone`
    the pro licence lifting the cap, and `upgrade` on the free plan
        → A-4 (upgrade runs on the free plan)
    the ledger's identity, pruning and CI-checkout tests
        → the two tests below: no new ledger is written, and an old one is kept
          byte for byte
"""

from __future__ import annotations

from pathlib import Path

from edify.cli import main
from edify.licensing import projects


def _init(root: Path) -> int:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    return main(["--repo", str(root), "--quiet", "init", "--no-graph", "--yes"])


def test_init_never_writes_the_ledger(tmp_path: Path, isolated_home: Path) -> None:
    for i in range(5):
        assert _init(tmp_path / f"p{i}") == 0
    assert list(isolated_home.rglob("projects.tsv")) == []
    assert not projects.ledger_path().exists()


def test_an_existing_ledger_is_left_byte_identical(tmp_path: Path) -> None:
    ledger = projects.ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    body = b"#key\tpath\tadded\ngit:example/one\t/somewhere/one\t2026-01-01\n"
    ledger.write_bytes(body)

    root = tmp_path / "repo"
    assert _init(root) == 0
    assert main(["--repo", str(root), "--quiet", "doctor"]) in (0, 1)
    assert main(["--repo", str(root), "license", "status"]) == 0
    assert ledger.read_bytes() == body
