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
retain the exact `engine_newPayloadV6` inputs, including the separate ILs and
revealed claims. It records `None` in
`store.payload_inclusion_list_satisfaction` while execution validation or
inclusion checking is pending, including when execution is already `VALID`. An
`INVALIDATED` execution response records `False`.

Once execution is `VALID`, the adapter MUST poll
`engine_getInclusionListVerdictV1` with its returned `inclusionCheckId`, without
resending the payload. Pending execution retains the normal `newPayload` retry
path. After an unknown or evicted identifier, it MAY resubmit the retained
inputs to recover the check; it MUST NOT reconstruct them from a later IL view.
A completed verdict is recorded only for the associated beacon block; ancestors
and other blocks sharing its execution hash are unchanged. Forkchoice responses
report execution validity only.

Pending checks do not prevent optimistic import, but MUST NOT be treated as
satisfied for payload extension or validator duties requiring inclusion
satisfaction. Execution becoming `VALID` alone does not complete the inclusion
check. Retained inputs MAY be discarded once the verdict is recorded or the
block is invalidated or pruned from fork choice.
