# Ethereum 2.0 Phase 0 -- Weak Subjectivity Guide

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Constants](#constants)
- [Weak Subjectivity Checkpoint](#weak-subjectivity-checkpoint)
- [Weak Subjectivity Period](#weak-subjectivity-period)
  - [Calculating the Weak Subjectivity Period](#calculating-the-weak-subjectivity-period)
- [Weak Subjectivity Sync](#weak-subjectivity-sync)
  - [Weak Subjectivity Sync Procedure](#weak-subjectivity-sync-procedure)
  - [Checking for Stale Weak Subjectivity Checkpoint](#checking-for-stale-weak-subjectivity-checkpoint)
- [Distributing Weak Subjectivity Checkpoints](#distributing-weak-subjectivity-checkpoints)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document is a guide for implementing the Weak Subjectivity protections in Phase 0 of Ethereum 2.0.
This document is still a work-in-progress, and is subject to large changes.
For more information about weak subjectivity and why it is required, please refer to:

- [Weak Subjectivity in Eth2.0](https://notes.ethereum.org/@adiasg/weak-subjectvity-eth2)
- [Proof of Stake: How I Learned to Love Weak Subjectivity](https://blog.ethereum.org/2014/11/25/proof-stake-learned-love-weak-subjectivity/)

## Prerequisites

This document uses data structures, constants, functions, and terminology from
[Phase 0 -- The Beacon Chain](./beacon-chain.md) and [Phase 0 -- Beacon Chain Fork Choice](./fork-choice.md).

## Constants

| Name           | Value        |
|----------------|--------------|
| `SAFETY_DECAY` | `uint64(10)` |

## Weak Subjectivity Checkpoint

Any `Checkpoint` can used be a Weak Subjectivity Checkpoint.
These Weak Subjectivity Checkpoints are distributed by providers,
downloaded by users and/or distributed as a part of clients, and used as input while syncing a client.

## Weak Subjectivity Period

The Weak Subjectivity Period is the number of recent epochs within which there
must be a Weak Subjectivity Checkpoint to ensure that an attacker who takes control
of the validator set at the beginning of the period is slashed at least a minimum threshold
in the event that a conflicting `Checkpoint` is finalized.

`SAFETY_DECAY` is defined as the maximum percentage tolerable loss in the one-third
safety margin of FFG finality. Thus, any attack exploiting the Weak Subjectivity Period has
a safety margin of at least `1/3 - SAFETY_DECAY/100`.

### Calculating the Weak Subjectivity Period

*Note*: `compute_weak_subjectivity_period()` is planned to be updated when a more accurate calculation is made.

```python
def compute_weak_subjectivity_period(state: BeaconState) -> uint64:
    weak_subjectivity_period = MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    validator_count = len(get_active_validator_indices(state, get_current_epoch(state)))
    if validator_count >= MIN_PER_EPOCH_CHURN_LIMIT * CHURN_LIMIT_QUOTIENT:
        weak_subjectivity_period += SAFETY_DECAY * CHURN_LIMIT_QUOTIENT // (2 * 100)
    else:
        weak_subjectivity_period += SAFETY_DECAY * validator_count // (2 * 100 * MIN_PER_EPOCH_CHURN_LIMIT)
    return weak_subjectivity_period
```

*Details about the calculation*:
- `100` appears in the denominator to get the actual percentage ratio from `SAFETY_DECAY`
- For more information about other terms in this equation, refer to
  [Weak Subjectivity in Eth2.0](https://notes.ethereum.org/@adiasg/weak-subjectvity-eth2)

A brief reference for what these values look like in practice:

| `validator_count` | `weak_subjectivity_period` |
| ----  | ---- |
| 1024  | 268 |
| 2048  | 281 |
| 4096  | 307 |
| 8192  | 358 |
| 16384 | 460 |
| 32768 | 665 |
| 65536 | 1075 |
| 131072  | 1894 |
| 262144  | 3532 |
| 524288  | 3532 |

## Weak Subjectivity Sync

Clients should allow users to input a Weak Subjectivity Checkpoint at startup, and guarantee that any successful sync leads to the given Weak Subjectivity Checkpoint along the canonical chain. If such a sync is not possible, the client should treat this as a critical and irrecoverable failure.

### Weak Subjectivity Sync Procedure

1. Input a Weak Subjectivity Checkpoint as a CLI parameter in `block_root:epoch_number` format,
  where `block_root` (an "0x" prefixed 32-byte hex string) and `epoch_number` (an integer) represent a valid `Checkpoint`.
  Example of the format:
```
0x8584188b86a9296932785cc2827b925f9deebacce6d72ad8d53171fa046b43d9:9544
```
2.  - *IF* `epoch_number > store.finalized_checkpoint.epoch`,
      then *ASSERT* during block sync that block with root `block_root` is in the sync path at epoch `epoch_number`.
      Emit descriptive critical error if this assert fails, then exit client process.
    - *IF* `epoch_number <= store.finalized_checkpoint.epoch`,
      then *ASSERT* that the block in the canonical chain at epoch `epoch_number` has root `block_root`.
      Emit descriptive critical error if this assert fails, then exit client process.

### Checking for Stale Weak Subjectivity Checkpoint
Clients may choose to validate that the input Weak Subjectivity Checkpoint is not stale at the time of startup.
To support this mechanism, the client needs to take the state at the Weak Subjectivity Checkpoint as
a CLI parameter input (or fetch the state associated with the input Weak Subjectivity Checkpoint from some source).
The check can be implemented in the following way:

```python
def is_within_weak_subjectivity_period(store: Store, ws_state: BeaconState, ws_checkpoint: Checkpoint) -> bool:
    # Clients may choose to validate the input state against the input Weak Subjectivity Checkpoint
    assert ws_state.latest_block_header.state_root == store.block_states[ws_checkpoint.root]
    assert compute_epoch_at_slot(ws_state.slot) == ws_checkpoint.epoch

    ws_period = compute_weak_subjectivity_period(ws_state)
    ws_state_epoch = compute_epoch_at_slot(ws_state.slot)
    current_epoch = compute_epoch_at_slot(get_current_slot(store))
    return current_epoch <= ws_state_epoch + ws_period
```

## Distributing Weak Subjectivity Checkpoints
This section will be updated soon.
