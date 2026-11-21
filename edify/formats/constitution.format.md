# The constitution: `.edify/constitution.md`

The few non-negotiable principles of this repository, written by its people once and
changed rarely. `.edify/conventions.md` is scraped from config (what the tools enforce);
this is what the tools cannot see. `/plan` checks every feature against it before research
and again after design (`## Constitution check`); `/verify` reports a violation as a finding.

```markdown
# <project> constitution — v<MAJOR.MINOR> · ratified <date> · amended <date>

## Principles
### I. <name>                       ← 3–7 principles; each one is testable
<one or two sentences: the rule, then why>
Gate: <what /plan checks — a yes/no question>

### II. Tests before code (non-negotiable)
Phase 2 is red before phase 3 starts; a test written after its code is reported.
Gate: does every assertion have a phase-2 task?

## Constraints                       ← stack, security, compliance, performance floors
## Amending                         ← who approves; MAJOR = a principle removed or redefined
```

A principle that no gate can check is advice: cut it or give it a gate. A plan that
violates a gate justifies it in one row — `| violation | why needed | simpler alternative
rejected because |` — or does not pass.
