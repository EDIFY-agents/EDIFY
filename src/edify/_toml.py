"""`tomllib` on 3.11+, and a small reader of the same shape on 3.10.

The package supports 3.10 and has no runtime dependencies, so `tomli` is not an
option. The fallback reads what manifests and tool configs actually hold: tables,
arrays of tables, dotted and quoted keys, strings (basic, literal, multi-line),
integers, floats, booleans, arrays and inline tables. Dates come back as their text.
Anything it cannot read raises `TOMLDecodeError`, which every caller already treats
as "no data" — a degraded answer, never a crash.
"""

from __future__ import annotations

import re
from typing import IO, Any

try:  # pragma: no cover - which branch runs depends on the interpreter
    import tomllib as _stdlib
except ModuleNotFoundError:  # Python 3.10
    _stdlib = None


class _FallbackDecodeError(ValueError):
    pass


TOMLDecodeError = _stdlib.TOMLDecodeError if _stdlib else _FallbackDecodeError

_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")
_NUMBER = re.compile(r"[+-]?(?:0x[0-9A-Fa-f_]+|0o[0-7_]+|0b[01_]+|inf|nan|[0-9_]+(?:\.[0-9_]+)?(?:[eE][+-]?[0-9_]+)?)")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?|\d{2}:\d{2}:\d{2}(?:\.\d+)?")
_ESCAPES = {"b": "\b", "t": "\t", "n": "\n", "f": "\f", "r": "\r", '"': '"', "\\": "\\"}


def load(fh: IO[bytes]) -> dict[str, Any]:
    if _stdlib is not None:
        return _stdlib.load(fh)
    try:
        return loads(fh.read().decode("utf-8"))
    except UnicodeDecodeError as e:
        raise _FallbackDecodeError(str(e)) from e


def loads(text: str) -> dict[str, Any]:
    if _stdlib is not None:
        return _stdlib.loads(text)
    return _Parser(text).document()


class _Parser:
    def __init__(self, text: str) -> None:
        self.s = text.replace("\r\n", "\n")
        self.i = 0

    # -- helpers ------------------------------------------------------------

    def fail(self, what: str) -> None:
        line = self.s.count("\n", 0, self.i) + 1
        raise _FallbackDecodeError(f"{what} (line {line})")

    def peek(self, n: int = 1) -> str:
        return self.s[self.i : self.i + n]

    def blank(self, newlines: bool = False) -> None:
        """Skip spaces and tabs, comments, and (when asked) newlines."""
        while self.i < len(self.s):
            c = self.s[self.i]
            if c in " \t" or (newlines and c == "\n"):
                self.i += 1
            elif c == "#":
                end = self.s.find("\n", self.i)
                self.i = len(self.s) if end < 0 else end
            else:
                break

    def expect(self, token: str) -> None:
        if not self.s.startswith(token, self.i):
            self.fail(f"expected {token!r}")
        self.i += len(token)

    # -- structure ----------------------------------------------------------

    def document(self) -> dict[str, Any]:
        root: dict[str, Any] = {}
        table = root
        while True:
            self.blank(newlines=True)
            if self.i >= len(self.s):
                return root
            if self.peek(2) == "[[":
                self.i += 2
                path = self.key()
                self.expect("]]")
                parent = self.descend(root, path[:-1])
                items = parent.setdefault(path[-1], [])
                if not isinstance(items, list):
                    self.fail("array of tables redefines a key")
                table = {}
                items.append(table)
            elif self.peek() == "[":
                self.i += 1
                path = self.key()
                self.expect("]")
                table = self.descend(root, path)
            else:
                path = self.key()
                self.blank()
                self.expect("=")
                self.blank()
                value = self.value()
                self.descend(table, path[:-1])[path[-1]] = value
            self.blank()
            if self.i < len(self.s) and self.s[self.i] != "\n":
                self.fail("expected the end of the line")

    def descend(self, table: dict[str, Any], path: list[str]) -> dict[str, Any]:
        for part in path:
            nxt = table.setdefault(part, {})
            if isinstance(nxt, list) and nxt and isinstance(nxt[-1], dict):
                nxt = nxt[-1]
            if not isinstance(nxt, dict):
                self.fail(f"{part!r} is not a table")
            table = nxt
        return table

    def key(self) -> list[str]:
        parts = []
        while True:
            self.blank()
            c = self.peek()
            if c == '"':
                parts.append(self.basic_string())
            elif c == "'":
                parts.append(self.literal_string())
            else:
                m = _BARE_KEY.match(self.s, self.i)
                if not m:
                    self.fail("expected a key")
                parts.append(m.group())
                self.i = m.end()
            self.blank()
            if self.peek() != ".":
                return parts
            self.i += 1

    # -- values -------------------------------------------------------------

    def value(self) -> Any:
        c = self.peek()
        if self.peek(3) == '"""':
            return self.multiline('"""')
        if self.peek(3) == "'''":
            return self.multiline("'''")
        if c == '"':
            return self.basic_string()
        if c == "'":
            return self.literal_string()
        if c == "[":
            return self.array()
        if c == "{":
            return self.inline_table()
        if self.s.startswith("true", self.i):
            self.i += 4
            return True
        if self.s.startswith("false", self.i):
            self.i += 5
            return False
        m = _DATE.match(self.s, self.i)
        if m:
            self.i = m.end()
            return m.group()
        m = _NUMBER.match(self.s, self.i)
        if m and m.group():
            self.i = m.end()
            return _number(m.group())
        self.fail("expected a value")

    def basic_string(self) -> str:
        self.expect('"')
        out = []
        while True:
            if self.i >= len(self.s) or self.s[self.i] == "\n":
                self.fail("unterminated string")
            c = self.s[self.i]
            self.i += 1
            if c == '"':
                return "".join(out)
            out.append(self.escape() if c == "\\" else c)

    def escape(self) -> str:
        c = self.peek()
        self.i += 1
        if c in _ESCAPES:
            return _ESCAPES[c]
        if c in "uU":
            n = 4 if c == "u" else 8
            code = self.s[self.i : self.i + n]
            self.i += n
            try:
                return chr(int(code, 16))
            except ValueError:
                self.fail("bad unicode escape")
        self.fail("bad escape")
        return ""

    def literal_string(self) -> str:
        self.expect("'")
        end = self.s.find("'", self.i)
        nl = self.s.find("\n", self.i)
        if end < 0 or (0 <= nl < end):
            self.fail("unterminated string")
        text = self.s[self.i : end]
        self.i = end + 1
        return text

    def multiline(self, quote: str) -> str:
        self.i += 3
        if self.peek() == "\n":
            self.i += 1
        end = self.s.find(quote, self.i)
        if end < 0:
            self.fail("unterminated string")
        while self.s.startswith(quote[0], end + 3) and end + 3 < len(self.s):
            end += 1  # up to two quotes may sit right before the closing three
        raw = self.s[self.i : end]
        self.i = end + 3
        if quote == "'''":
            return raw
        raw = re.sub(r"\\[ \t]*\n\s*", "", raw)  # line-ending backslash
        out, k = [], 0
        while k < len(raw):
            if raw[k] == "\\":
                sub = _Parser(raw)
                sub.i = k + 1
                out.append(sub.escape())
                k = sub.i
            else:
                out.append(raw[k])
                k += 1
        return "".join(out)

    def array(self) -> list[Any]:
        self.expect("[")
        items: list[Any] = []
        while True:
            self.blank(newlines=True)
            if self.peek() == "]":
                self.i += 1
                return items
            items.append(self.value())
            self.blank(newlines=True)
            if self.peek() == ",":
                self.i += 1
            elif self.peek() != "]":
                self.fail("expected ',' or ']'")

    def inline_table(self) -> dict[str, Any]:
        self.expect("{")
        table: dict[str, Any] = {}
        self.blank()
        if self.peek() == "}":
            self.i += 1
            return table
        while True:
            path = self.key()
            self.blank()
            self.expect("=")
            self.blank()
            self.descend(table, path[:-1])[path[-1]] = self.value()
            self.blank()
            if self.peek() == "}":
                self.i += 1
                return table
            self.expect(",")


def _number(text: str) -> int | float:
    t = text.replace("_", "")
    sign = -1 if t.startswith("-") else 1
    body = t.lstrip("+-")
    if body in ("inf", "nan"):
        return sign * float(body)
    if body[:2] in ("0x", "0o", "0b"):
        return sign * int(body, 0)
    if any(ch in body for ch in ".eE"):
        return float(t)
    return int(t)
