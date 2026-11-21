"""`edify swarm` — lease tasks so many agents and people can build one feature at once.

The loop every worker runs, whether it is the only one or one of fifty:

    edify swarm claim            → a task id, or exit 1 when nothing is ready
    edify swarm prompt <id>      → skill + task + decisions + graph slice + servers
    build it, run its done-check, commit on swarm/<id>
    edify swarm done <id>        → recorded; the next claim may now unblock
                                   (--status partial|failed|needs_input → a block)

The orchestrator's two: `status` (who holds what, what is expiring) and `merge`
(finished branches in a safe order; `--apply` lands them).

Exit codes: 0 ok, 1 nothing ready / not yours / merge conflict, 2 bad input.
"""

from __future__ import annotations

import subprocess
import time
from datetime import date

from .. import skills
from .. import swarm
from ..context import Context
from ..errors import EdifyError
from ..formats import mcp as mcp_format
from ..formats import tasks as tasks_format
from ..graph import insight


def _setup(ctx: Context):
    path = swarm.find_feature(ctx.layout.root, getattr(ctx.args, "feature", None))
    feature = path.parent.name
    parsed = tasks_format.parse(path, ctx.layout.rel(path))
    store = swarm.store_for(ctx.layout.root, feature, getattr(ctx.args, "git", False))
    graph = ctx.store if ctx.store.exists() else None
    return path, feature, parsed, store, graph


def _state_cell(row: swarm.Row) -> str:
    return f"blocked ({row.status})" if row.state == "blocked" and row.status else row.state


def board(ctx: Context) -> int:
    path, feature, parsed, store, graph = _setup(ctx)
    rows = swarm.board(parsed, store.all(), graph)
    ctx.out.data(
        [
            {
                "task": r.task.id, "title": r.task.title, "phase": r.task.phase, "state": r.state,
                "status": r.status, "agent": r.lease.agent if r.lease else "", "why": r.why,
            }
            for r in rows
        ]
    )
    counts = {s: sum(r.state == s for r in rows) for s in ("ready", "leased", "waiting", "blocked", "done")}
    ctx.out.line(f"{feature}: " + " · ".join(f"{v} {k}" for k, v in counts.items()))
    ctx.out.table(
        ["task", "ph", "state", "who / why", "title"],
        [
            [r.task.id, str(r.task.phase if r.task.phase is not None else "-"), _state_cell(r),
             (r.lease.agent if r.state in ("leased", "done") and r.lease else r.why)[:40], r.task.title[:48]]
            for r in rows
        ],
    )
    return 0


def claim(ctx: Context) -> int:
    path, feature, parsed, store, graph = _setup(ctx)
    agent = ctx.args.agent or swarm.whoami()
    rows = swarm.board(parsed, store.all(), graph)
    wanted = [r for r in rows if r.state == "ready" and (not ctx.args.task or r.task.id == ctx.args.task)]
    if ctx.args.task and not wanted:
        state = next((r.state + (f" ({r.why})" if r.why else "") for r in rows if r.task.id == ctx.args.task), "unknown")
        ctx.out.data({"claimed": None, "state": state})
        ctx.out.line(f"{ctx.args.task} is not ready: {state}")
        return 1
    now = int(time.time())
    for row in wanted:
        lease = swarm.Lease(row.task.id, agent, now, now + 60 * ctx.args.ttl, row.task.paths)
        if store.put("leased", lease):
            worktree = _worktree(ctx, row.task.id) if ctx.args.worktree else ""
            ctx.out.data({"claimed": row.task.id, "feature": feature, "agent": agent,
                          "expires": lease.expires, "files": lease.files, "worktree": worktree})
            ctx.out.line(f"{row.task.id}\t{row.task.title}")
            ctx.out.line(f"next: edify swarm prompt {row.task.id} {feature}")
            if worktree:
                ctx.out.line(f"worktree: {worktree}")
            return 0
    waiting = sum(r.state in ("waiting", "leased") for r in rows)
    left = sum(r.state != "done" for r in rows)
    ctx.out.data({"claimed": None, "open": left, "waiting": waiting})
    ctx.out.line("all done" if not left else f"nothing ready — {waiting} waiting on others; retry after a `done`")
    return 1


def prompt(ctx: Context) -> int:
    """Everything a fresh agent needs for one task, and nothing else."""
    path, feature, parsed, store, graph = _setup(ctx)
    task = parsed.by_id(ctx.args.task)
    if task is None:
        raise EdifyError(f"no task {ctx.args.task} in {ctx.layout.rel(path)}")
    phase = str(task.phase if task.phase is not None else swarm.DEFAULT_PHASE)
    role = task.role or "implementer"
    skill_path = _skill_path(ctx, task, phase)
    parts = [f"# {task.id} · {task.title}", f"feature `{feature}` · phase {phase} · {ctx.layout.rel(path)}", ""]
    parts += ["## Method", f"Load `{skill_path}` and follow it." if skill_path else "No skill resolves; follow the task.", ""]
    parts += ["## Task", swarm.block_text(path, task), ""]
    decisions = _section(path, "Decisions")
    if decisions:
        parts += ["## Decisions so far (binding)", decisions, ""]
    if graph is not None:
        query = " ".join([task.title, *task.paths])
        parts += ["## Graph slice", insight.context(graph, query, budget=ctx.args.budget).text, ""]
    registry = mcp_format.parse(ctx.layout.mcp) if ctx.layout.mcp.exists() else None
    # The same scoping `edify mcp config` applies, so the prompt never names a server
    # the spawn's config will not contain.
    servers = registry.for_spawn(role, phase) if registry else []
    parts += ["## Servers",
              (", ".join(f"{s.name}@{s.version}" for s in servers) + f" — `edify mcp config {role} {phase}`")
              if servers else "none — do not connect any", ""]
    parts += [
        "## Loop",
        "1. Work only in the files above; the graph answers structure (`edify graph where|explain|context`).",
        "2. Run every `Done when` check; paste the raw output in your hand-back.",
        f"3. Commit on branch `swarm/{task.id}`; then `edify swarm done {task.id} {feature}`.",
        f"4. Not completed? `edify swarm done {task.id} {feature} --status partial|failed|needs_input"
        " --reason \"…\"` — one line, then stop.",
        "5. A decision the task left open goes to `## Decisions` in tasks.md, with why.",
    ]
    text = "\n".join(parts)
    ctx.out.data({"task": task.id, "skill": skill_path, "servers": [s.name for s in servers], "prompt": text})
    ctx.out.line(text)
    return 0


def _fenced(ctx: Context, held: swarm.Lease | None, agent: str, task_id: str, key: str) -> bool:
    """True (and says so) when another agent holds a live lease and --force is absent."""
    if held is None or not held.live or held.agent == agent or getattr(ctx.args, "force", False):
        return False
    ctx.out.data({key: None, "held_by": held.agent})
    ctx.out.line(f"{task_id} is leased by {held.agent}, not {agent} — not recorded (--force overrides)")
    return True


def done(ctx: Context) -> int:
    """Record a typed hand-back. `completed` is a done; anything else is a block."""
    path, feature, parsed, store, graph = _setup(ctx)
    task = _task(parsed, ctx.args.task)
    agent = ctx.args.agent or swarm.whoami()
    status = ctx.args.status or "completed"
    if status != "completed" and not ctx.args.reason:
        ctx.out.error(f"a `{status}` hand-back needs --reason: one line saying what is missing")
        return 2
    held = store.all()["leased"].get(task.id)
    # A worker that outlived its lease must not overwrite the new holder's work.
    if _fenced(ctx, held, agent, task.id, "done"):
        return 1
    now = int(time.time())
    if status != "completed":
        store.put("blocked", swarm.Lease(task.id, agent, now, now, task.paths, ctx.args.reason, status))
        ctx.out.data({"done": None, "blocked": task.id, "status": status, "reason": ctx.args.reason})
        ctx.out.line(f"{task.id} {status}: {ctx.args.reason} — recorded as a block, not a done")
        return 0
    store.put("done", swarm.Lease(task.id, agent, now, now, task.paths, status="completed"))
    wrote = swarm.mark_done_in_file(path, task, date.today().isoformat())
    ctx.out.data({"done": task.id, "status": "completed", "status_written": wrote})
    ctx.out.line(f"{task.id} done" + (" — Status line written to tasks.md" if wrote else ""))
    return 0


def release(ctx: Context) -> int:
    """Give a lease back. Another agent's live lease needs --force."""
    path, feature, parsed, store, graph = _setup(ctx)
    agent = ctx.args.agent or swarm.whoami()
    held = store.all()["leased"].get(ctx.args.task)
    if held is None:
        ctx.out.data({"released": None})
        ctx.out.line(f"{ctx.args.task} held no lease")
        return 1
    if _fenced(ctx, held, agent, ctx.args.task, "released"):
        return 1
    # Drop only while the holder we just checked still holds it.
    ok = store.drop("leased", ctx.args.task, owner=None if ctx.args.force else held.agent)
    ctx.out.data({"released": ctx.args.task if ok else None, "held_by": held.agent})
    ctx.out.line(f"{ctx.args.task} released" if ok else f"{ctx.args.task} changed hands meanwhile — not released")
    return 0 if ok else 1


def renew(ctx: Context) -> int:
    """Extend a lease you hold; refused once someone else holds it."""
    path, feature, parsed, store, graph = _setup(ctx)
    agent = ctx.args.agent or swarm.whoami()
    expires = int(time.time()) + 60 * ctx.args.ttl
    if not store.renew(ctx.args.task, agent, expires):
        ctx.out.data({"renewed": None})
        ctx.out.line(f"{ctx.args.task} is not leased by {agent}")
        return 1
    ctx.out.data({"renewed": ctx.args.task, "expires": expires})
    ctx.out.line(f"{ctx.args.task} renewed for {ctx.args.ttl} min")
    return 0


def block(ctx: Context) -> int:
    path, feature, parsed, store, graph = _setup(ctx)
    task = _task(parsed, ctx.args.task)
    if not ctx.args.reason:
        ctx.out.error("a block needs --reason: one line saying what is missing")
        return 2
    agent = ctx.args.agent or swarm.whoami()
    if _fenced(ctx, store.all()["leased"].get(task.id), agent, task.id, "blocked"):
        return 1
    now = int(time.time())
    store.put("blocked", swarm.Lease(task.id, agent, now, now, task.paths, ctx.args.reason))
    ctx.out.data({"blocked": task.id, "reason": ctx.args.reason})
    ctx.out.line(f"{task.id} blocked: {ctx.args.reason} — a /tasks amendment, not a crisis")
    return 0


def status(ctx: Context) -> int:
    """One line per agent: what it holds, for how long, and when that runs out."""
    path, feature, parsed, store, graph = _setup(ctx)
    leases = store.all()
    done_ids = {t.id for t in parsed.tasks if t.status == "done"} | set(leases["done"])
    now = time.time()
    soon = 60 * ctx.args.soon
    agents = []
    for h in swarm.holders(leases, done_ids):
        left = h.left(now)
        flag = "lapsed" if left <= 0 else "expiring" if left <= soon else "ok"
        agents.append({"agent": h.agent, "tasks": h.tasks, "since": h.since, "expires": h.expires,
                       "left": left, "flag": flag})
    blocked = [
        {"task": t, "status": b.status or "blocked", "reason": b.reason, "agent": b.agent}
        for t, b in sorted(leases["blocked"].items()) if t not in done_ids
    ]
    total = len(parsed.tasks)
    n_done = sum(t.id in done_ids for t in parsed.tasks)
    ctx.out.data({"feature": feature, "agents": agents, "blocked": blocked, "done": n_done, "total": total})

    expiring = sum(a["flag"] == "expiring" for a in agents)
    lapsed = sum(a["flag"] == "lapsed" for a in agents)
    ctx.out.line(
        f"{feature}: {len(agents)} agent{'s' * (len(agents) != 1)} · {sum(len(a['tasks']) for a in agents)} leased"
        f" ({expiring} expiring, {lapsed} lapsed) · {len(blocked)} blocked · {n_done}/{total} done"
    )
    width = max([len(a["agent"]) for a in agents] + [5])
    for a in agents:
        when = (f"lapsed {swarm.ago(-a['left'])} ago — reclaimable" if a["flag"] == "lapsed"
                else f"expires in {swarm.ago(a['left'])}" + ("  ← expiring" if a["flag"] == "expiring" else ""))
        ctx.out.line(f"{a['agent']:<{width}}  {','.join(a['tasks'])}  since {swarm.ago(now - a['since'])}  {when}")
    for b in blocked:
        ctx.out.line(f"{'—':<{width}}  {b['task']}  {b['status']}: {b['reason']}  ({b['agent']})")
    return 0


def merge(ctx: Context) -> int:
    """Done tasks' `swarm/<id>` branches in a safe order; `--apply` lands them."""
    path, feature, parsed, store, graph = _setup(ctx)
    root = ctx.layout.root
    if swarm._git(root, "rev-parse", "--git-dir").returncode != 0:
        raise EdifyError("not a git repository", hint="merge order needs the swarm/<id> branches")
    blast = swarm.BlastRadius(graph)
    rows = swarm.board(parsed, store.all(), graph, blast)
    index = {t.id: i for i, t in enumerate(parsed.tasks)}
    items, missing, changed = [], [], {}
    for row in rows:
        if row.state != "done":
            continue
        branch = f"swarm/{row.task.id}"
        if not swarm.branch_exists(root, branch):
            missing.append(row.task.id)
            continue
        changed[row.task.id] = swarm.changed_files(root, branch)
        items.append((row.task, row.task.paths + changed[row.task.id]))
    steps = swarm.merge_order(items, blast, index)
    for s in steps:
        declared = {swarm._norm(p) for p in s.task.paths}
        s.undeclared = sorted(f for f in changed[s.task.id] if swarm._norm(f) not in declared)
        s.merged = swarm.is_merged(root, s.branch)

    plan = [{"task": s.task.id, "branch": s.branch, "phase": s.task.phase, "wave": s.wave, "after": s.after,
             "merged": s.merged, "undeclared": s.undeclared} for s in steps]
    result: dict = {"feature": feature, "order": plan, "missing": missing, "merged": [], "conflict": None}
    pending = [s for s in steps if not s.merged]
    ctx.out.line(f"{feature}: {len(steps)} done branch{'es' * (len(steps) != 1)} · {len(pending)} to merge"
                 + (f" · {len(missing)} done without a branch" if missing else ""))
    ctx.out.table(
        ["#", "wave", "branch", "after", "state"],
        [[str(i), str(s.wave), s.branch, ", ".join(s.after) or "—", "merged" if s.merged else "to merge"]
         for i, s in enumerate(steps, 1)],
    )
    for s in steps:
        if s.undeclared:
            ctx.out.warn(f"{s.branch} changed files outside its task: {', '.join(s.undeclared[:5])}")
    if missing:
        ctx.out.note("no branch for: " + ", ".join(missing))

    if not ctx.args.apply:
        ctx.out.data(result)
        if pending:
            ctx.out.note("same wave = no shared blast radius; `--apply` merges in this order")
        return 0

    for s in pending:
        ok, files, message = swarm.merge_one(root, s)
        if not ok:
            result["conflict"] = {"task": s.task.id, "branch": s.branch, "files": files, "message": message[:400]}
            ctx.out.data(result)
            what = ", ".join(files) if files else message.splitlines()[0] if message else "git merge failed"
            ctx.out.error(f"{s.task.id} ({s.branch}) did not merge: {what}",
                          hint="merge aborted; earlier merges kept. A conflict is a missing `Depends on` — amend tasks.md")
            return 1
        result["merged"].append(s.task.id)
        ctx.out.line(f"merged {s.branch}")
    ctx.out.data(result)
    if pending:
        ctx.out.line("next: the phase exit check, then `edify graph update --changed`")
    return 0


# ---------------------------------------------------------------------------


def _task(parsed, task_id):
    task = parsed.by_id(task_id)
    if task is None:
        raise EdifyError(f"no task {task_id}", hint="`edify swarm board` lists them")
    return task


def _skill_path(ctx: Context, task, phase: str) -> str:
    try:
        entries = skills.load_index(ctx.layout)
    except EdifyError:
        return ""
    for e in entries:
        if task.skill and e.name == task.skill:
            return e.path
    try:
        return skills.resolve(ctx.layout, task.role or "implementer", phase).path
    except EdifyError:
        return ""


def _section(path, title: str) -> str:
    from ..formats.document import parse_document

    sec = parse_document(path).section(title)
    if sec is None:
        return ""
    text = sec.text.strip()
    rows = [line for line in text.splitlines() if line.startswith("| D-")]
    return text if rows else ""


def _worktree(ctx: Context, task_id: str) -> str:
    root = ctx.layout.root
    target = root.parent / f"{root.name}-{task_id.lower()}"
    out = subprocess.run(
        ["git", "worktree", "add", "-q", "-B", f"swarm/{task_id}", str(target)],
        cwd=str(root), capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        ctx.out.warn(f"worktree not created: {out.stderr.strip()[:160]}")
        return ""
    return str(target)
