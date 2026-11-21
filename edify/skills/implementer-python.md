---
name: implementer-python
description: Implements a build task in a Python service or library codebase.
kind: skill
role: implementer
phase: 0 1 3 4 5 6
tech: python django flask fastapi sqlalchemy pydantic celery
provenance: original
license: -
---

# Implementer — Python

Build steps, submit gate and hand-back are `.edify/skills/implementer-general.md`; read
it first. This adds what Python gets wrong.

## Method
1. From the pattern pointer copy: module layout, how errors are raised and caught,
   fixtures, and the data shape in use (dataclasses, pydantic, plain dicts).
2. The graph parses Python with a real syntax tree: `edify graph where` and `defines`
   answers are exact — use them before writing a helper or an import.
3. Match annotation level: fully annotated module under mypy/pyright → annotate fully;
   unannotated → do not half-annotate.
4. Keep the import style (absolute vs relative) and where `__init__.py` re-exports live.
5. After the done-check, the type checker and linter `.edify/conventions.md` names.

## Traps
- A mutable default (`def f(x=[])`) is shared across calls; default `None`, build inside.
- Bare `except:` swallows `KeyboardInterrupt`/`SystemExit`; catch what is raised.
- A blocking call (sync HTTP client, `time.sleep`, sync DB driver) inside `async def`
  stalls the loop for every request.
- An ORM query in a loop is an N+1 that only shows under load; use the codebase's
  eager-loading pattern.
- Commit where the existing code commits (request layer vs service); a commit in the
  wrong layer is a rollback that will not roll back.
- No new dependency the plan did not decide on.
