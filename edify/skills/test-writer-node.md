---
name: test-writer-node
description: Turns spec assertions into failing tests in a TypeScript or JavaScript codebase.
kind: skill
role: test
phase: 2
tech: typescript javascript jest vitest react
provenance: adapted
license: MIT github.com/obra/superpowers@44c9b2d6e889982ac18c27d05a19fefe335194e1
source: harvest test-critique, condition-based-waiting
---

# Test writer — Node / TypeScript

Phase 2: each assertion the task names becomes a test that **fails**, at the
verification kind the spec declared, before any implementing code exists. This red is
the definition of finished every later phase is measured against.

## Method
1. Copy the pattern pointer's fixture setup exactly — factories, teardown, auth fixture.
2. One `describe` per requirement, one `it` per assertion, the id in the name
   (`A-7: …`) so a failure names what is unsatisfied.
3. Import types and schemas from the frozen phase-1 contract; never redeclare a shape.
4. `property` → a generated-input test (fast-check, or what the neighbours use) with the
   stated invariant and their shrink config — never downgraded to three examples.
5. `observation` → no test; a skipped placeholder `A-n: see T-<phase-7 task>` keeps the
   count honest.
6. Stub nothing. Imports of modules that do not exist yet are the expected failure.
7. Run the suite: N failing, 0 passing. The type check must still pass.

## Traps
- A test green on arrival tested something that exists, or nothing.
- A snapshot written before the code goes green against whatever is built; assert values.
- A subset assertion on an unauthenticated body misses a leak; assert the exact key set.
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
