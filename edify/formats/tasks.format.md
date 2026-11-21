# The `tasks.md` format

The build plan, precise enough that a cheap model — or fifty of them at once — builds
it without asking. Read `tasks.example.md` once: its level of detail is the contract.

```yaml
---
feature: team-invitations
spec: spec.md
plan: —                  # plan.md, or —
status: draft            # draft | approved | amended
milestone: M1            # optional: this list tasks one milestone
phases: 8
tasks: 16
date: 2026-08-06
---
```

## Phases — horizontal layers; a feature uses the ones it needs
| # | phase | lands here |
|---|---|---|
| 0 | Foundation | deps, config, flag, skeleton |
| 1 | Contracts | schema, migrations, types, API shapes — **frozen at phase end** |
| 2 | Verification | every assertion as a test that **fails** |
| 3 | Core | domain logic |
| 4 | Surfaces | endpoints, screens, jobs — against frozen contracts; the swarm's phase |
| 5 | Integration | wiring, mocks replaced, end-to-end |
| 6 | Hardening | errors, permissions, edge cases, limits |
| 7 | Proof | `/verify` in a fresh agent |

`## Phases` is a table: number · name · task ids · parallel groups · **exit check** (a
runnable command). A later phase never starts while an earlier one has open tasks.

## The task block
```
### T-7 · <one line: what this task does>
Phase 4 · Role implementer · Skill implementer-node · Size s
Discharges REQ-4, CL-2
Depends on T-4, T-6 · Parallel with T-8, T-9
Verification example, property (A-7)          ← phase 2 only
Files
| path | range | action |
|---|---|---|
| src/api/invitations.ts | — | new |
| src/api/router.ts | 22-38 | edit |
Follow the pattern at
- src/api/members.ts:18-77 — same handler shape: schema, service call, 201 + Location
Steps
1. Add a `token` field to the request schema at line 22: string, 32 chars, required.
Done when
- `npm test -- invitations` passes
- POST twice with the same token returns 200 and creates one row
```
- **Role** is one of `planner adversary test implementer debugger verifier` — skill
  resolution and server scoping key on it. **Skill** names the file the spawn loads.
- **Discharges** is required: a task that discharges nothing is refused.
- **Files**: `edit` needs a line range (from the graph); `new` has none. A whole-file
  edit inflates the blast radius and serialises the swarm.
- **Parallel with** is computed by `edify graph overlap`, never asserted.
- **Follow the pattern at** is the highest-leverage line; for novel work write
  `no precedent in this codebase`.
- **Steps**: 3–8, each doable without a question. **Done when**: a command or an
  observable fact. Phase 2's done-check asserts the tests **fail**.
- `Status — **done** <date>` is written under the heading by `edify swarm done`.

## `## Coverage`
| source | what it is | asserted by | built by |
|---|---|---|---|
| REQ-1 | An admin can invite by email | T-4, T-5 | T-2, T-7 |
| CL-6 | Retention rule | — | `waived` — only an email the admin already holds |
| REQ-9 | Revoke an invitation | `deferred` M2 | `deferred` M2 |

Cells: task ids · `waived` + reason · `proof-only` · `deferred` (only with `milestone:`).
An empty cell means not ready.

## `## Decisions`
Append-only during the run, empty at the gate: `| # | decision | why | binds |`. Every
later spawn carries it. Six rows in one feature means `/tasks` under-specified.

## `edify check` reports
No discharge, steps or done-check · whole-file edit · missing file (except a delete by a
done task) · `deferred` without `milestone:` · phase-2 check asserting a pass · an
assertion with no phase-2 task · empty coverage cell · phase without exit check ·
dependency on a task that does not exist.
