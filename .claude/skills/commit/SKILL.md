---
name: commit
description: >-
  Commit changes and open pull requests. Follow the project's conventions
  for scope, formatting, and writing style. Use when the user asks to make
  a commit or pull request.
compatibility: Requires make, uv, git
---

# Committing changes

## Scope

A pull request should have a single, well-defined objective. If a change
accomplishes multiple unrelated things, split it into separate pull requests.
For a large change with one objective, break it into multiple commits when
possible. Each commit should adhere to the preparation steps below.

## Preparation

Check that the branch is up to date with `ethereum/consensus-specs@master`;
rebase if it is not. Run the linter (`make lint`) and ensure it passes. If the
linter makes modifications, stage these fixes. Ensure relevant tests pass if the
specifications or testing framework changed.

## Writing style

The subject line (and PR title) must be written in the imperative mood. It must
not have component prefixes like the "conventional commit" style. It must be
less than or equal to 68 characters. Use sentence case, not title case. Code
(functions, classes, etc) must be wrapped in backticks. There must be no
terminal punctuation.

The body (and PR description) should describe what and why, not how. Wrap the
body at 72 characters. Do not use section headers. A single paragraph is ideal,
but multiple paragraphs are okay if necessary. Keep things simple and try to be
concise. Mention any relevant information, concerns, or related PRs/issues. Do
not mention running the linter or tests; CI will show this. Do not include a
`Co-Authored-By` trailer.
