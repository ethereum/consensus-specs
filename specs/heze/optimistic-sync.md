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

While execution validation is incomplete, the consensus engine MUST retain the
exact `engine_newPayloadV6` inputs, including the separate ILs and revealed
claims, and record `None` in `store.payload_inclusion_list_satisfaction`.
Retries use these inputs, not a later IL view. A `VALID` response includes a
completed boolean inclusion verdict; an `INVALIDATED` execution response
records `False`.

The verdict is recorded only for the associated beacon block; ancestors and
other blocks sharing its execution hash are unchanged. Forkchoice responses
report execution validity only. Retained inputs MAY be discarded once the
verdict is recorded or the block is invalidated or pruned from fork choice.

An unavailable verdict does not prevent optimistic import, but MUST NOT be
treated as satisfaction for payload extension or validator duties requiring it.
