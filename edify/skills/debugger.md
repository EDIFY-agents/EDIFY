---
name: debugger
description: Diagnoses a failure from evidence — reproduce first, then isolate, then the smallest fix.
kind: skill
role: debugger
phase: 0 1 2 3 4 5 6 7
tech: any
provenance: adapted
license: MIT github.com/SWE-agent/SWE-agent@3ea751c087f32b16e039a2233dd6eefecef325d5
source: harvest reproduction-first, network-diagnosis (CC0 awesome-cursorrules)
---

# Debugger

You arrive after a done-check failed twice, or with a defect report. Evidence first;
a fix applied before the failure is captured destroys the only proof either way.

## Reproduce
1. One line: expected X, got Y. Can't write both halves → you don't have the defect yet.
2. Locate before scripting: `edify graph where` the named symbol, `edify graph path` /
   `dependents` for what reaches it. Reports are often wrong about which layer failed.
3. Reproduce at this commit with a script that prints an explicit success line. Reuse an
   existing fixture before building one.

## Isolate
4. Read the accumulated evidence (attempts, outputs). Form one hypothesis, design the
   cheapest observation that would refute it, run it. Repeat; never two changes at once.
5. **Is it the network?** The error string names the layer: DNS (`ENOTFOUND`, `NXDOMAIN`),
   connect (`ECONNREFUSED`, timeout), TLS (`certificate`, `SSL`), proxy (`407`, `403` from
   a proxy), registry (`404` on a package). Probe that target only; read-only; offer
   remediations as options — never change the machine's config yourself.

## Fix
6. Smallest change that makes the unchanged repro pass. Then widen once: adjacent inputs.
7. Run the task's done-check.

## Stuck
Won't reproduce → say what you tried: fixed, environmental, or misreported are all
findings. Root cause outside the task's files → `edify swarm done <id> --status failed
--reason "<cause>"`.

## Hand back
Status `completed | partial | failed | needs_input` · symptom · repro command with its
before/after output · root cause `file:line` · the fix · done-check output.
