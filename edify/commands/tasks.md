---
name: tasks
description: Spec and plan become leaseable tasks — then the tasks get built, by one agent or a swarm.
model: strongest to write · cheapest that follows instructions to build
ends-at: a human (write) · a green suite (run)
---

# /tasks

**Write** the list once; **run** it with the same loop for one agent, fifty, or five people.

## Write → `specs/<feature>/tasks.md` per `.edify/formats/tasks.format.md`
**In:** approved spec; plan, `data-model.md`, `contracts/`, `quickstart.md` if any; the
graph. Read `tasks.example.md` once — its level of detail is the contract.
1. **Cut**: every `REQ` and checklist row → one or more tasks.
2. **Place**: `edify graph context "<task>"`, `where`, `dependents` → exact files and
   line ranges.
3. **Order** into phases 0–7. Phase 2 is every assertion as a **failing** test, never
   merged into implementation tasks.
4. **Parallelise** with `edify graph overlap`; keep each task inside one MAP.md community.
5. **Detail** each block: pattern pointer, steps, `Done when`.
6. **Close** `## Coverage`; `edify check`; gate: show phases, coverage, tasks.

## Run — after approval
```
edify swarm claim [feature] [--worktree]   # exit 1 = nothing ready right now
edify swarm prompt <id>                    # skill + task + decisions + graph slice + servers
build exactly that task · run its Done when · commit on swarm/<id>
edify swarm done <id>                      # or: --status partial|failed|needs_input --reason "…"
repeat until claim says "all done"; then /verify in a fresh agent
```
- **Swarm**: the orchestrator dispatches and merges, never edits code. N workers, each in
  its own worktree, get only `edify swarm prompt` output and loop claim → build → done,
  handing back `completed | partial | failed | needs_input` with raw evidence; anything
  but `completed` is recorded as a block. Leases are phase-gated and overlap-safe.
  `edify swarm status`: who holds what, what is expiring. Other machines: `edify swarm --git …`.
- **Merge** after each phase: `edify swarm merge --apply` lands done `swarm/*` branches
  (phase, then task order; overlapping radii serialised) and stops at the first conflict;
  then the phase exit check and `edify graph update --changed`. A conflict is a missing
  `Depends on`: amend tasks.md.
- **Failed done-check**: retry once, then the `debugger` skill, then a non-`completed`
  hand-back. Never retry a side effect (deploy, migration, external write) without
  checking its prior state.
- A decision the task left open → one row in `## Decisions`; it binds later spawns.

## Refuse
Building an unapproved list. Editing a frozen contract. Marking done without the check.
