---
name: plan
description: A spec becomes the decisions that bind more than one task.
model: strongest
ends-at: a human
---

# /plan

Only when the feature adds a technology or service, spans milestones, needs a
cross-cutting strategy (migrations, shared components, config), or will be built by
several people or a swarm. Otherwise go from `/spec` to `/tasks`.

**In:** approved `spec.md`, `.edify/constitution.md`, the graph. **Out:** `plan.md`
(`.edify/formats/plan.format.md`) plus the design files it needs — `research.md`,
`data-model.md`, `contracts/`, `quickstart.md` (`design.format.md`). Calibrate on the
`*.example.md` set once; it is one feature end to end.

## Steps
0. **Technical context** and **constitution check**; then `research.md` resolves every
   `[NEEDS CLARIFICATION]`; then `data-model.md`, `contracts/`, `quickstart.md`; re-check.
1. **Milestones** cut by dependency; each rule states its reason.
2. **Decisions**, each with an exact version and the alternative it beat. Check real
   APIs with the `docs` server, not memory.
3. **Cross-cutting**: migration numbers, variants, asset budgets, shared components —
   allocated once; plus the verification budget.
4. **Partition**: from `.edify/graph/MAP.md`, put concurrent milestones in different
   communities so they cross few bridges. Name each frozen contract's owner.
5. **Context seeds** per milestone, from `edify graph context`.
6. **Risks**, each mapped to the milestone that mitigates it.
7. `edify check`, then stop at the gate.

## Refuse
Function signatures (that is `/tasks`). Dates.

## Gate
Show milestones, decisions with alternatives, partition, risks.
