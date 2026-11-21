---
name: test-writer-python
description: Turns spec assertions into failing tests in a Python codebase.
kind: skill
role: test
phase: 2
tech: python pytest django flask fastapi
provenance: adapted
license: MIT github.com/obra/superpowers@44c9b2d6e889982ac18c27d05a19fefe335194e1
source: harvest test-critique, condition-based-waiting
---

# Test writer — Python

Phase 2: each assertion the task names becomes a test that **fails**, at the
verification kind the spec declared, before any implementing code exists. This red is
the definition of finished every later phase is measured against.

## Method
1. Copy the pattern pointer's fixtures exactly — `conftest.py`, DB teardown, client.
2. One class or module per requirement, one test function per assertion, the id in the
   name (`test_a7_…`) so a failure names what is unsatisfied.
3. Import models and schemas from the frozen phase-1 contract; never redeclare a shape.
4. `property` → the repository's property library (Hypothesis) with the stated invariant
   and a bounded example count. None installed → say the plan should have budgeted one;
   never three examples called a property test.
5. `observation` → no test; a skipped placeholder naming the phase-7 task keeps the count
   honest.
6. Stub nothing. Imports of modules that do not exist yet are the expected failure.
7. Run the suite: N failing, 0 passing.

## Traps
- A test green on arrival tested something that exists, or nothing.
- `pytest.raises` without `match=` passes on the wrong error.
- A module-scoped fixture that mutates state makes results depend on test order.
- Time frozen in one test and not its neighbour: a suite that fails at midnight.
- Mocking the unit under test makes the suite agree with itself.

## Critique before handing back
- Name the production change that would make each test fail; none → the test is empty.
- Expected values come from the spec, never from the code under test.
- No assertions on source text, on mocks of the unit, or on framework dispatch.
- Replace fixed sleeps with a poll on the condition the next assertion needs; keep a
  delay only where timing is the behaviour (debounce, TTL). Run it 20× and in parallel.

## Hand back
Status `completed | partial | failed | needs_input` · task id · test files · raw suite
output with the failing count. An assertion that cannot fail as written is a spec
finding: `edify swarm done <id> --status needs_input --reason "A-k cannot fail — <why>"`.
