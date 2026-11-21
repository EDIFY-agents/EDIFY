---
feature: team-invitations
spec: spec.md
plan: plan.md
status: approved
phases: 8
tasks: 16
date: 2026-08-06
---

# tasks — team invitations

> **Worked example for `tasks.format.md`.** A TypeScript / Postgres / React codebase: an
> admin invites someone by email; the invitee opens a link and joins. Calibrate on the
> precision — exact ranges, a pattern pointer per task, steps a cheap model never has to
> choose between. Not a template: a task list comes from the spec, the plan and its
> design files (`data-model.md`, `contracts/`, `quickstart.md`) and the graph — the same
> feature as `spec.example.md` and `plan.example.md`, ids and all.

## Phases

| # | phase | tasks | parallel-safe | exit check |
|---|---|---|---|---|
| 0 | Foundation | T-1 | — | `npm run build` |
| 1 | Contracts — **frozen at phase end** | T-2, T-3 | — | `npm run migrate:test && npm run typecheck` |
| 2 | **Verification** — assertions as failing tests | T-4, T-5 | T-4 ∥ T-5 | `npm test -- invitations` reports **16 failing, 1 skipped, 0 passing** |
| 3 | Core | T-6, T-7 | T-6 ∥ T-7 | `npm test -- invitations/service` |
| 4 | Surfaces | T-8, T-9, T-10, T-11 | T-8 ∥ T-9 ∥ T-10 ∥ T-11 | `npm test -- invitations && npm run typecheck` |
| 5 | Integration | T-12, T-13 | — | `npm run test:e2e -- invitations` |
| 6 | Hardening | T-14, T-15 | T-14 ∥ T-15 | `npm test -- invitations` |
| 7 | Proof | T-16 | — | see T-16 |

Phase 4 is parallel because `edify graph overlap` found its file sets and their
dependents disjoint. Phase 2's exit check asserts **failure**: sixteen red tests, one
skipped observation and no implementation is the correct state; every later phase is
measured by how much turns green.

## Phase 0 · Foundation

### T-1 · Add the invitation config block and feature flag

Phase 0 · Role implementer · Skill implementer-node · Size xs
Discharges CL-1
Depends on — · Parallel with —
Files
| path | range | action |
|---|---|---|
| src/config/index.ts | 44-71 | edit |
| src/config/index.test.ts | 30-58 | edit |
| .env.example | 12-18 | edit |
Follow the pattern at
- `src/config/index.ts:22-43` — the `sessions` block: the same zod object, the same `parseEnv` call.
Steps
1. After line 43 add `invitations`: `ttlHours` (default `72`), `maxPerHour` (`20`), `enabled` (`false`).
2. Register `INVITE_TTL_HOURS`, `INVITE_MAX_PER_HOUR`, `INVITE_ENABLED` in the same `parseEnv`
   call, and add them with defaults under `# features` in `.env.example`.
3. Mirror the test at `src/config/index.test.ts:12-29`: defaults apply when the vars are absent.
Done when
- `npm test -- config` passes and `grep INVITE_ .env.example` returns three lines

## Phase 1 · Contracts — frozen at phase end

A later task that needs one of these shapes changed stops and becomes a `/tasks` amendment.

### T-2 · Create the invitations table and its migration

Phase 1 · Role implementer · Skill implementer-postgres · Size s
Discharges REQ-1, REQ-3, CL-4
Depends on — · Parallel with —
Files
| path | range | action |
|---|---|---|
| migrations/0031_invitations.up.sql | — | new |
| migrations/0031_invitations.down.sql | — | new |
| src/db/schema.ts | 118-146 | edit |
Follow the pattern at
- `migrations/0027_members.up.sql:1-24` — `id uuid … gen_random_uuid()`, `created_at
  timestamptz`, `workspace_id … on delete cascade`, trailing index block; down is a bare `drop table`.
Steps
1. Table `invitations`: `id`, `workspace_id` (cascade), `email citext not null`, `role text check
   (role in ('admin','member'))`, `token char(32) not null unique`, `invited_by uuid references
   users(id)`, `expires_at timestamptz not null`, `accepted_at`, `revoked_at`, `created_at`.
2. Indexes, in `0027`'s trailing style: unique partial on `(workspace_id, email)` where
   `accepted_at is null and revoked_at is null`; plain on `token`.
3. The matching down migration.
4. `src/db/schema.ts`: `Invitation` type after `Member` (line 117); add to the `Tables` union (line 146).
Done when
- `npm run migrate:test` applies and rolls back cleanly; `npm run typecheck` passes
- Two pending invitations for one `(workspace_id, email)` raise a unique violation; one after the first is accepted does not

### T-3 · Freeze the invitations API contract

Phase 1 · Role implementer · Skill implementer-node · Size s
Discharges REQ-1, REQ-2, REQ-6
Depends on T-2 · Parallel with —
Files
| path | range | action |
|---|---|---|
| src/api/contracts/invitations.ts | — | new |
| src/api/contracts/index.ts | 8-14 | edit |
Follow the pattern at
- `src/api/contracts/members.ts:1-58` — one zod schema per request/response, its inferred type
  beneath each, an `Errors` const at the bottom.
Steps
1. Pairs: `CreateInvitation` (in `email`, `role`; out `id`, `email`, `role`, `expiresAt`),
   `GetInvitation` (in `token`; out `workspaceName`, `email`, `role`, `expiresAt`),
   `AcceptInvitation` (in `token`; out `workspaceId`, `membershipId`), `ListInvitations`.
2. `Errors`: `INVITE_NOT_FOUND`, `INVITE_EXPIRED`, `INVITE_ALREADY_ACCEPTED`, `INVITE_REVOKED`,
   `INVITE_RATE_LIMITED`, `INVITE_ALREADY_MEMBER`.
3. Re-export alphabetically from `src/api/contracts/index.ts:8-14`.
Done when
- `npm run typecheck && npm run lint` pass
- Every error code in the spec's error states appears in `Errors`

## Phase 2 · Verification

Assertion tests live in `tests/assertions/`, apart from co-located unit tests, so "how many
spec assertions hold" is one command's output.

### T-4 · Assertions A-1..A-11 as failing tests — lifecycle

Phase 2 · Role test · Skill test-writer-node · Size m
Discharges A-1, A-2, A-3, A-4, A-5, A-6, A-7, A-8, A-9, A-10, A-11
Verification example (A-1..A-6, A-8..A-11), property (A-7)
Depends on T-3 · Parallel with T-5
Files
| path | range | action |
|---|---|---|
| tests/assertions/invitations.lifecycle.test.ts | — | new |
| tests/assertions/invitations.token.property.test.ts | — | new |
Follow the pattern at
- `tests/assertions/members.lifecycle.test.ts:1-52` — one `describe` per REQ, one `it` per
  assertion, named `A-N: <assertion text verbatim>`; fixtures from `tests/assertions/helpers.ts:1-40`.
- `tests/assertions/auth.token.property.test.ts:1-30` — generator and shrink config for A-7.
Steps
1. One `describe` each for REQ-1, REQ-3, REQ-4, REQ-6; import types from T-3, never redeclare.
2. A-7 as a property: 1,000 generated tokens are distinct, 32 chars, base32 only.
3. Stub nothing: imports resolving to modules that do not exist yet is the expected failure.
Done when
- `npm test -- tests/assertions/invitations` reports **11 failing, 0 passing**, each failure naming its id
- `npm run typecheck` passes — the tests compile against the frozen contract

### T-5 · Assertions A-12..A-17 as failing tests — surfaces and error states

Phase 2 · Role test · Skill test-writer-node · Size m
Discharges A-12, A-13, A-14, A-15, A-16, A-17
Verification example (A-12..A-16), observation (A-17)
Depends on T-3 · Parallel with T-4
Files
| path | range | action |
|---|---|---|
| tests/assertions/invitations.api.test.ts | — | new |
| tests/assertions/invitations.ui.test.tsx | — | new |
Follow the pattern at
- `tests/assertions/members.api.test.ts:1-60` — `authedAs(admin)` from `test/helpers/auth.ts:18`, how a `403` is asserted.
Steps
1. API: A-12 admin creates (201) and the 21st in an hour gets 429, A-13 non-admin gets 403,
   A-14 the unauthenticated preview returns
   **exactly** four keys (a subset assertion misses a leak), A-15 accepting twice makes one membership.
2. UI: A-16 — each of four error codes renders its own message, asserted by text.
3. A-17 is `observation`: no test; a skipped placeholder `A-17: see T-16` keeps the count honest.
Done when
- `npm test -- tests/assertions/invitations` reports **16 failing, 1 skipped, 0 passing**

## Phase 3 · Core

### T-6 · Implement token generation and validation

Phase 3 · Role implementer · Skill implementer-node · Size s
Discharges REQ-2, CL-2
Depends on T-3 · Parallel with T-7
Files
| path | range | action |
|---|---|---|
| src/invitations/token.ts | — | new |
| src/invitations/token.test.ts | — | new |
Follow the pattern at
- `src/auth/tokens.ts:14-38` — `generate()` already makes 32-char base32; call it, never write a second generator.
Steps
1. `newInviteToken()` delegates to `generate(32)`; `isWellFormed(token)` checks shape only.
2. Test: well-formed passes, wrong length and non-base32 fail, 10,000 tokens are distinct.
Done when
- `npm test -- invitations/token` passes
- `edify graph references generate` lists this file — no second generator exists

### T-7 · Implement the invitation service

Phase 3 · Role implementer · Skill implementer-node · Size m
Discharges REQ-1, REQ-3, REQ-4, REQ-6
Depends on T-2, T-3 · Parallel with T-6
Files
| path | range | action |
|---|---|---|
| src/invitations/service.ts | — | new |
| src/invitations/service.test.ts | — | new |
Follow the pattern at
- `src/members/service.ts:1-140` — plain object of async `(db, …)` functions, `AppError` with a code from `Errors`
  from `src/errors.ts:9`, transactions via `withTx` from `src/db/tx.ts:11`.
Steps
1. Export `create`, `getByToken`, `accept`, `revoke`.
2. `create`: `INVITE_ALREADY_MEMBER` if a member already has the email (helper at
   `src/members/service.ts:62`); token from `newInviteToken()`; `expires_at = now() + ttlHours`.
3. `getByToken` checks, **in this order**: not found, expired, already accepted, revoked — an
   expired accepted invite reports as accepted, as the spec's error states require.
4. `accept`, inside `withTx`: re-validate, add the membership via `src/members/service.ts:88`,
   set `accepted_at`. `revoke`: set `revoked_at`, `INVITE_NOT_FOUND` outside the workspace.
5. Test the happy paths, each error code, and double-accept (throws; one membership).
Done when
- `npm test -- invitations/service` passes, the double-accept test asserting one `memberships` row
- A-1..A-6 and A-8..A-11 in `tests/assertions/` go green — phase 2's red, not the unit tests, is the bar

## Phase 4 · Surfaces

All four build against T-3's frozen contract; file sets are disjoint.

### T-8 · POST /workspaces/:id/invitations

Phase 4 · Role implementer · Skill implementer-node · Size s
Discharges REQ-1
Depends on T-3, T-7 · Parallel with T-9, T-10, T-11
Files
| path | range | action |
|---|---|---|
| src/api/routes/invitations.create.ts | — | new |
| src/api/routes/invitations.create.test.ts | — | new |
| src/api/router.ts | 61-74 | edit |
Follow the pattern at
- `src/api/routes/members.add.ts:1-52` — `requireRole('admin')`, schema parse, service call, `201` + `Location`.
Steps
1. Guard with `requireRole('admin')` (`src/api/middleware/role.ts:7`); parse with `createInvitationSchema`.
2. Return `201` with `Location: /workspaces/:id/invitations/:inviteId`.
3. Register in `src/api/router.ts:61-74`, between `members` and `projects`.
4. Test: admin succeeds, non-admin `403`, duplicate pending `409`.
Done when
- `npm test -- invitations.create` passes

### T-9 · GET /invitations/:token — the unauthenticated preview

Phase 4 · Role implementer · Skill implementer-node · Size s
Discharges REQ-2
Depends on T-3, T-7 · Parallel with T-8, T-10, T-11
Files
| path | range | action |
|---|---|---|
| src/api/routes/invitations.get.ts | — | new |
| src/api/routes/invitations.get.test.ts | — | new |
| src/api/router.ts | 61-74 | edit |
| src/api/middleware/auth.ts | 40-52 | edit |
Follow the pattern at
- `src/api/routes/password-reset.get.ts:1-38` — the only other unauthenticated token lookup.
Steps
1. Return only `workspaceName`, `email`, `role`, `expiresAt` — the body is the whole security surface.
2. Add the path to `publicRoutes` at `src/api/middleware/auth.ts:40-52`; register in the router.
3. Test: valid token returns exactly those keys; expired `410`; unknown `404`.
Done when
- `npm test -- invitations.get` passes, asserting the exact key set

### T-10 · POST /invitations/:token/accept

Phase 4 · Role implementer · Skill implementer-node · Size s
Discharges REQ-3
Depends on T-3, T-7 · Parallel with T-8, T-9, T-11
Files
| path | range | action |
|---|---|---|
| src/api/routes/invitations.accept.ts | — | new |
| src/api/routes/invitations.accept.test.ts | — | new |
| src/api/router.ts | 61-74 | edit |
Follow the pattern at
- `src/api/routes/members.add.ts:1-52` — same shape, authenticated rather than role-guarded.
Steps
1. Call `accept` with `req.user.id`; return `200` `{workspaceId, membershipId}`; register in the router.
2. Test: logged in works, logged out `401`, accepted twice `409`, a different email succeeds (D-1).
Done when
- `npm test -- invitations.accept` passes, the twice-accepted case asserting one membership

### T-11 · The invite-accept page

Phase 4 · Role implementer · Skill implementer-react · Size m
Discharges REQ-2, REQ-6
Depends on T-3 · Parallel with T-8, T-9, T-10
Files
| path | range | action |
|---|---|---|
| web/src/pages/AcceptInvite.tsx | — | new |
| web/src/pages/AcceptInvite.test.tsx | — | new |
| web/src/routes.tsx | 28-41 | edit |
Follow the pattern at
- `web/src/pages/ResetPassword.tsx:1-96` — token from `useParams`, `useQuery`, states loading → error → ready → submitted.
Steps
1. Fetch the preview with the client at `web/src/api/client.ts:12`.
2. One sentence per error code (expired, accepted, revoked, not found), never a generic failure.
3. Accept → navigate to `/workspaces/:workspaceId`; logged out → `/login?next=…` (`ResetPassword.tsx:44`).
4. Register `/invite/:token` in the public block of `web/src/routes.tsx:28-41`; MSW test per state.
Done when
- `npm test -- AcceptInvite` passes, each error code asserted by its own text

## Phase 5 · Integration

### T-12 · Send the invitation email

Phase 5 · Role implementer · Skill implementer-node · Size s
Discharges REQ-1, REQ-5
Depends on T-8 · Parallel with —
Files
| path | range | action |
|---|---|---|
| src/email/templates/invitation.tsx | — | new |
| src/email/templates/invitation.test.tsx | — | new |
| src/api/routes/invitations.create.ts | 30-46 | edit |
Follow the pattern at
- `src/api/routes/members.add.ts:38-45` — enqueue the mail, never send it inline: mail failure never fails the request.
Steps
1. Template `{workspaceName, inviterName, acceptUrl, expiresAt}`; `acceptUrl` is
   `${config.publicUrl}/invite/${token}` — the route from T-11.
2. Enqueue after the service call, before the response; test the link matches T-11's route.
Done when
- `npm test -- email/invitation` passes; a forced mailer failure still returns `201`

### T-13 · End-to-end: invite, open, accept

Phase 5 · Role implementer · Skill implementer-node · Size m
Discharges REQ-1, REQ-2, REQ-3
Depends on T-8, T-9, T-10, T-11, T-12 · Parallel with —
Files
| path | range | action |
|---|---|---|
| e2e/invitations.spec.ts | — | new |
Follow the pattern at
- `e2e/password-reset.spec.ts:1-88` — seeded users, outbox helper `e2e/helpers/outbox.ts:9`, serial describe blocks.
Steps
1. Seed an admin and a non-member; invite through the UI; read the link from the outbox.
2. Accept as the non-member; assert the workspace page and the new member's role.
3. Re-open the link; assert the already-accepted message.
Done when
- `npm run test:e2e -- invitations` passes twice in a row from a clean database

## Phase 6 · Hardening

### T-14 · Rate-limit invitation creation

Phase 6 · Role implementer · Skill implementer-node · Size s
Discharges CL-3
Depends on T-8 · Parallel with T-15
Files
| path | range | action |
|---|---|---|
| src/api/routes/invitations.create.ts | 12-20 | edit |
| src/api/routes/invitations.create.test.ts | 60-84 | edit |
Follow the pattern at
- `src/api/middleware/rateLimit.ts:22-40` — exists; this is a registration, as at `src/api/routes/password-reset.request.ts:14`.
Steps
1. `rateLimit({key: 'workspace', max: config.invitations.maxPerHour, window: '1h'})` after the role guard.
2. Test: request `maxPerHour + 1` returns `429` `INVITE_RATE_LIMITED`.
Done when
- `npm test -- invitations.create` passes; `grep -n '20' src/api/routes/invitations.create.ts` returns nothing

### T-15 · Audit-log every invitation lifecycle event

Phase 6 · Role implementer · Skill implementer-node · Size s
Discharges CL-5
Depends on T-7 · Parallel with T-14
Files
| path | range | action |
|---|---|---|
| src/invitations/service.ts | 40-160 | edit |
| src/invitations/service.test.ts | 120-150 | edit |
Follow the pattern at
- `src/members/service.ts:96-104` — one audit record `{actor, action, subject}` inside the same transaction.
Steps
1. Record `invitation.created|accepted|revoked` inside the existing transactions; subject is the invitation id.
2. Test one audit row per operation, and none after a rollback.
Done when
- `npm test -- invitations/service` passes, the rollback case asserting zero audit rows

## Phase 7 · Proof

### T-16 · Verify the feature

Phase 7 · Role verifier · Skill verifier · Size m
Discharges REQ-1, REQ-2, REQ-3, REQ-4, REQ-5, REQ-6, CL-1, CL-2, CL-3, CL-4, CL-5, CL-6, CL-7
Depends on all · Parallel with —

Fresh session that wrote none of the code. Files: none — evidence, not code.
Steps
1. `npm test && npm run test:e2e`, raw output; `tests/assertions/invitations` reports **16 passing, 1 skipped, 0 failing**.
2. `git log --stat`: every `tests/assertions/` file landed before the source it exercises.
3. Real run: dev stack, invite, pull the link from the outbox, accept in a fresh browser profile; paste the transcript.
4. A-17 / CL-7 (`observation`): keyboard-only and screen-reader pass on the accept page, recording attached.
5. Walk `## Coverage`; a declared kind downgraded (property → example) is reported, not accepted.
6. One design: a second token generator? two error-mapping styles? `invite` vs `invitation` naming?
Done when
- The assertion count above, the transcript and the recording are in `verification.md` as raw output
- Every coverage row is satisfied, waived, or blocked; the one-design read says what was checked

## Coverage

| source | what it is | asserted by | built by |
|---|---|---|---|
| REQ-1 | An admin can invite someone by email | T-4, T-5 | T-2, T-7, T-8, T-12, T-13 |
| REQ-2 | The invitee sees who invited them before accepting | T-5 | T-3, T-9, T-11, T-13 |
| REQ-3 | Accepting the link creates the membership | T-4, T-5 | T-2, T-7, T-10, T-13 |
| REQ-4 | An admin can revoke a pending invitation | T-4 | T-7 |
| REQ-5 | The invitee receives an email with the link | T-4 | T-12 |
| REQ-6 | Expired, used, and revoked links each say what happened | T-4, T-5 | T-3, T-7, T-11 |
| CL-1 | The feature is behind a flag | — | T-1 |
| CL-2 | Tokens are unguessable and single-use | T-4 (property) | T-6, T-7 |
| CL-3 | Invitation creation is rate-limited | T-5 | T-14 |
| CL-4 | The migration has a rollback | — | T-2 |
| CL-5 | Lifecycle events are audit-logged | T-4 | T-15 |
| CL-6 | Personal data has a retention rule | `waived` — the only datum is an email the admin already holds; cascade-deleted with the workspace | |
| CL-7 | The accept page is accessible | T-5 (skipped placeholder) | `observation` — T-16 step 4 |

A builder with no asserter is a requirement nobody wrote a failing test for. The two dashes
are structural (a flag exists; a down migration runs) and their done-checks cover them; any
other dash in `asserted by` blocks the gate.

## Decisions

Empty at the gate. D-1 was appended by T-10's builder during the run.

| # | decision | why | binds |
|---|---|---|---|
| D-1 | Accepting with a different logged-in email succeeds | REQ-3 says the link is the credential; forwarding is a real workflow | T-10, T-13, T-16 |

