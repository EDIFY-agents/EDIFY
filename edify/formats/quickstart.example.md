# quickstart — team-invitations

> **Worked example for `design.format.md` § quickstart.md.** The runnable proof that the
> feature works end to end: prerequisites, commands, expected outcomes. `/verify` runs it
> and pastes the output; it is not implementation and holds no code beyond the commands.

## Prerequisites

- `docker compose up -d db redis mail` — Postgres, Redis, and the mail sandbox on `:8025`.
- `.env` with `INVITE_ENABLED=true`; `MAIL_SANDBOX_URL` from the secret store (name only).
- `npm run migrate && npm run seed` — workspace `acme`, admin `ada@acme.test`, member `bo@acme.test`.

## Steps

| # | do | expect | proves |
|---|---|---|---|
| 1 | `curl -sX POST :3000/workspaces/acme/invitations -H "$ADA" -d '{"email":"cy@x.io","role":"member"}'` | `201`, `Location` header, `expiresAt` 72 h ahead | A-1, A-12 |
| 2 | `curl -s :8025/api/messages \| jq '.[0].to, .[0].links'` | one message to `cy@x.io` with `/invite/<32 chars>` | A-9 |
| 3 | `curl -s :3000/invitations/$TOKEN` (signed out) | exactly `workspaceName, email, role, expiresAt` | A-14 |
| 4 | Browser, fresh profile: open the link, sign up as `cy`, accept | lands in `acme`; under 30 s from step 2 | A-3, SC-1 |
| 5 | Open the same link again; then a revoked one; then an expired one (`npm run invite:expire $ID`) | three different messages, each naming what happened | A-4, A-5, A-6, A-16 |
| 6 | As `bo` (member): repeat step 1 | `403` | A-13 |
| 7 | Keyboard only, then VoiceOver/NVDA, on the accept page | every control reachable and announced; recording saved | A-17 (observation) |

## Done when

All seven expectations hold, `grep -r "$TOKEN" logs/` finds nothing (SC-3), and the output
of every step is pasted into `verification.md` § Tiers.
