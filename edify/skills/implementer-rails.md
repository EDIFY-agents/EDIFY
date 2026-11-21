---
name: implementer-rails
description: Implements a build task in a Rails codebase, against the version the lockfile reports.
kind: skill
role: implementer
phase: 0 1 3 4 5 6
tech: ruby rails
provenance: adapted
license: MIT github.com/VoltAgent/awesome-claude-code-subagents@82b73821baa7a911d5b14cfb6da238b7f0db6b42
---

# Implementer — Rails

Build steps, submit gate and hand-back are `.edify/skills/implementer-general.md`; read
it first. Rails 7 and 8 ship different defaults for the same job, so the idiom is a
fact you read, not one you remember.

## Method
1. **Read `Gemfile.lock` first**: the resolved `rails` version and `RUBY VERSION`. Name
   both in the hand-back; gate Ruby features (YJIT, newer syntax) on the second.
2. The built-in for a job, by version — but what `Gemfile.lock` and `config/` show
   installed wins, and the pattern pointer outranks this table:

   | job | 7.x | 8.x |
   |---|---|---|
   | jobs · cache · cable | Sidekiq/GoodJob · Redis/Memcached · Redis | Solid Queue · Solid Cache · Solid Cable |
   | assets | Sprockets or Propshaft | Propshaft |
   | auth | Devise or `has_secure_password` | `rails generate authentication` |
   | rate limiting | `rack-attack` (`rate_limit` from 7.2) | `rate_limit` in the controller |
   | deploy | Capistrano, Docker, PaaS | Kamal 2 with Thruster |

   The 8.x column does not exist on 7.x: no generator, no Solid\* tables.
3. From the pattern pointer copy where logic sits (model, service, concern), RSpec vs
   Minitest, FactoryBot vs fixtures, serializer style.
4. Rails resolves by naming convention: `edify graph where <name>` before deciding a
   method or scope is missing.
5. A task naming an idiom the detected version lacks is a wrong task — report it with
   the `Gemfile.lock` line, do not substitute.

## Traps
- N+1 passes unit tests; with `strict_loading` or `bullet` on, a missing `includes`
  raises — follow the surrounding eager loading.
- A plain `add_index` locks writes; on Postgres use `algorithm: :concurrently` with
  `disable_ddl_transaction!` (`strong_migrations` refuses the unsafe form).
- Propshaft runs no ERB: a `.js.erb` carried over silently stops compiling.
- Solid Queue/Cache/Cable without their installers' schema: a queue that accepts jobs
  and never runs one.
- A callback enqueuing a job fires inside the transaction; enqueue after commit.
- `brakeman`/`bundler-audit` in CI fail on raw SQL interpolation or a vulnerable gem.
