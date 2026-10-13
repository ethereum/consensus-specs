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

For each beacon block with a pending inclusion check, the consensus engine MUST
retain the context identifier and exact inclusion list transactions, membership
and revealed claims submitted to the execution engine. It records `None` in
`store.payload_inclusion_list_satisfaction` while either execution validation or
inclusion checking is pending, including when execution is already `VALID`.
An `INVALIDATED` execution response records `False`.

The consensus engine MUST retrieve deferred results through
`engine_getInclusionListStatusV1`, or through `engine_forkchoiceUpdatedV5` when
selecting the associated execution block as head. On `-38007: Unknown inclusion context`, it MUST repeat `engine_newPayloadV6` with the retained inputs and use
the returned identifier. It MUST NOT reconstruct those inputs from a later
inclusion list view. A completed verdict is recorded only for the associated
beacon block; ancestors and other blocks sharing its execution hash are unchanged.

Pending checks do not prevent optimistic import, but MUST NOT be treated as
satisfied for payload extension or validator duties requiring inclusion
satisfaction. Execution becoming `VALID` alone does not complete the inclusion
check. Retained inputs MAY be discarded once the verdict is recorded or the block
is invalidated or pruned from fork choice.
