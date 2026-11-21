# Changelog

All notable changes to `edify-agents-cli`. The format follows Keep a Changelog; versioning
is semantic on the CLI surface.

Two contract versions move independently of the CLI version and are recorded in
`.edify/graph/meta` and `edify/manifest.md`: `graph-schema` (bumping it rebuilds an
existing graph rather than misreading it) and `index-schema`.

## Unreleased

## 0.3.2

No caps left in the public edition, and the format files rebuilt around one worked
feature. Nothing to migrate: `--json` keeps every field it had, and `edify check`
requires the same five spec sections as before, so existing specs stay clean. Run
`edify init --force` (or `edify upgrade`) to pick up the new formats.

- **No caps in the public edition.** The MCP registry now scopes every server into
  spawns on every plan; the one-server limit and its licence warnings are gone.
  `mcp_cap` stays in `--json` as `null`, and `needs_licence` in `mcp list --json` is
  always `false`. The `mcp.multi` entitlement is retired; a token that names it still
  verifies and simply carries nothing extra.
- **One worked feature, every file — spec-kit's set.** The examples now follow *team
  invitations* through `spec`, `plan`, `research`, `data-model`, `contracts`, `quickstart`
  and `tasks`, with ids that line up file to file and check clean.
- `spec.md` gains prioritised user stories with Given/When/Then, key entities, success
  criteria (`SC-n`) and assumptions; `plan.md` gains a technical context, a constitution
  check, the design-file list and the project structure.
- New `design.format.md` (research, data model, contracts, quickstart) and
  `constitution.format.md` (`.edify/constitution.md`: principles with gates `/plan` checks).
  `.edify/formats/README.md` maps every file to the command that writes it.
- `/verify` replays `quickstart.md` before the tier table.

## 0.3.1

Faster on huge repositories, and a smaller repository.

- **Point lookups.** `graph build` also writes `edges.rev.tsv` (edges sorted by
  destination). `explain`, `context`, `path`, `dependents` and `references` binary-search
  the two sorted files for the nodes they touch instead of loading every edge — same
  answers, same order. On a 1.76M-line repository: `context` 7.0s → 2.5s, `explain`
  6.0s → 1.7s, `dependents` / `references` 4.9s → 1.7s.
- **Parallel extraction.** On trees of 1,500+ files, files are parsed in a process pool;
  results fold back in file order, so the graph is byte-identical to a serial build.
  `EDIFY_JOBS=N` sets the workers, `EDIFY_JOBS=1` forces serial. `graph build` on the same
  repository: 27.7s → 20.3s on four cores (63s in 0.2.1).
- **CLI.** A command family named with no subcommand (`edify swarm`, `edify graph`, …)
  prints that family's help and exits 2 — nothing ran. `edify version` at a terminal shows
  the once-per-version feedback invitation again; off-terminal it keeps the 18 ms path.
- `.edify/run/` (spawn MCP configs, local leases) carries its own `*` `.gitignore`, so
  `edify init` never edits yours and `doctor` is green from the start.

## 0.3.0

Built for huge repositories, swarms of agents, and several people on one feature.

- **Four commands.** `/spec`, `/plan`, `/tasks`, `/verify`, each 30–50 lines. `/build`
  folds into `/tasks`: write the task list, then run it with one loop. Unknowns are
  marked `[NEEDS CLARIFICATION: …]`. `/verify` exercises every surface a spec declares
  (service, browser, device or emulator, live API keys, connectors) and reports a tier it
  cannot run as `blocked: needs X`, never as a pass. Format contracts are a third of their
  former length.
- **The graph summarises itself.** `edify graph map` writes `.edify/graph/MAP.md`:
  communities (deterministic label propagation over the file graph), hubs and bridges.
  `graph context "<task>"` returns the slice one task needs under a token budget.
  `graph explain` and `graph path` tag each edge EXTRACTED or INFERRED and exit 0
  (answered), 3 (ambiguous, pin with `file::name`) or 4 (not found).
- **Incremental graph.** `graph update --changed` re-extracts only what git reports.
  A scoped update now resolves references out of the re-extracted directories instead of
  dropping them. `graph hook` installs git hooks that keep the graph current.
- **Swarm leases.** `edify swarm board|claim|prompt|done|block|release|renew`. Claims are
  gated on phase and dependencies, and a claim waits while its blast radius (files plus
  graph dependents) touches a live lease. Leases live in the git common dir by default.
  With `--git` they live on `origin/edify-swarm`, where push atomicity is the lock. `done`
  is fenced: an expired holder cannot record over the new one. `swarm prompt` is the
  whole spawn payload: resolved skill, task block, decisions, graph slice, scoped servers.
- **MCP and plugins only when needed.** `edify mcp config <role> <phase>` writes only the
  scoped servers, from `.edify/mcp.pool.json` (no runtime auto-loads it), for
  `--mcp-config … --strict-mcp-config`.
- **Library.** The harvested methods are folded into the role skills that resolve
  automatically: verification-gap and edge-case-trace into `verifier`, submit-gate and
  evidence-before-claim into `implementer-general`, reproduction-first and
  network-diagnosis into `debugger`, finding-triage into `adversary`, and test-critique
  and condition-based-waiting into both test writers. `implementer-rails` is new. Role
  skills are 23–33 lines.

## 0.2.1

- **Licences carry the team fields.** A team or partner token names its client, its admin
  handles, an optional repository binding (the root commit) and its signing key (`kid`).
  Every field is optional, so tokens already issued keep working.
- **Licence ID.** Every licence has one, derived from its signed bytes, shown by
  `edify license status` and in `--json` as `license.id`.
- **Revocation, offline.** A release can carry a signed list of revoked licence IDs
  (`edify/licensing/revoked.tsv`). A revoked licence runs the public edition and says so;
  `activate` refuses it. Nothing is fetched.
- **Key rotation.** Several licence keys can ship at once, selected by the token's `kid`.
  `EDIFY_LICENSE_PUBKEY` now adds a key rather than replacing the shipped one.
- `license status` shows the client, admins, licence ID, verifying key and whether a bound
  licence matches this repository. `status` and `doctor` warn 30 days before expiry
  (was 15).
- `edify check` understands milestone-scoped task lists. With `milestone:` in the
  frontmatter, a `deferred` coverage row excuses the assertions it owns (listed as notes,
  not errors), and a delete by a task marked `Status — done` no longer counts as a
  missing file. `deferred` without a milestone is an error.
- Fixed: `edify license activate <token>` crashed with "File name too long" when the
  token, pasted on the command line, was longer than a filename may be.
- Fixed: a validly signed token with a non-numeric `seats`, or a payload that is not an
  object, crashed licence resolution instead of being refused.

## 0.2.0

- **Renamed** on PyPI from `edify-cli`, a name that belongs to another project, to
  `edify-agents-cli`.
- Removed: the individual paid plan (`pro`), the purchase and project-count
  subcommands, and the graph, project and upgrade caps.
- Changed: a second MCP server needs a team or partner licence, and existing entries are
  kept.
- Docs: the README and `docs/` now carry the site's ink clips as animated WebP
  (`assets/motion/`), and the terminal screenshots are recaptured from 0.2.0 output.

## Between 0.1.0 and 0.2.0

Condensed; the full notes are in git history (`git log -p -- CHANGELOG.md`).

- **A real issuing key.** 0.1.0 shipped the public key of an all-zeros seed; it was
  replaced with a random key whose private half never enters this repository, and
  `tests/test_licensing.py` fails if a trivially derivable key comes back.
- **`edify self update [--from PATH]` and `edify self where`.** Replaces the CLI through
  whichever tool installed it (uv, pipx or pip; `--manager` overrides detection),
  `--dry-run` prints the exact argv, a locked `edify.exe` on Windows is reported rather
  than hidden, and `--offline` refuses to fetch `hatchling`. Never touches `.edify/`.
- **The install has a face.** A wordmark and an animated ∞ (a lemniscate of Gerono,
  precomputed frames, two glyph sets by stream encoding) paint to stderr on a real
  terminal only; `--json` output is unchanged and `EDIFY_NO_ANIM` turns it off.
- **`edify init new [PATH]`.** A folder set up from zero for every runtime in one table
  (`src/edify/agents.py`): Claude Code, Codex, Cursor, Gemini CLI, Copilot, Windsurf and
  a generic `AGENTS.md`. Eight skippable questions write `.edify/profile.md`. Clearing is
  one implementation (`host.clear`) shared with `setup --fresh`, and a later `init`
  keeps every runtime already set up current.
- **`edify setup [PATH] [--fresh]`.** Pins the root where pointed instead of walking up
  into a parent checkout; `--fresh` clears EDIFY's own files and nothing else.
- **Installed skills are visible to the runtime.** `edify skills sync` writes pointer
  files at `.claude/skills/<name>/SKILL.md`; a hand-authored `SKILL.md` is never touched.
- **`/harvest`.** `edify harvest pick | stage | screen | propose | admit | reject |
  status`, with `harvest/ledger.json` recognising a candidate by URL, content hash and
  entry name. `pick` scores sources deterministically; the screen (licence allowlist,
  duplicate, injection scan) fails closed; `admit` needs a person at a terminal and then
  installs, indexes, mirrors and records governance in one step.
- **Governance over every installed file.** `.edify/governance.tsv` and
  `edify governance list | verify | rebuild`; `verify` tells a modified EDIFY file from
  an edited repository-owned one.
- **The library asks before it installs** (`--skills`, `--yes`); with no terminal it asks
  nothing.
- **Feedback with no telemetry.** `edify feedback` writes four answers to a local file
  and prints how to send them; nothing is transmitted.
- **macOS and publishing.** Platform config directories, a walk that ignores macOS
  bundle debris, `INSTALL.md`, the Homebrew formula, `PUBLISHING.md`, and a tag-driven
  `release.yml` with trusted publishing and wheel smoke tests on three platforms.
- Fixed: a `→` or `·` in output no longer kills a command on a cp1252 Windows console.
- A paid individual plan and its project, graph and upgrade caps were added here and
  removed in 0.2.0.

## [0.1.0] — 2026-08-07

First release: the graph commands, the methodology surface, and the install path.

- **The map.** `edify graph build | update | where | dependents | defines | overlap |
  references | stat`, deterministic and byte-identical on unchanged source. Python is
  parsed with a real syntax tree, 19 languages are scanned, and `meta.method_<language>`
  and `meta.languages_uncovered` say which. No model writes the graph. Optional
  `--extractor ctags`.
- **The documents.** `edify check [--fix] [--exit-code]` over specs, plans, tasks, skill
  files and the server registry; it reports and never blocks.
- **The install.** `edify init`, `skills list | resolve | index | add`,
  `mcp list | check | for`, `doctor`, and `upgrade` (with `--archive` for air-gapped
  machines).
- **The methodology tree.** Five command files (`/spec`, `/plan`, `/tasks`, `/build`,
  `/verify`; `/build` folded into `/tasks` in 0.3.0), three format contracts with worked
  examples, twelve skill entries, the harvest design, and a one-entry registry.
- **Licensing.** Offline Ed25519 verification in pure Python (RFC 8032 §7.1 vector),
  `edify license status | activate | deactivate`, and the issuer.
- **Known limits.** Everything but Python, Markdown and SQL is scanned, not parsed
  (`doctor` says amber); `mcp check` cannot probe remote or version-less servers; no
  standalone binaries.
