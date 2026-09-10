---
name: review
description: >-
  Review changes. Check that they are correct, consistent with the rest of the
  specifications, and compliant with the project's conventions. Always load this
  skill before reviewing changes.
compatibility: Requires make and uv
---

# Reviewing changes

## Load relevant skills

Before reviewing, load the skills that govern the area under review. Their
conventions define what a correct change looks like, and a review largely checks
the change against them.

## Understand the intent

Before judging a change, understand what it is meant to accomplish. Consult the
pull request description, the linked issue, or the relevant EIP. Correctness is
relative to intent, so confirm that the change actually does what it sets out to
do before looking for smaller issues.

## Scope

A change should have a single, well-defined objective. Flag unrelated changes
that have been bundled in, and suggest splitting them into separate pull
requests. A focused change is easier to review and easier to reason about later.

## Terminology

Terminology must match older specifications. Reuse the existing name for a
concept instead of inventing a synonym, so that a term means the same thing
across every spec.

## Section ordering

The order of sections within a document must match the order established by
older specifications. When an item is added or modified, place its section where
the equivalent item appears in earlier specs rather than introducing a new
arrangement.

## Backported changes

The specifications are organized as a sequence of upgrades, where each builds on
the one before it. When some change is backported to an older spec so that it is
easier to express a change in a newer spec, the functionality in the older spec
(if considered stable) must not change unless explicitly stated somewhere.

## Providing feedback

Only raise an issue when you are confident it is a genuine mistake. Do not
report speculative concerns. Stylistic issues are worth reporting, but only when
you are confident the code does not adhere to the repository's defined
standards.

When suggesting a change, be clear and concise. If necessary, provide an example
so the intent is unambiguous. Keep code suggestions compliant with `make lint`.
Running the linter over the suggested code, once applied, should produce no
complaints.
