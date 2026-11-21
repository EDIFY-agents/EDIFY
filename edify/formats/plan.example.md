---
feature: team-invitations
spec: spec.md
status: approved
milestones: 2
date: 2026-08-05
supersedes: —
---

# plan — team-invitations

> **Worked example for `plan.format.md`.** Written because two people and a swarm build
> this feature at once and a rate limiter is shared — not because it is large. Calibrate
> on what each row commits to: an exact version and the alternative it beat, a gate you can
> measure, a seed with a line range. Its four design files sit beside it (`design.format.md`).

## Summary

Invitation rows with a single-use 32-char token; four endpoints frozen in
`contracts/invitations.md`; email through the existing queue; one accept page.

## Technical context

**Language/Version** TypeScript 5.4 on Node 20 LTS · **Primary dependencies** Fastify 4.26,
zod 3.23, React 18.3 · **Storage** Postgres 15 (`migrations/`) · **Testing** vitest 1.6,
Playwright 1.47 · **Target** Linux containers, evergreen browsers · **Project type** web
service + SPA · **Performance** create p95 < 150 ms · **Constraints** feature-flagged; no
token in logs · **Scale** ≤ 20 invitations per admin per hour.

## Constitution check

Gates from `.edify/constitution.md`, checked before research and again after design:
I. tests before code — phase 2 is red first ✓ · II. no new runtime service ✓ (Redis
already runs) · III. every surface behind auth or a single-use secret ✓.

## Design artefacts

`research.md` (D-1..D-3 evidence) · `data-model.md` (Invitation, its states) ·
`contracts/invitations.md` (four endpoints, six error codes) · `quickstart.md` (the
end-to-end run `/verify` repeats).

## Milestones

| id | delivers | requirements covered | gate | size |
|---|---|---|---|---|
| M1 | Invitation lifecycle: table, contract, service, create/accept/revoke, email | REQ-1, REQ-3, REQ-4, REQ-5 | `npm test -- invitations/service` green; quickstart steps 1–3 pass | m |
| M2 | Signed-out preview and the accept page with its four error states | REQ-2, REQ-6 | quickstart steps 4–5 pass; A-17 recording attached | s |

M2 starts after M1's phase 1 — it consumes the frozen contract, not the service.

## Technology decisions

| # | decision | version | beat | why |
|---|---|---|---|---|
| D-1 | Tokens from Node's `crypto.randomBytes(20)`, base32-encoded | 20.11 | uuid v4 | 160 bits, URL-safe, already how `src/auth/tokens.ts:14-38` mints reset tokens |
| D-2 | Rate limit with `rate-limiter-flexible` on the existing Redis | 5.0.3 | in-process counter | survives restarts and works across the four API pods |
| D-3 | Email template in the existing `react-email` setup — a default | 2.1.0 | — | the mailer already renders it; no decision to revisit |

## Cross-cutting

- **Migration** `0031_invitations` belongs to M1; nothing else takes 0031.
- **Shared component** the `Errors` const in the contract is the only source of error codes;
  API and UI both import it.
- **Verification budget** A-7 is a property test (fast-check 3.15.0, 1,000 runs, < 2 s);
  A-17 is an observation on the browser surface (Playwright + axe, recording attached);
  REQ-5 runs against the mail sandbox (`MAIL_SANDBOX_URL`, secret name only).

## Project structure

```
src/api/contracts/invitations.ts   src/api/routes/invitations.*.ts
src/invitations/{token,service}.ts src/email/templates/invitation.tsx
src/pages/invite/[token].tsx       migrations/0031_invitations.{up,down}.sql
tests/assertions/invitations.*     specs/team-invitations/{spec,plan,research,data-model,quickstart,tasks}.md
```

## Per-milestone

### M1 — lifecycle

Goal: an invitation can be created, accepted once and revoked. Size m · affected
`src/invitations/`, `src/api/`, `migrations/`.

Context seeds
- src/services/members.ts:20-66 — the membership creation the accept path reuses
- src/api/routes/members.add.ts:18-77 — handler shape and its mail-queue call
- src/auth/tokens.ts:14-38 — the token minting D-1 copies

### M2 — preview and page

Goal: a signed-out visitor sees the preview and a precise message for each dead link.
Size s · affected `src/pages/invite/`, `src/api/routes/invitations.get.ts`.

Context seeds
- src/pages/reset/[token].tsx:1-80 — the closest existing token page
- src/api/middleware/auth.ts:40-52 — the unauthenticated route allowlist

## Parallelization

M1 phase 4 (four endpoints) runs as a swarm: `edify graph overlap` shows the route files
disjoint. M2's page and M1's service sit in different communities of `MAP.md`; the only
bridge between them is the contract, which is frozen first.

## Risks

| risk | milestone | mitigation |
|---|---|---|
| A token leaks through request logs | M1 | `src/api/middleware/log.ts:12-30` redacts `:token` path params; A-14 asserts the preview's key set |
| Two accepts race and create two memberships | M1 | unique partial index + transaction (data-model); A-15 |
| Invitation spam from a compromised admin | M1 | D-2 rate limit; audit events (CL-5) |
