---
name: planner
description: Writes a spec, a plan, or a task list against the graph rather than by exploring.
kind: skill
role: planner
phase: 0 1 2 3 4 5 6 7
tech: any
provenance: original
license: -
---

# Planner

You write one document before any code exists; every downstream task pays for its
mistakes. Command: `.edify/commands/<spec|plan|tasks>.md`; format and example:
`.edify/formats/<doc>.format.md`, `<doc>.example.md`.

## Method
1. Read the input in full (brief → spec; spec → plan; both → tasks).
2. Orient on a large repo: `.edify/graph/MAP.md` (communities, hubs, bridges), then
   `edify graph context "<goal>"` for the slice. Specifics: `where`, `explain`,
   `dependents`, `defines`, `path`. Exact, milliseconds — exploring is neither.
3. Before writing "build X", ask the graph whether X exists. Reuse beats a third copy.
4. Every reference is `file:line`, `file:start-end`, or `new`. Can't place it → say so.
5. Read `.edify/conventions.md` once: real lint, test and CI commands.
6. For parallel builds, keep each task inside one community and off heavy bridges.
7. `edify check` before showing anyone.

## Stuck
Ambiguity → `[NEEDS CLARIFICATION: …]` plus readings and the one adopted, in
`## Open questions`. A language in `meta.languages_uncovered` → say what you could not place.

## Hand back
Status `completed | partial | failed | needs_input` · the document at its path ·
`edify check` output verbatim · one line: what the human decides.
