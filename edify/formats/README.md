# Formats

Every file a feature produces, who writes it, and its contract. One worked feature —
*team invitations* — runs through every example, so ids line up file to file.

```
.edify/constitution.md        principles + gates            constitution.format.md
specs/<feature>/
├── spec.md                   /spec    what and why          spec.format.md     spec.example.md
├── plan.md                   /plan    binding decisions     plan.format.md     plan.example.md
├── research.md               /plan    evidence for each     design.format.md   research.example.md
├── data-model.md             /plan    entities, states      design.format.md   data-model.example.md
├── contracts/<interface>.md  /plan    frozen interfaces     design.format.md   contracts.example.md
├── quickstart.md             /plan    end-to-end proof      design.format.md   quickstart.example.md
├── tasks.md                  /tasks   leaseable build plan  tasks.format.md    tasks.example.md
└── verification.md           /verify  evidence              .edify/commands/verify.md
```

`/plan` and its four design files are skipped when the feature adds no technology, has
one milestone and one builder — then `/tasks` reads the spec alone. The closure
checklist (`## What this entails`) lives in the spec rather than in separate checklist
files, and parallel tasks are marked by `Parallel with`, computed from the graph.
