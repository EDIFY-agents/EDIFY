# {{repo}}
Stack: {{stack}}  ·  Tests: {{test}}

## Commands — .edify/commands/<name>.md
/spec   — what and why; unknowns marked [NEEDS CLARIFICATION]
/plan   — binding decisions, only when the work needs them
/tasks  — leaseable tasks, then build them: one agent or a swarm
/verify — fresh session; real runs on every tier, evidence not claims

## The codebase map — query before reading files, never guess a path
  edify graph map                 → .edify/graph/MAP.md: subsystems, hubs, bridges
  edify graph context "<task>"    → the files and ranges this task needs
  edify graph where|explain <x>   → file:line · edges · who depends on it
  edify graph dependents <x>      → everything that breaks if it changes

## Load only what the task needs
Skills: `edify skills resolve <role> <phase>` → one file. Servers: `edify mcp config
<role> <phase>` → only those. Parallel work: `edify swarm claim|prompt|done`.
Features: specs/<feature>/   Conventions: .edify/conventions.md
