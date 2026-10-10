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
  [`is_inclusion_list_satisfied`](./fork-choice.md#new-is_inclusion_list_satisfied)
  function MUST return `True` if the execution engine returns `NOT_VALIDATED`.
  An `INVALIDATED` response MUST return `False`.

For each optimistically imported beacon block, the consensus engine MUST retain
the inclusion list transactions, membership and revealed claims supplied for its
check. When its payload transitions from `NOT_VALIDATED` to `VALID`, it MUST
repeat `engine_newPayloadV6` with those exact inputs and record the returned
inclusion list satisfaction for that beacon block. `engine_forkchoiceUpdatedV5`
does not return this verdict: different beacon blocks may carry the same
execution payload with different claims or local inclusion list views. The
recorded inclusion list satisfaction of its ancestors remains unchanged. The
retained inputs MAY be discarded after the verdict is recorded or the block is
invalidated or pruned from fork choice.
