"""`edify license` — what this machine is entitled to, and how to change it.

`status` says which plan this machine is on and what a licence would add;
`activate` installs a signed token; `deactivate` removes it. There is no purchase
and no price: the public edition is every command, uncapped, and a team or
partner licence is issued on request.

Offline throughout. Activation writes a signed token to a file; nothing is sent
anywhere, and no command in this CLI opens a socket to check a plan.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..context import Context
from ..distribution import CONTACT
from ..errors import EdifyError
from ..licensing import tier
from ..licensing.token import parse
from ..ui import MARKS


def status(ctx: Context) -> int:
    ent = ctx.entitlement
    ctx.out.data(ent.as_dict())

    ctx.out.field("plan", ent.plan)
    if ent.license:
        lic = ent.license
        ctx.out.field("licensed", f"{lic.email or lic.subject or 'unnamed'} · {lic.seats} seat(s)")
        if lic.expires_at:
            when = time.strftime("%Y-%m-%d", time.gmtime(lic.expires_at))
            ctx.out.field("expires", f"{when} ({lic.days_left} days)")
    if ent.problem:
        ctx.out.warn(f"a licence was found and not accepted: {ent.problem}")
    ctx.out.field("source", str(ent.source))
    ctx.out.line("")

    ctx.out.line(ctx.out.c("entitlements", "muted"))
    for feature, description in sorted(tier.FEATURE_NAMES.items()):
        allowed = ent.allows(feature)
        if ctx.out.fancy:
            # At a terminal, the site's state device: enforced, or not covered.
            mark = ctx.out.c(MARKS["pass"], "signal") if allowed else ctx.out.c(MARKS["uncovered"], "faint")
        else:
            mark = "[yes]" if allowed else "[no ]"
        ctx.out.line(f"  {mark} {feature:<19} {ctx.out.c(description, 'dim')}")
    ctx.out.line("")
    ctx.out.field("registry", 'unlimited' if ent.mcp_cap is None else f'{ent.mcp_cap} server')
    if not ent.paid:
        ctx.out.line("")
        ctx.out.line("public edition — every command, uncapped, no account")
        ctx.out.line(f"team edition  edify license activate <token>  ·  ask for one: {CONTACT}")
    return 0


def activate(ctx: Context) -> int:
    token = ctx.args.token.strip()
    if Path(token).expanduser().is_file():
        token = Path(token).expanduser().read_text(encoding="utf-8").strip()

    verdict = parse(token)
    if not verdict.valid or verdict.license is None:
        raise EdifyError(f"not activated — {verdict.reason}")

    path = tier.save(token)
    lic = verdict.license
    ctx.out.data({"path": str(path), "license": lic.as_dict()})
    ctx.out.ok(f"{lic.plan} plan activated for {lic.email or lic.subject or 'this machine'}")
    ctx.out.line(str(path))
    return 0


def deactivate(ctx: Context) -> int:
    removed = tier.clear()
    ctx.out.data({"removed": removed})
    ctx.out.line("licence removed" if removed else "no licence file to remove")
    return 0
