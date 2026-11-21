---
name: implementer-node
description: Implements a build task in a TypeScript or JavaScript service codebase.
kind: skill
role: implementer
phase: 0 1 3 4 5 6
tech: typescript javascript express fastify nestjs
provenance: original
license: -
---

# Implementer — Node / TypeScript

Build steps, submit gate and hand-back are `.edify/skills/implementer-general.md`; read
it first. This adds what Node and TypeScript get wrong.

## Method
1. From the pattern pointer copy: handler structure, schema parsing, how errors are
   thrown and mapped, test fixture setup.
2. Import request/response types and schemas from where phase 1 froze them; never
   redeclare a shape.
3. Before a helper: `edify graph where <name>` and `edify graph defines <file>` — a second
   token generator or date formatter is the defect the graph prevents.
4. Match module style: named vs default exports, `async/await` vs `.then`, ESM vs CJS
   (`.edify/conventions.md` says what the configs declare).
5. After the done-check, the type check (`tsc --noEmit` or the repo's script). Passing
   tests with a broken `tsc` is not done.

## Traps
- `any` moves the failure to runtime and out of review; use `unknown` and narrow.
- A `catch` that logs and continues turns a failed write into a silent success.
- A floating promise (no `await`, no `.catch`) loses its error; mail, webhooks and
  analytics go through the queue the codebase already uses, outside the request path.
- `JSON.parse` output and `req.body` are untyped until a schema has parsed them.
- No dependency upgrades and no new package the plan did not decide on.
