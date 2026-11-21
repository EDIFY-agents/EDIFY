"""Leases: many agents and many people on one task list, without collisions.

A lease is a small file naming a task, who holds it, and when it expires. Two
stores keep them, with one contract:

- `put("leased")` succeeds for exactly one claimant;
- `put("done"|"blocked")` moves the task out of every other state in one step;
- `renew` and `drop(owner=…)` act only while `owner` still holds the lease.

`LocalStore` lives in the git common directory, shared by every worktree on one
machine; exclusive create (`O_EXCL`) is the lock. `GitStore` lives on a branch of
the remote (`edify-swarm`), shared by everyone who can push; a non-forced push is
the lock, so of two racing writes one is rejected and retried on a fresh read.

What may run is decided here, mechanically: a task is ready when its dependencies
are done, every earlier phase is done, nobody holds it, and its blast radius (files
plus their dependents, from the graph) touches no live lease. The same radius
orders the merge of finished `swarm/<id>` branches.
"""

from __future__ import annotations

import getpass
import os
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from .errors import EdifyError
from .formats import tasks as tasks_format
from .graph.store import GraphStore

STATES = ("leased", "done", "blocked")
#: What a worker hands back. Anything but `completed` is recorded as a block.
HANDBACKS = ("completed", "partial", "failed", "needs_input")
#: The phase a task with none is treated as — the same default `swarm prompt` uses.
DEFAULT_PHASE = 3


@dataclass
class Lease:
    task: str
    agent: str
    since: int
    expires: int
    files: list[str] = field(default_factory=list)
    reason: str = ""
    status: str = ""

    @property
    def live(self) -> bool:
        return self.expires > time.time()

    def dump(self) -> str:
        reason = " ".join(self.reason.split())  # one line, or the format breaks
        return (
            f"task={self.task}\nagent={self.agent}\nsince={self.since}\nexpires={self.expires}\n"
            f"files={' '.join(self.files)}\nreason={reason}\nstatus={self.status}\n"
        )

    @staticmethod
    def load(text: str) -> "Lease":
        kv = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
        return Lease(
            kv.get("task", ""),
            kv.get("agent", ""),
            int(kv.get("since", "0") or 0),
            int(kv.get("expires", "0") or 0),
            kv.get("files", "").split(),
            kv.get("reason", ""),
            kv.get("status", ""),
        )


def whoami() -> str:
    return os.environ.get("EDIFY_AGENT") or f"{getpass.getuser()}@{socket.gethostname()}"


def _git(root: Path, *args: str, input: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, input=input,
        env={**os.environ, **(env or {})}, check=False,
    )


def _empty() -> dict[str, dict[str, Lease]]:
    return {s: {} for s in STATES}


# ---------------------------------------------------------------------------
# stores
# ---------------------------------------------------------------------------


class LocalStore:
    """`<git-common-dir>/edify-swarm/<feature>/<state>/<task>`."""

    def __init__(self, root: Path, feature: str):
        override = os.environ.get("EDIFY_SWARM_DIR")
        if override:
            base = Path(override)
        else:
            out = _git(root, "rev-parse", "--git-common-dir")
            common = (root / out.stdout.strip()).resolve() if out.returncode == 0 else root / ".edify" / "run"
            base = common / "edify-swarm"
        self.base = base / feature

    def all(self) -> dict[str, dict[str, Lease]]:
        out = _empty()
        for state in STATES:
            d = self.base / state
            if d.is_dir():
                for p in sorted(d.iterdir()):
                    if not p.name.startswith("."):
                        out[state][p.name] = Lease.load(p.read_text(encoding="utf-8"))
        return out

    def _read(self, state: str, task: str) -> Lease | None:
        try:
            return Lease.load((self.base / state / task).read_text(encoding="utf-8"))
        except OSError:
            return None

    def _write(self, state: str, lease: Lease) -> None:
        """Write, then rename into place: a reader never sees a half-written file,
        which would parse as `expires=0` and look free to steal."""
        d = self.base / state
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f".tmp-{lease.task}-{os.getpid()}-{time.time_ns()}"
        tmp.write_text(lease.dump(), encoding="utf-8")
        os.replace(tmp, d / lease.task)

    def put(self, state: str, lease: Lease, replace_expired: bool = True) -> bool:
        if state != "leased":
            self._write(state, lease)
            for other in STATES:
                if other != state:
                    self.drop(other, lease.task)
            return True
        d = self.base / state
        d.mkdir(parents=True, exist_ok=True)
        target = d / lease.task
        if target.exists() and replace_expired:
            held = self._read(state, lease.task)
            if held is not None and not held.live:
                # Of two agents stealing one expired lease, only one rename succeeds.
                try:
                    os.rename(target, d / f".stale-{lease.task}-{os.getpid()}-{time.time_ns()}")
                except OSError:
                    return False
        try:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(lease.dump())
        return True

    def drop(self, state: str, task: str, owner: str | None = None) -> bool:
        if owner is not None:
            held = self._read(state, task)
            if held is None or held.agent != owner:
                return False
        try:
            (self.base / state / task).unlink()
            return True
        except FileNotFoundError:
            return False

    def renew(self, task: str, owner: str, expires: int) -> bool:
        held = self._read("leased", task)
        if held is None or held.agent != owner:
            return False
        if not held.live:
            # Expired: retake it through the claim path, which races fairly.
            return self.put("leased", replace(held, expires=expires))
        self._write("leased", replace(held, expires=expires))
        return True


class GitStore:
    """Leases as files on `origin/edify-swarm`, written with plumbing — no checkout.

    Every write is decided against the tree it is committed on, and the push is
    non-forced, so a decision made on a stale read loses the push and is retried
    after a fresh fetch. That makes reusing one read safe: an uncontended command
    costs one fetch and one push.
    """

    BRANCH = "edify-swarm"
    TRIES = 4

    def __init__(self, root: Path, feature: str, remote: str = "origin"):
        self.root, self.feature, self.remote = root, feature, remote
        self.ref = f"refs/remotes/{remote}/{self.BRANCH}"
        self._head: str | None = None
        self._fetched = False
        self._cache: dict[str | None, dict[str, dict[str, Lease]]] = {}

    def _fetch(self) -> str | None:
        _git(self.root, "fetch", "-q", self.remote, f"+refs/heads/{self.BRANCH}:{self.ref}")
        out = _git(self.root, "rev-parse", "-q", "--verify", self.ref)
        self._head = out.stdout.strip() if out.returncode == 0 else None
        self._fetched = True
        return self._head

    def _current(self, fresh: bool = False) -> tuple[str | None, dict[str, dict[str, Lease]]]:
        head = self._fetch() if fresh or not self._fetched else self._head
        return head, self._read(head)

    def _read(self, head: str | None) -> dict[str, dict[str, Lease]]:
        """Every lease at `head`, in two git calls: `ls-tree` and one `cat-file --batch`."""
        if head in self._cache:
            return self._cache[head]
        out = _empty()
        if head:
            wanted: list[tuple[str, str, str]] = []
            for row in _git(self.root, "ls-tree", "-r", head, f"{self.feature}/").stdout.splitlines():
                meta, _, path = row.partition("\t")
                parts = path.split("/")
                if len(parts) == 3 and parts[1] in STATES and len(meta.split()) == 3:
                    wanted.append((meta.split()[2], parts[1], parts[2]))
            blobs = _cat_batch(self.root, [sha for sha, _, _ in wanted]) if wanted else {}
            for sha, state, task in wanted:
                out[state][task] = Lease.load(blobs.get(sha, ""))
        self._cache[head] = out
        return out

    def all(self) -> dict[str, dict[str, Lease]]:
        return self._current()[1]

    def _commit(self, head: str | None, edits: dict[str, str | None], message: str) -> bool:
        """Apply path → content (None deletes) on top of `head` and push. One try."""
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
            if head:
                _git(self.root, "read-tree", head, env=env)
            for path, content in edits.items():
                if content is None:
                    _git(self.root, "update-index", "--force-remove", path, env=env)
                    continue
                blob = _git(self.root, "hash-object", "-w", "--stdin", input=content).stdout.strip()
                _git(self.root, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=env)
            tree = _git(self.root, "write-tree", env=env).stdout.strip()
        args = ["commit-tree", tree, "-m", message] + (["-p", head] if head else [])
        commit = _git(self.root, *args, env={
            "GIT_AUTHOR_NAME": "edify-swarm", "GIT_AUTHOR_EMAIL": "swarm@edify.invalid",
            "GIT_COMMITTER_NAME": "edify-swarm", "GIT_COMMITTER_EMAIL": "swarm@edify.invalid",
        }).stdout.strip()
        if not commit:
            raise EdifyError("could not write a lease commit", hint="is this a git repository with a remote?")
        if _git(self.root, "push", "-q", self.remote, f"{commit}:refs/heads/{self.BRANCH}").returncode != 0:
            return False
        # What we pushed is the remote's state now; the next read needs no fetch.
        _git(self.root, "update-ref", self.ref, commit)
        self._head = commit
        return True

    def _path(self, state: str, task: str) -> str:
        return f"{self.feature}/{state}/{task}"

    def _cas(self, decide, message: str) -> bool:
        """Read, decide the edits (None refuses), commit, push; refetch only after a lost race."""
        for attempt in range(self.TRIES):
            head, current = self._current(fresh=attempt > 0)
            edits = decide(current)
            if edits is None:
                return False
            if self._commit(head, edits, message):
                return True
        return False

    def put(self, state: str, lease: Lease, replace_expired: bool = True) -> bool:
        def decide(current):
            held = current["leased"].get(lease.task)
            if state == "leased" and held is not None and (held.live or not replace_expired):
                return None
            edits: dict[str, str | None] = {self._path(state, lease.task): lease.dump()}
            if state != "leased":
                for other in STATES:
                    if other != state and lease.task in current[other]:
                        edits[self._path(other, lease.task)] = None
            return edits

        return self._cas(decide, f"swarm: {state} {lease.task} by {lease.agent}")

    def drop(self, state: str, task: str, owner: str | None = None) -> bool:
        def decide(current):
            held = current[state].get(task)
            if held is None or (owner is not None and held.agent != owner):
                return None
            return {self._path(state, task): None}

        return self._cas(decide, f"swarm: drop {state} {task}")

    def renew(self, task: str, owner: str, expires: int) -> bool:
        def decide(current):
            held = current["leased"].get(task)
            if held is None or held.agent != owner:
                return None
            return {self._path("leased", task): replace(held, expires=expires).dump()}

        return self._cas(decide, f"swarm: renew {task} by {owner}")


def _cat_batch(root: Path, shas: list[str]) -> dict[str, str]:
    """Blob contents for many object ids in one `git cat-file --batch`."""
    raw = subprocess.run(
        ["git", "cat-file", "--batch"], cwd=str(root), input=("\n".join(shas) + "\n").encode(),
        capture_output=True, check=False,
    ).stdout
    blobs: dict[str, str] = {}
    i = 0
    while i < len(raw):
        nl = raw.find(b"\n", i)
        if nl < 0:
            break
        header = raw[i:nl].decode().split()
        i = nl + 1
        if len(header) < 3 or header[1] == "missing":
            continue
        size = int(header[2])
        blobs[header[0]] = raw[i : i + size].decode("utf-8", "replace")
        i += size + 1
    return blobs


def store_for(root: Path, feature: str, use_git: bool):
    return GitStore(root, feature) if use_git else LocalStore(root, feature)


# ---------------------------------------------------------------------------
# blast radius
# ---------------------------------------------------------------------------


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


class BlastRadius:
    """A file set plus the files that depend on it, one hop out.

    Equal to `queries.dependent_files(files, depth=1)`, but the incoming-edge map is
    built once per instance rather than rescanned for every task × lease.
    """

    def __init__(self, graph: GraphStore | None):
        self.incoming: dict[str, set[str]] | None = None
        if graph is not None and graph.exists():
            incoming: dict[str, set[str]] = {}
            by_id = graph.by_id
            for edge in graph.edges:
                if edge.relation not in ("references", "imports", "exposes"):
                    continue
                src, dst = by_id.get(edge.src), by_id.get(edge.dst)
                if src is None or dst is None or src.file == dst.file:
                    continue
                incoming.setdefault(dst.file, set()).add(src.file)
            self.incoming = incoming

    def of(self, files: list[str]) -> set[str]:
        out = {_norm(f) for f in files if f}
        if self.incoming:
            for f in list(out):
                out |= self.incoming.get(f, set())
        return out


def radius(store: GraphStore | None, files: list[str]) -> set[str]:
    """One-off blast radius; build a `BlastRadius` when asking more than once."""
    return BlastRadius(store).of(files)


# ---------------------------------------------------------------------------
# the board
# ---------------------------------------------------------------------------


@dataclass
class Row:
    task: tasks_format.Task
    state: str  # done | blocked | leased | ready | waiting
    lease: Lease | None = None
    why: str = ""

    @property
    def status(self) -> str:
        """The hand-back status, where one was recorded."""
        if self.lease is not None and self.lease.status:
            return self.lease.status
        return "completed" if self.state == "done" else ""


def find_feature(root: Path, feature: str | None) -> Path:
    specs = root / "specs"
    if feature:
        path = specs / feature / "tasks.md"
        if not path.is_file():
            raise EdifyError(f"no {path.relative_to(root)}", hint="run /tasks for this feature first")
        return path
    found = sorted(specs.glob("*/tasks.md")) if specs.is_dir() else []
    if len(found) == 1:
        return found[0]
    if not found:
        raise EdifyError("no specs/<feature>/tasks.md in this repository", hint="run /tasks first")
    names = ", ".join(p.parent.name for p in found)
    raise EdifyError(f"several features have tasks: {names}", hint="name one: edify swarm board <feature>")


def board(
    parsed: tasks_format.Tasks,
    leases: dict[str, dict[str, Lease]],
    graph: GraphStore | None,
    blast: BlastRadius | None = None,
) -> list[Row]:
    blast = blast or BlastRadius(graph)
    done = {t.id for t in parsed.tasks if t.status == "done"} | set(leases["done"])
    live = {k: v for k, v in leases["leased"].items() if v.live and k not in done}
    held: set[str] = set()
    for lease in live.values():
        held |= blast.of(lease.files)

    phases = sorted({t.phase for t in parsed.tasks if t.phase is not None})
    open_below = {
        p: [t.id for t in parsed.tasks if t.phase is not None and t.phase < p and t.id not in done] for p in phases
    }
    rows: list[Row] = []
    for t in parsed.tasks:
        if t.id in done:
            rows.append(Row(t, "done", leases["done"].get(t.id)))
        elif t.id in leases["blocked"]:
            rows.append(Row(t, "blocked", leases["blocked"][t.id], leases["blocked"][t.id].reason))
        elif t.id in live:
            rows.append(Row(t, "leased", live[t.id]))
        else:
            missing = [d for d in t.depends_on if d not in done]
            earlier = open_below.get(t.phase, []) if t.phase is not None else []
            if missing:
                rows.append(Row(t, "waiting", why="needs " + ", ".join(missing)))
            elif earlier:
                rows.append(Row(t, "waiting", why=f"phase {t.phase} waits on {', '.join(earlier[:4])}"))
            elif held and (clash := blast.of(t.paths) & held):
                rows.append(Row(t, "waiting", why="overlaps a live lease: " + ", ".join(sorted(clash)[:3])))
            else:
                rows.append(Row(t, "ready"))
    return rows


# ---------------------------------------------------------------------------
# the orchestrator's view
# ---------------------------------------------------------------------------


@dataclass
class Holder:
    """One agent's live or lapsed leases, for `edify swarm status`."""

    agent: str
    tasks: list[str]
    since: int
    expires: int  # the soonest expiry among its leases

    def left(self, now: float) -> int:
        return int(self.expires - now)


def holders(leases: dict[str, dict[str, Lease]], done: set[str] = frozenset()) -> list[Holder]:
    """Who holds what, soonest expiry first. Lapsed leases stay listed until reclaimed."""
    by_agent: dict[str, Holder] = {}
    for lease in leases["leased"].values():
        if lease.task in done:
            continue
        h = by_agent.get(lease.agent)
        if h is None:
            by_agent[lease.agent] = Holder(lease.agent, [lease.task], lease.since, lease.expires)
        else:
            h.tasks.append(lease.task)
            h.since, h.expires = min(h.since, lease.since), min(h.expires, lease.expires)
    return sorted(by_agent.values(), key=lambda h: (h.expires, h.agent))


def ago(seconds: float) -> str:
    """`42s`, `17m`, `3h05m` — compact, for one-line views."""
    s = int(abs(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


# ---------------------------------------------------------------------------
# merge order
# ---------------------------------------------------------------------------


@dataclass
class MergeStep:
    task: tasks_format.Task
    branch: str
    wave: int
    after: list[str]  # earlier steps whose blast radius overlaps this one
    files: list[str]  # declared plus actually changed
    undeclared: list[str] = field(default_factory=list)
    merged: bool = False


def merge_order(
    items: list[tuple[tasks_format.Task, list[str]]], blast: BlastRadius, index: dict[str, int]
) -> list[MergeStep]:
    """Phase, then task order; overlap within a phase pushes a step to a later wave.

    Steps in one wave share no blast radius, so they may land in any order (or as
    one batch); a pair that overlaps lands in task order. Every phase starts a new
    wave after all earlier phases.
    """
    items = sorted(items, key=lambda it: (_phase(it[0]), index.get(it[0].id, 0)))
    steps: list[tuple[MergeStep, set[str]]] = []
    floor, top, current = 0, -1, None
    for task, files in items:
        phase = _phase(task)
        if phase != current:
            floor, current = top + 1, phase
        r = blast.of(files)
        clash = [s for s, sr in steps if _phase(s.task) == phase and sr & r]
        wave = max([floor] + [s.wave + 1 for s in clash])
        top = max(top, wave)
        steps.append((MergeStep(task, f"swarm/{task.id}", wave, [s.task.id for s in clash], sorted(set(files))), r))
    return sorted((s for s, _ in steps), key=lambda s: (s.wave, index.get(s.task.id, 0)))


def _phase(task: tasks_format.Task) -> int:
    return task.phase if task.phase is not None else DEFAULT_PHASE


def branch_exists(root: Path, branch: str) -> bool:
    return _git(root, "rev-parse", "-q", "--verify", f"refs/heads/{branch}").returncode == 0


def changed_files(root: Path, branch: str, base: str = "HEAD") -> list[str]:
    """Files `branch` changed since it left `base`."""
    out = _git(root, "diff", "--name-only", f"{base}...{branch}")
    return out.stdout.split() if out.returncode == 0 else []


def is_merged(root: Path, branch: str, base: str = "HEAD") -> bool:
    return _git(root, "merge-base", "--is-ancestor", branch, base).returncode == 0


def merge_one(root: Path, step: MergeStep) -> tuple[bool, list[str], str]:
    """`git merge --no-ff` one branch. On failure the merge is aborted, leaving the
    tree as it was; returns (ok, conflicted files, git's message)."""
    msg = f"swarm: merge {step.task.id} · {step.task.title}"
    out = _git(root, "merge", "--no-ff", "--no-edit", "-m", msg, step.branch)
    if out.returncode == 0:
        return True, [], ""
    conflicted = _git(root, "diff", "--name-only", "--diff-filter=U").stdout.split()
    if _git(root, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0:
        _git(root, "merge", "--abort")
    return False, conflicted, (out.stderr or out.stdout).strip()


# ---------------------------------------------------------------------------
# tasks.md
# ---------------------------------------------------------------------------


def block_text(path: Path, task: tasks_format.Task) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[task.line - 1 : task.end_line]).rstrip()


def mark_done_in_file(path: Path, task: tasks_format.Task, today: str) -> bool:
    """Write `Status — **done** <date>` under the task heading, once."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    block = lines[task.line - 1 : task.end_line]
    if any(tasks_format._STATUS.match(line) for line in block):
        return False
    lines.insert(task.line, f"Status — **done** {today}\n")
    path.write_text("".join(lines), encoding="utf-8")
    return True
