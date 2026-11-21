# data model — team-invitations

> **Worked example for `design.format.md` § data-model.md.** Entities from the spec's key
> entities, with fields, rules from the requirements, and the state machine. No SQL: the
> migration is a task; this is what the migration must satisfy.

## Invitation (new)

| field | type | rule | from |
|---|---|---|---|
| id | uuid | primary key | — |
| workspace_id | uuid | → workspaces.id, cascade delete | CL-6 |
| email | citext | required, valid address | REQ-1 |
| role | `admin` \| `member` | required | REQ-1 |
| token | char(32) | base32, unique, never logged | A-7, CL-2, SC-3 |
| invited_by | uuid | → users.id | REQ-2 |
| expires_at | timestamptz | `created_at + ttlHours` (72) | A-1, A-6 |
| accepted_at · revoked_at | timestamptz? | at most one is set | A-4, A-5 |
| created_at | timestamptz | default now | — |

**Uniqueness** one *pending* invitation per `(workspace_id, email)` — a partial unique
index where `accepted_at` and `revoked_at` are null. **Relationship** an accepted
invitation creates exactly one Membership (`src/db/schema.ts:96-117`).

## States

```
          create
            │
            ▼
        ┌────────┐  accept (token valid, now < expires_at)   ┌──────────┐
        │pending │ ─────────────────────────────────────────▶ │ accepted │
        └────────┘                                            └──────────┘
          │    │ revoke (admin)        ┌─────────┐
          │    └─────────────────────▶ │ revoked │
          │ now ≥ expires_at           └─────────┘
          ▼
      ┌─────────┐    accepted, revoked, expired: terminal; every transition writes
      │ expired │    one audit event (A-10). Expired is derived, never stored.
      └─────────┘
```

| from | event | to | error otherwise |
|---|---|---|---|
| pending | accept | accepted | `INVITE_EXPIRED` if past `expires_at` |
| pending | revoke | revoked | — |
| accepted | accept · revoke | accepted | `INVITE_ALREADY_ACCEPTED` (A-4, A-11) |
| revoked | accept | revoked | `INVITE_REVOKED` (A-5) |
