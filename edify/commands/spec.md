---
name: spec
description: A brief becomes a specification — what and why, never how.
model: strongest
ends-at: a human
---

# /spec

**In:** the brief, `.edify/conventions.md`, the graph. **Out:** `specs/<feature>/spec.md`
per `.edify/formats/spec.format.md` (calibrate on `spec.example.md` once).

## Steps
1. Paste the brief verbatim into `## Brief`. Never edit it again.
2. Orient: read `.edify/graph/MAP.md` (`edify graph map`), then
   `edify graph context "<the brief>"`. Every codebase claim is a `file:line` from the
   graph, or `new`; do not explore files to answer structure.
3. Draft user stories by priority (P1 alone is an MVP; Given/When/Then each) → intent →
   requirements (`REQ-n`) → assertions (`A-n`, one per scenario, the cheapest
   verification kind that can fail) → key entities, success criteria (`SC-n`),
   assumptions, non-goals. Check against `.edify/constitution.md` if it exists.
4. Mark every unknown inline `[NEEDS CLARIFICATION: question]` — never guess.
5. Spawn one adversary (skill `adversary`) given only the brief and the draft. Its
   findings go to `## What this entails` / `## Open questions`, tagged adversary.
6. Repeat 3–5 until a pass adds nothing, at most three. Residue stays an open question.
7. `edify check`, then stop at the gate.

## Refuse
Code. Library or version choices (that is `/plan`). An assertion that cannot fail.

## Gate
Show intent, requirements, open questions, cost band. The human answers or accepts
defaults on the record, and approves.
