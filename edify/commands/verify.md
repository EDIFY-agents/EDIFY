---
name: verify
description: The code becomes evidence — on every surface it will really run on.
model: strong, and never a session that wrote the code
ends-at: a report anyone can read
---

# /verify

Run things; decide nothing; never edit code. **In:** the repo, spec, tasks, plan.
**Out:** `specs/<feature>/verification.md`. Method: skill `verifier`.

## Passes
1. **Re-run** suite, types, lint exactly as the spec's constraints say. Raw output with
   real exit codes (`set -o pipefail`; a piped status is not evidence).
2. **Order**: from `git log`, each assertion's test landed before its code.
3. **Exercise for real**: replay `quickstart.md` step by step if there is one, then every
   tier the spec's assertions declare:

| tier | how | evidence |
|---|---|---|
| service | start it; real requests (`curl`, client) | request/response transcript |
| browser | Playwright headless; drive the user path | screenshots + console log |
| device | emulator/simulator (`emulator -avd`, `xcrun simctl`, `adb`) or a real device on an attached machine | logs, screenshots, exit codes |
| live API | sandbox keys from env/secret store, never pasted; record endpoint and version | redacted responses |
| connector | the MCP server or connector the feature integrates with, via `edify mcp config verifier 7` | tool call + result |
| data | fixtures or a disposable DB; migrations up and down | row counts, diffs |

   A tier that cannot run here (no device, key, network) is **blocked: needs X** —
   never skipped silently, never faked with a mock.
4. **Coverage**: every row satisfied (evidence) · waived (reason) · blocked (what). A
   declared kind silently downgraded (property → example) fails.
5. **Plan gates**, if there is a plan.
6. **One design**: duplicated helpers, two error styles, vocabulary drift — name them.
   `edify graph dependents` shows what a change reached.

## Report
```
## Ran        command · exact invocation · raw output
## Ordering   assertion → test commit → code commit
## Tiers      tier · how · evidence | blocked: needs X
## Coverage   row · satisfied | waived | blocked
## One design what was checked, what was found
```
**Corrections become checks**: each defect a human had to point out is proposed as a
lint rule or test, never as more prose in CLAUDE.md.
In CI, passes 1 and 4 are the mechanical half; a non-zero exit is the team's block.
