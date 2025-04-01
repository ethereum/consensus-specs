# Electra -- Weak Subjectivity Guide

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom Types](#custom-types)
- [Constants](#constants)
- [Configuration](#configuration)
- [Weak Subjectivity Checkpoint](#weak-subjectivity-checkpoint)
- [Weak Subjectivity Period](#weak-subjectivity-period)
  - [Calculating the Weak Subjectivity Period](#calculating-the-weak-subjectivity-period)
    - [`compute_weak_subjectivity_period`](#compute_weak_subjectivity_period)
- [Weak Subjectivity Sync](#weak-subjectivity-sync)
  - [Weak Subjectivity Sync Procedure](#weak-subjectivity-sync-procedure)
  - [Checking for Stale Weak Subjectivity Checkpoint](#checking-for-stale-weak-subjectivity-checkpoint)
    - [`is_within_weak_subjectivity_period`](#is_within_weak_subjectivity_period)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document is an extension of the [Phase 0 -- Weak Subjectivity
Guide](../phase0/weak-subjectivity.md). All behaviors and definitions defined in this document, and
documents it extends, carry over unless explicitly noted or overridden.

This document is a guide for implementing Weak Subjectivity protections in Electra. The Weak
Subjectivity Period (WSP) calculations have changed in Electra due to EIP-7251, which increases the
maximum effective balance for validators and allows validators to consolidate.

## Custom Types

| Name | SSZ Equivalent | Description |
| - | - | - |
| `Ether` | `uint64` | an amount in Ether |

## Constants

| Name | Value |
| - | - |
| `ETH_TO_GWEI` | `uint64(10**9)` |

## Configuration

| Name | Value |
| - | - |
| `SAFETY_DECAY` | `uint64(10)` |

## Weak Subjectivity Checkpoint

Any `Checkpoint` object can be used as a Weak Subjectivity Checkpoint.
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

A detailed analysis of the calculation of the weak subjectivity period is made in [here](https://notes.ethereum.org/@CarlBeek/electra_weak_subjectivity).

#### `compute_weak_subjectivity_period`

```python
def compute_weak_subjectivity_period(state: BeaconState) -> uint64:
    """
    Returns the weak subjectivity period for the current ``state``.
    This computation takes into account the effect of:
        - validator set churn (bounded by ``get_balance_churn_limit()`` per epoch), and
    A detailed calculation can be found at:
    https://github.com/runtimeverification/beacon-chain-verification/blob/master/weak-subjectivity/weak-subjectivity-analysis.pdf
    """
    t = get_total_active_balance(state)
    delta = get_balance_churn_limit(state)
    D = SAFETY_DECAY

    epochs_for_validator_set_churn = D * t // (4 * delta * 100)
    ws_period = MIN_VALIDATOR_WITHDRAWABILITY_DELAY + epochs_for_validator_set_churn

    return ws_period
```

## Weak Subjectivity Sync

Clients should allow users to input a Weak Subjectivity Checkpoint at startup,
and guarantee that any successful sync leads to the given Weak Subjectivity Checkpoint along the canonical chain.
If such a sync is not possible, the client should treat this as a critical and irrecoverable failure.

### Weak Subjectivity Sync Procedure

1. Input a Weak Subjectivity Checkpoint as a CLI parameter in `block_root:epoch_number` format,
   where `block_root` (an "0x" prefixed 32-byte hex string) and `epoch_number` (an integer) represent a valid `Checkpoint`.
   Example of the format:

   ```
   0x8584188b86a9296932785cc2827b925f9deebacce6d72ad8d53171fa046b43d9:9544
   ```

2. Check the weak subjectivity requirements:
    - *IF* `epoch_number > store.finalized_checkpoint.epoch`,
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

#### `is_within_weak_subjectivity_period`

```python
def is_within_weak_subjectivity_period(store: Store, ws_state: BeaconState, ws_checkpoint: Checkpoint) -> bool:
    # Clients may choose to validate the input state against the input Weak Subjectivity Checkpoint
    assert ws_state.latest_block_header.state_root == ws_checkpoint.root
    assert compute_epoch_at_slot(ws_state.slot) == ws_checkpoint.epoch

    ws_period = compute_weak_subjectivity_period(ws_state)
    ws_state_epoch = compute_epoch_at_slot(ws_state.slot)
    current_epoch = compute_epoch_at_slot(get_current_slot(store))
    return current_epoch <= ws_state_epoch + ws_period
```
