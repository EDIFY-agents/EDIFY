# Project Governance

Who decides what, and how that changes.

## Today: single-vendor, open contribution

EDIFY is built and maintained by EDIFY. Direction, the roadmap, the document
formats, and what the paid tier gates are decided by the maintainers. Anyone may
open issues, discussions, and pull requests, and they are reviewed on merit.

We state this plainly rather than describing a committee that does not exist. A
project with one maintainer and a governance document describing a technical
steering committee is telling you something false on its first page.

## What is open to contribution and what is not

| area | who decides |
|---|---|
| bug fixes, tests, docs, platform support | contributors — send the PR |
| new languages in the graph extractor | contributors, against the extractor contract |
| skill library entries | maintainers, after curation |
| the three document formats | maintainers — these are contracts; changing one invalidates every existing spec |
| the five commands and their boundaries | maintainers |
| editions, licensing | maintainers |
| the name and marks | maintainers ([TRADEMARK.md](TRADEMARK.md)) |

## How decisions get made in public

Anything that changes behaviour a user depends on goes through a
[discussion](https://github.com/EDIFY-agents/EDIFY/discussions) before it goes through a PR. The reasoning is
written down, including a ledger of everything cut and what the cut cost. A design
record that lists only additions is a sales document.

## Licence stability

The public edition is released under the [MIT License](LICENSE). A version
published under it stays under it: that grant cannot be taken back, even if the
project is abandoned or a future maintainer would rather it were not.

## Becoming a maintainer

Sustained, high-quality contribution over time, plus judgment about what belongs
in the product — which mostly means a demonstrated willingness to argue *against*
adding things. Maintainers are invited, not applied for.

## If this project is abandoned

The [CHANGELOG](CHANGELOG.md) records every release date, so the Apache 2.0
conversion date of every version is computable without us. The methodology tree
under [`edify/`](edify/) is plain Markdown and useful without the CLI. The graph
format is documented, checksummed TSV that any tool can read.

Nothing here requires us to stay alive for your repository to keep working.
