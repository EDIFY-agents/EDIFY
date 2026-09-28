"""The TOML reader 3.10 falls back on, checked on every interpreter.

`_Parser` is exercised directly so the fallback is tested on 3.11+ too, where
`edify._toml.load` hands the work to `tomllib` instead.
"""

from __future__ import annotations

import io

import pytest

from edify import _toml
from edify._toml import _FallbackDecodeError, _Parser

PYPROJECT = '''
# a comment
[project]
name = "demo"            # trailing comment
version = '0.1.0'
dependencies = [
  "fastapi>=0.110",
  "pydantic[email] ; python_version >= '3.10'",   # comment inside an array
]
description = """
Two lines,\
 joined."""

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.ruff]
line-length = 100
lint.select = ["E", "F"]

[tool.poetry.dependencies]
python = "^3.10"
requests = { version = "2.32.3", optional = true }

[[tool.mypy.overrides]]
module = "a.*"
strict = true

[[tool.mypy.overrides]]
module = "b.*"
"quoted key" = 'C:\\path'
ratio = 1.5e3
hex = 0xff
big = 1_000
off = false
released = 2026-09-27
'''


def test_the_fallback_reads_a_real_manifest() -> None:
    data = _Parser(PYPROJECT).document()
    project = data["project"]
    assert project["name"] == "demo"
    assert project["version"] == "0.1.0"
    assert project["dependencies"] == ["fastapi>=0.110", "pydantic[email] ; python_version >= '3.10'"]
    assert project["description"] == "Two lines, joined."
    assert project["optional-dependencies"] == {"dev": ["pytest>=8.0"]}
    assert data["tool"]["ruff"] == {"line-length": 100, "lint": {"select": ["E", "F"]}}
    assert data["tool"]["poetry"]["dependencies"]["requests"] == {"version": "2.32.3", "optional": True}
    first, second = data["tool"]["mypy"]["overrides"]
    assert first == {"module": "a.*", "strict": True}
    assert second["quoted key"] == "C:\\path"
    assert (second["ratio"], second["hex"], second["big"], second["off"]) == (1500.0, 255, 1000, False)
    assert second["released"] == "2026-09-27"


def test_the_fallback_agrees_with_tomllib_where_tomllib_exists() -> None:
    tomllib = pytest.importorskip("tomllib")
    want = tomllib.loads(PYPROJECT)
    want["tool"]["mypy"]["overrides"][1]["released"] = "2026-09-27"  # a date object there, text here
    assert _Parser(PYPROJECT).document() == want


@pytest.mark.parametrize("text", ['name = "unterminated', "= 1", "[table", "a = [1, 2", "a = 1 b = 2"])
def test_broken_toml_is_a_decode_error_not_a_crash(text: str) -> None:
    with pytest.raises(_FallbackDecodeError):
        _Parser(text).document()


def test_load_reads_bytes() -> None:
    assert _toml.load(io.BytesIO(b'[project]\nname = "x"\n')) == {"project": {"name": "x"}}
