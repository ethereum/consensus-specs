# Heze -- Optimistic Sync

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Mechanisms](#mechanisms)
  - [How to optimistically import blocks](#how-to-optimistically-import-blocks)
    - [New How to track inclusion list satisfaction](#new-how-to-track-inclusion-list-satisfaction)

<!-- mdformat-toc end -->

## Introduction

This document specifies the Heze modifications to optimistic sync for inclusion
list satisfaction. It extends the
[Bellatrix optimistic sync specification](../bellatrix/optimistic-sync.md).

## Mechanisms

### How to optimistically import blocks

#### New How to track inclusion list satisfaction

When optimistically importing a block:

- The
  [`is_inclusion_list_satisfied`](../fork-choice.md#new-is_inclusion_list_satisfied)
  function MUST return `True` if the execution engine returns `NOT_VALIDATED`.
  An `INVALIDATED` response MUST return `False`.

When a block transitions from `NOT_VALIDATED` -> `VALID`, the response from the
execution engine also indicates whether the block's execution payload satisfies
the inclusion list constraints. The consensus engine MUST record the result for
that block. The recorded inclusion list satisfaction of its ancestors remains
unchanged.
