# EDIFY manifest

What this install is, and what it pins. Read by `edify doctor` and `edify upgrade`.

- edify: 0.3.2
- library: 0.1.0
- graph-schema: 1
- index-schema: 1
- extractor: builtin
- extractor-alternative: universal-ctags
- extractor-min-version: 6.0.0

## The extractor

Built-in: Python is parsed with the standard library's syntax tree; every other covered
language is scanned with a line-pattern table. `meta.method_<language>` in
`.edify/graph/meta` records which, so a scan is never mistaken for a parse. For
parse-grade precision elsewhere, install Universal Ctags and run
`edify graph build --extractor ctags`; EDIFY owns the TSV contract, and
`src/edify/graph/langs/ctags.py` is the only file a replacement extractor changes.

## What no model touches

The graph, at any stage — an uncovered language has no nodes, and
`meta.languages_uncovered` says which. Skill resolution and server scoping are
exact-match lookups over sorted tables.
