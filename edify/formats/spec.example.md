---
feature: team-invitations
status: approved
date: 2026-08-04
supersedes: —
brief-source: —
---

# spec — team invitations

> **Worked example for `spec.format.md`.** One feature carried through every file:
> this spec, `plan.example.md`, `research.example.md`, `data-model.example.md`,
> `contracts.example.md`, `quickstart.example.md`, `tasks.example.md`. The shape
> is what to copy, not the length; the ids here are the ones the task list discharges.

## Brief

"Admins should be able to invite people to their workspace by email. The person clicks the
link and they're in."

## User stories

### US1 — Invite and join (P1, the MVP)
An admin enters an email and a role; the invitee gets a link, sees who invited them, and
joins in one click. **Independent test:** invite → open link → accept → the invitee is a
member, with no other story built.
1. **Given** an admin of workspace W, **When** they invite `a@x.io` as member, **Then** a
   pending invitation exists and one email with the link is queued.
2. **Given** a valid link, **When** the invitee opens it signed out, **Then** they see the
   workspace name, inviter role and expiry — and nothing else.
3. **Given** a valid link, **When** it is accepted, **Then** exactly one membership exists.

### US2 — Revoke (P2)
**Independent test:** invite → revoke → the link reports revoked.
1. **Given** a pending invitation, **When** an admin revokes it, **Then** its link says so.

### US3 — Links that explain themselves (P3)
**Independent test:** each dead link shows its own message.
1. **Given** an expired, used, revoked or unknown link, **When** opened, **Then** the page
   names which, and offers the next step.

## Intent

1. Growing a workspace takes one action by an admin and one by the invitee.
2. A link is the credential: whoever holds it can join, once, before it expires.
3. A dead link never leaves the invitee guessing why.

## Constraints

- TypeScript 5.4, Node 20 LTS, Postgres 15, React 18 — as in `package.json:1-40`.
- `npm test`, `npm run test:e2e`, `npm run typecheck`, `npm run lint` (CI: `.github/workflows/ci.yml:20-58`).
- Mail goes through the existing queue (`src/email/mailer.ts:12-48`); never sent inline.
- Roles are `admin` and `member` (`src/db/schema.ts:96-117`).

## Requirements

| id | requirement | assertions |
|---|---|---|
| REQ-1 | An admin can invite someone by email | A-1, A-2, A-7, A-12, A-13 |
| REQ-2 | The invitee sees who invited them before accepting | A-14, A-17 |
| REQ-3 | Accepting the link creates the membership | A-3, A-4, A-15 |
| REQ-4 | An admin can revoke a pending invitation | A-5, A-10, A-11 |
| REQ-5 | The invitee receives an email with the link | A-9 |
| REQ-6 | Expired, used, and revoked links each say what happened | A-6, A-8, A-16 |

## Assertions

| id | assertion | verification | citation |
|---|---|---|---|
| A-1 | Creating an invitation stores it pending, expiring `ttlHours` (72) later | example | new |
| A-2 | Inviting an existing member returns `INVITE_ALREADY_MEMBER` | example | src/services/members.ts:40-66 |
| A-3 | Accepting a valid token creates one membership with the invited role | example | src/services/members.ts:20-39 |
| A-4 | A second accept of the same token returns `INVITE_ALREADY_ACCEPTED` | example | new |
| A-5 | A revoked token returns `INVITE_REVOKED` | example | new |
| A-6 | A token past `expires_at` returns `INVITE_EXPIRED` | example | new |
| A-7 | Tokens are 32 chars of base32 and never repeat across 1,000 draws | property | src/auth/tokens.ts:14-38 |
| A-8 | An unknown token returns `INVITE_NOT_FOUND` | example | new |
| A-9 | Creating an invitation enqueues exactly one email whose link is `/invite/<token>` | example | src/email/mailer.ts:12-48 |
| A-10 | Create, accept and revoke each write one audit event | example | src/audit/log.ts:8-30 |
| A-11 | Revoking an accepted invitation changes nothing and returns `INVITE_ALREADY_ACCEPTED` | example | new |
| A-12 | An admin's POST returns 201 + `Location`; the 21st in an hour returns 429 `INVITE_RATE_LIMITED` | example | src/api/routes/members.add.ts:18-77 |
| A-13 | A non-admin's POST returns 403 | example | src/api/middleware/auth.ts:40-52 |
| A-14 | The signed-out preview returns exactly `workspaceName, email, role, expiresAt` | example | new |
| A-15 | Two concurrent accepts of one token create one membership | example | new |
| A-16 | The accept page shows a distinct message for each of the four error codes | example | new |
| A-17 | The accept page works by keyboard alone and with a screen reader (surface: browser) | observation | new |

## Key entities

- **Invitation** — a pending offer of a role in a workspace to an email; single-use, expiring.
- **Membership** — existing (`src/db/schema.ts:96-117`); created by an accepted invitation.
Fields and states: `data-model.md`.

## Success criteria

- **SC-1** — An invitee goes from email to member in under 30 seconds (quickstart step 4).
- **SC-2** — Zero support tickets of the form "my link doesn't work" with no stated reason.
- **SC-3** — No invitation token appears in logs or analytics events.

## What this entails

| id | what it entails | status |
|---|---|---|
| CL-1 | The feature is behind a flag | REQ-1 — `INVITE_ENABLED` |
| CL-2 | Tokens are unguessable and single-use | REQ-1, REQ-3 — A-4, A-7 |
| CL-3 | Invitation creation is rate-limited | REQ-1 — A-12 — adversary-found |
| CL-4 | The migration has a rollback | REQ-3 |
| CL-5 | Lifecycle events are audit-logged | REQ-4 — A-10 — adversary-found |
| CL-6 | Personal data has a retention rule | waived — the only datum is an email the admin already holds |
| CL-7 | The accept page is accessible | REQ-2 — A-17 |

## Assumptions

- The workspace already has at least one admin (`src/services/workspaces.ts:30-52`).
- Invitees may already have an account; signing up is the existing flow, not new work.

## Open questions

| # | question | readings | adopted | who resolves |
|---|---|---|---|---|
| Q-1 | Must the accepting user's email match the invited one? | match required · link is the credential | link is the credential (intent 2) | product — accepted at gate |

## Non-goals

- Bulk or CSV invitations. Invitation links shared in chat (no email). SSO-provisioned members.
