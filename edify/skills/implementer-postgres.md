---
name: implementer-postgres
description: Implements a schema, migration, or query task against a relational database.
kind: skill
role: implementer
phase: 1 3 5 6
tech: postgres mysql prisma drizzle typeorm sqlalchemy
provenance: original
license: -
---

# Implementer — schema and migrations

Build steps, submit gate and hand-back are `.edify/skills/implementer-general.md`; read
it first. Usually a phase-1 contract — table, migration, mirroring type — frozen when
the phase ends, so three later phases build on it.

## Method
1. Open the most recent migration and copy its conventions exactly: id column and
   default, timestamp type, foreign keys and delete behaviour, where indexes go.
2. The migration number comes from `plan.md`'s cross-cutting section; never pick one.
3. Write the down migration in the same commit.
4. Put the constraint in the database (unique, partial, check, FK); the service-layer
   check only makes the message nice — the index is what holds under a race.
5. Mirror the table into the codebase's type/model file and its union or registry.
6. Run up, down, up against a test database; paste the output. `edify graph where
   <table>` confirms it is on the map.

## Traps
- `NOT NULL` without a default rewrites and locks the table; on a large table: add
  nullable, backfill, constrain — separate migrations.
- `CREATE INDEX` without `CONCURRENTLY` blocks writes on a live table (and cannot run
  inside a transaction).
- `ON DELETE CASCADE` is a retention decision; use what the spec asked for.
- `timestamp` without time zone is read as different instants by different services.
- Uniqueness that ignores soft-deleted rows is a partial index.
- Never edit a migration applied anywhere; write a new one.
