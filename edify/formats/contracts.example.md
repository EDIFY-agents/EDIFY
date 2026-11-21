# contract — invitations API

> **Worked example for `design.format.md` § contracts/.** Saved as
> `specs/team-invitations/contracts/invitations.md`. One file per interface the feature
> exposes — endpoints here; a CLI's commands, a library's public functions, an event's
> payload elsewhere. Frozen at the end of phase 1; a later change is a `/tasks` amendment.

## Endpoints

| method · path | auth | request | 2xx response | errors |
|---|---|---|---|---|
| `POST /workspaces/:id/invitations` | admin of `:id` | `{email, role}` | 201 `{id, email, role, expiresAt}` + `Location` | 403, 409 `INVITE_ALREADY_MEMBER`, 429 `INVITE_RATE_LIMITED` |
| `GET /workspaces/:id/invitations` | admin of `:id` | — | 200 `[{id, email, role, expiresAt, state}]` | 403 |
| `GET /invitations/:token` | none | — | 200 `{workspaceName, email, role, expiresAt}` — exactly these keys (A-14) | 404 `INVITE_NOT_FOUND`, 410 `INVITE_EXPIRED` · `INVITE_REVOKED` · `INVITE_ALREADY_ACCEPTED` |
| `POST /invitations/:token/accept` | signed in | — | 200 `{workspaceId, membershipId}` | same as above |
| `DELETE /workspaces/:id/invitations/:inv` | admin of `:id` | — | 204 | 403, 409 `INVITE_ALREADY_ACCEPTED` |

## Error codes — `Errors` in `src/api/contracts/invitations.ts`

`INVITE_NOT_FOUND` · `INVITE_EXPIRED` · `INVITE_REVOKED` · `INVITE_ALREADY_ACCEPTED` ·
`INVITE_ALREADY_MEMBER` · `INVITE_RATE_LIMITED`. Body shape for every error:
`{ "error": "<CODE>", "message": "<human sentence>" }` — as `src/api/contracts/members.ts:50-58`.

## Rules

- `:token` is redacted in every log line (SC-3).
- Accept is idempotent per token: a repeat returns `INVITE_ALREADY_ACCEPTED`, never a
  second membership (A-15).
- Schemas are zod objects with `z.infer` types beside them; the UI imports the same types.
