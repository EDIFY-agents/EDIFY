# The `spec.md` format

What and why, for one feature, readable in ten minutes. Calibrate on `spec.example.md`.

```yaml
---
feature: team-invitations
status: draft            # draft | approved | amended
date: 2026-08-06
supersedes: —
brief-source: —
---
```

## Sections, in order
```
# spec — <feature>
## Brief              the ask, verbatim, never edited
## User stories       ### US<n> — <title> (P<n>): journey, **Independent test**, Given/When/Then
## Intent             numbered clauses; appended or struck, never renumbered
## Constraints        what is GIVEN: versions in use, platforms, real commands, hard limits
## Requirements       | id | requirement | assertions |
## Assertions         | id | assertion | verification | citation |
## Key entities       one line each: what it is, what it relates to — fields go to data-model.md
## Success criteria   SC-<n>: measurable, technology-free outcomes
## What this entails  | id | what it entails | status |   (the closure checklist)
## Assumptions        defaults taken where the brief was silent
## Open questions     | # | question | readings | adopted | who resolves |
## Non-goals
```

## Rules `edify check` enforces
- Every requirement lists ≥1 assertion; every assertion serves a requirement.
- `verification` ∈ `types example contract property model proof observation`, cheapest
  that can fail. Pure functions default to `property`; `types` is free and additive;
  `model`/`proof` must be budgeted in `plan.md`. `observation` names its surface
  (service · browser · device · live API · connector).
- `citation` is `file:line`, `file:start-end`, or `new` — never a bare filename.
- Each entails row is a `REQ-n`, `waived — reason`, or `open`; open rows block the gate.
- Unknowns in any section read `[NEEDS CLARIFICATION: …]` until the gate resolves them.

## User stories
Ordered by priority; P1 alone is a shippable MVP. Each story is testable on its own and
its Given/When/Then scenarios become assertions — one scenario, one `A-n`. Required
sections for `edify check` are Brief, Intent, Constraints, Requirements, Assertions; the
rest appear when the feature has them.

## What belongs where
Choices of library or version are decisions → `plan.md`. Constraints are only what is
given. The entails checklist covers what nobody asked for: permissions, migration and
rollback, error/empty/loading states, authorization, logs and alerts, i18n, retention.
Phase 2 turns every assertion into a failing test — one that cannot fail is not one.
