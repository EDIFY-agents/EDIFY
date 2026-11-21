---
name: implementer-react
description: Implements a build task in a React or Next.js front end.
kind: skill
role: implementer
phase: 0 3 4 5 6
tech: react nextjs vue svelte
provenance: original
license: -
---

# Implementer — front end

Build steps, submit gate and hand-back are `.edify/skills/implementer-general.md`; read
it first. Usually a surface task — screen, component, route — against a contract frozen
in phase 1.

## Method
1. Copy the pattern page's state machine exactly — typically loading → error → ready →
   submitted, in that order. That consistency outranks any styling choice.
2. Use the generated or shared API client; no hand-written `fetch` beside it. Import
   request/response types from the frozen contract.
3. One message per error code the spec names, never one generic failure.
4. Register routes the way neighbours do — same array or block, same public vs
   authenticated split.
5. Test with the neighbouring request-mocking setup, one handler per state; then the
   type check.

## Traps
- No loading state: an empty screen that looks like a bug to users and success to tests.
- Array-index `key` on a list reorders wrongly when the list changes; use the data's id.
- An effect that fetches without cleanup/abort races itself on fast navigation.
- Next.js: a server component cannot use hooks or browser APIs; `"use client"` marks the
  boundary, and anything passed across it must be serializable.
- An unauthenticated page renders only what the contract returns; test the exact key set.
- No restyling of untouched components, no state library the plan did not decide on.
