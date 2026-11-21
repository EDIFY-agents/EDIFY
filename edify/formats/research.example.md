# research — team-invitations

> **Worked example for `design.format.md` § research.md.** One block per open question or
> technology choice the plan had to settle. Each ends in a decision the plan's table repeats;
> the evidence lives here so the plan stays short. Nothing here is `[NEEDS CLARIFICATION]`.

## R-1 · How are tokens minted? → D-1

- **Decision** `crypto.randomBytes(20)` → base32, 32 characters.
- **Rationale** 160 bits of entropy; URL-safe without escaping; the repository already
  mints password-reset tokens this way (`src/auth/tokens.ts:14-38`), so one helper serves both.
- **Alternatives** uuid v4 — 122 bits and hyphenated, and a second token style in the
  codebase. Signed JWT — revocation needs a table anyway, so the signature buys nothing.
- **Evidence** `edify graph where mintToken` → `src/auth/tokens.ts:14`; Node 20.11 docs for
  `crypto.randomBytes` (via the `docs` server, `docs@node-20.11`).

## R-2 · Where does the rate limit live? → D-2

- **Decision** `rate-limiter-flexible` 5.0.3 on the existing Redis, keyed by admin id,
  20 per rolling hour.
- **Rationale** Four API pods: an in-process counter allows 80/hour. Redis is already a
  dependency (`docker-compose.yml:30-41`); the library is used by `src/api/middleware/login-limit.ts:1-40`.
- **Alternatives** in-process counter (wrong across pods); a database count (an extra
  query on every create, and a race at the boundary).

## R-3 · Must the accepting user's email match? → spec Q-1

- **Decision** No — the link is the credential (spec intent 2).
- **Rationale** Forwarding an invite to a colleague's other address is the common case
  the admin wants; the audit log (CL-5) records who accepted.
- **Alternatives** require a match — blocks the common case and still leaks the workspace
  name through the preview.

## R-4 · Email template → D-3 (a default)

- **Decision** a `react-email` 2.1.0 template beside the existing ones.
- **Rationale** nothing to decide: the mailer already renders these (`src/email/mailer.ts:12-48`).
