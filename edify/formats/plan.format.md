# The `plan.md` format

Every decision that binds more than one task, so no task makes one. Example:
`plan.example.md`. Written only when the work needs it.

```yaml
---
feature: team-invitations
spec: spec.md
status: draft            # draft | approved | amended
milestones: 6
date: 2026-08-06
supersedes: —
---
```

## Sections
```
# plan — <feature>
## Summary               the requirement and the approach, two lines
## Technical context     language/version · dependencies · storage · testing · target · project type ·
                         performance · constraints · scale — each a value or [NEEDS CLARIFICATION]
## Constitution check    each gate of .edify/constitution.md: ✓, or a justified violation row
## Design artefacts      which of research.md · data-model.md · contracts/ · quickstart.md exist (design.format.md)
## Milestones            | id | delivers | requirements covered | gate | size |  + one rule per line, with why
## Technology decisions  | # | decision | version | beat | why |
## Cross-cutting         migrations · variants · assets (with budget) · shared components · verification budget
## Project structure     the real directories this feature touches
## Per-milestone         ### M<n> — goal · requirements · gate · size · affected files · context seeds
## Parallelization       milestones that may overlap; owners; communities from MAP.md
## Risks                 | risk | milestone | mitigation |
```

Order of work: technical context → constitution check → `research.md` (resolve every
`[NEEDS CLARIFICATION]`) → `data-model.md`, `contracts/`, `quickstart.md` → re-check the
constitution → milestones, decisions, seeds.

## Rules `edify check` enforces
- Versions are exact (`2.3`), never `^2.3` or `latest`.
- A decision names the alternative it beat, or calls itself a default.
- Context seeds are `file:start-end — why` and resolve against the graph.

## Notes
- Dependency rules state their reason, so an amendment can relax them safely.
- Migration numbers are allocated here once; two tasks never claim the same one.
- The verification budget lists every `model`/`proof` assertion and every
  `observation` needing a device, emulator, live key or connector (secret names only).
- Parallel work: put concurrent milestones in different communities; name who owns
  each frozen contract. `/tasks` computes the exact task-level overlap from the graph.
- No function signatures (that is `/tasks`), no dates (sizes and sequence only).
