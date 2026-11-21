# The design files: `research.md` · `data-model.md` · `contracts/` · `quickstart.md`

Written by `/plan`, beside `plan.md` in `specs/<feature>/`, only the ones the feature needs.
The plan stays a page of decisions; the evidence and shapes behind them live here, and
`/tasks` cites them by `file:start-end`. Worked examples: `research.example.md`,
`data-model.example.md`, `contracts.example.md`, `quickstart.example.md`.

## `research.md` — why each decision is the one in the plan
One block per `[NEEDS CLARIFICATION]` the spec left, technology choice, or integration:
```
## R-<n> · <question> → D-<n> | spec Q-<n>
- **Decision**      what was chosen, with its exact version
- **Rationale**     why, citing `file:line` in this repo where it already does the thing
- **Alternatives**  what else was evaluated and why it lost
- **Evidence**      graph queries run, docs consulted (`docs@<version>`)
```
Done when no `[NEEDS CLARIFICATION]` remains anywhere in spec or plan.

## `data-model.md` — what the storage must satisfy
- One section per entity from the spec's key entities: `| field | type | rule | from |`,
  where `from` names the REQ, A or CL the rule comes from.
- Uniqueness and relationships in one line each. State machine for anything with a
  lifecycle: a diagram and a `| from | event | to | error otherwise |` table.
- No SQL and no ORM code — the migration is a task; this is its acceptance criterion.

## `contracts/<interface>.md` — every surface other code or people call
- One file per interface: HTTP endpoints, CLI commands, a library's public API, event
  payloads, a UI's routes. A table: operation · auth · input · success · errors.
- Error codes listed once, with the one place in code that owns them.
- Frozen at the end of phase 1; a change after that is a `/tasks` amendment.

## `quickstart.md` — the end-to-end proof `/verify` replays
- **Prerequisites**: services to start, env flags, secrets by *name* (never values), seed data.
- **Steps**: `| # | do | expect | proves |` — exact commands, observable results, the A/SC ids.
- Every `observation` assertion and every verification tier the spec declares (browser,
  device or emulator, live API, connector) has a step.
- No implementation; link to the contract and data model rather than repeating them.
