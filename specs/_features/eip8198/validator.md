# EIP-8198 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Slot timing](#slot-timing)
  - [Inherited behavior](#inherited-behavior)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-8198.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below. No
new duty and no new deadline value is introduced.

### Slot timing

Honest validator duties are specified as actions taken a number of milliseconds
into a slot (attesting at `get_attestation_due_ms()`, aggregating at
`get_aggregate_due_ms()`, submitting sync messages, payload attestations,
inclusion lists, etc. at their respective deadlines). Two rules define how these
translate to wall-clock time after the fork:

- **Slot start times follow the remapped timeline.** The wall-clock start of
  `slot` is `compute_time_at_slot(state, slot)` as modified in the EIP-8198
  beacon chain document: slots up to `EIP8198_FORK_EPOCH * SLOTS_PER_EPOCH`
  start at `SLOT_DURATION_MS` intervals from genesis, and later slots at
  `SLOT_DURATION_MS_EIP8198` intervals from the fork time. Validators MUST
  schedule duties against this timeline; deriving slot starts as
  `genesis_time + slot * SLOT_DURATION_MS` is incorrect after the fork.
  Equivalently, the time elapsed in the current slot is given by the fork
  choice's `get_time_into_slot_ms`.
- **Deadlines rescale automatically.** All intra-slot deadlines are expressed in
  basis points of the slot duration through `get_slot_component_duration_ms`,
  which is modified in the EIP-8198 fork choice document to use
  `SLOT_DURATION_MS_EIP8198`. The basis-point constants themselves are
  unchanged, so each duty keeps its relative position in the slot (e.g.
  attesting still happens 25% of the way into the slot).

The first post-fork slot begins exactly at the end of the last pre-fork slot
(the fork time); duties in that slot are already scheduled on the new timeline.

### Inherited behavior

The following existing behaviors are correct without further changes; they are
listed because they depend on the slot duration indirectly:

- **Execution payload timestamp**: block preparation sets
  `payload_attributes.timestamp` via `compute_time_at_slot(state, state.slot)`
  and therefore follows the remapped timeline through the beacon chain
  document's override.
- **Eth1 data voting**: `voting_period_start_time` is derived from
  `compute_time_at_slot` and likewise inherits the remap. (Post-merge, eth1 data
  voting is vestigial; this is noted only for completeness.)
- **Epoch-denominated durations** (sync committee periods, proposer lookahead,
  subnet subscription periods) are unchanged in epoch terms; their wall-clock
  durations shrink by the slot-duration ratio. No constant is rescaled.
