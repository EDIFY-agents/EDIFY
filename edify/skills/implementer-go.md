---
name: implementer-go
description: Implements a build task in a Go service codebase.
kind: skill
role: implementer
phase: 0 1 3 4 5 6
tech: go gin echo
provenance: original
license: -
---

# Implementer — Go

Build steps, submit gate and hand-back are `.edify/skills/implementer-general.md`; read
it first. This adds what Go gets wrong.

## Method
1. From the pattern pointer copy: handler wiring, error wrapping, interfaces declared
   beside their consumer, table-test layout.
2. Read the `go` directive in `go.mod` before relying on version-dependent behaviour.
3. Export only what the task needs; a capitalised identifier is API.
4. Wrap errors with `%w` and context, phrased as the surrounding code phrases them. No
   second error package.
5. Table tests where the neighbours use them. `go test ./... -race` when CI runs it;
   then `go vet` and the repository's linter.

## Traps
- Before Go 1.22 a loop variable captured by a goroutine is one variable for every
  iteration.
- A request path takes the `context.Context` it was given — never
  `context.Background()` — or a cancelled request keeps working.
- `defer Close()` inside a loop runs when the function returns, not per iteration.
- A nil map reads fine and panics on write.
- An interface holding a typed nil pointer is not nil — the error that "is nil" but isn't.
- No package restructuring and no new module the plan did not decide on.
