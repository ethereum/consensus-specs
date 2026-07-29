# EIP-8198 -- Optimistic Sync

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `current_slot`](#modified-current_slot)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made to optimistic sync to implement
EIP-8198.

*Note*: This specification is built upon
[Optimistic Sync](../../../sync/optimistic.md).

## Helpers

### Modified `current_slot`

Let `current_slot: Slot` be
`compute_slot_at_time_ms(Uint64(genesis_time), Uint64(time * 1000))`, where
`time` is the UNIX time according to the local system clock.

*Note*: `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY` remains slot-denominated; its
wall-clock duration scales with the slot duration.
