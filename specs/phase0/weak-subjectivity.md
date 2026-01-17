# Phase 0 -- Weak Subjectivity Guide

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Types](#types)
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
- [Distributing Weak Subjectivity Checkpoints](#distributing-weak-subjectivity-checkpoints)

<!-- mdformat-toc end -->

## Introduction

This document is a guide for implementing the Weak Subjectivity protections in
Phase 0. This document is still a work-in-progress, and is subject to large
changes. For more information about weak subjectivity and why it is required,
please refer to:

- [Weak Subjectivity in Ethereum Proof-of-Stake](https://notes.ethereum.org/@adiasg/weak-subjectvity-eth2)
- [Proof of Stake: How I Learned to Love Weak Subjectivity](https://blog.ethereum.org/2014/11/25/proof-stake-learned-love-weak-subjectivity/)

## Prerequisites

This document uses data structures, constants, functions, and terminology from
[Phase 0 -- The Beacon Chain](./beacon-chain.md) and
[Phase 0 -- Beacon Chain Fork Choice](./fork-choice.md).

## Types

| Name    | SSZ Equivalent | Description        |
| ------- | -------------- | ------------------ |
| `Ether` | `uint64`       | an amount in Ether |

## Constants

| Name          | Value           |
| ------------- | --------------- |
| `ETH_TO_GWEI` | `uint64(10**9)` |

## Configuration

| Name           | Value        |
| -------------- | ------------ |
| `SAFETY_DECAY` | `uint64(10)` |

## Weak Subjectivity Checkpoint

Any `Checkpoint` object can be used as a Weak Subjectivity Checkpoint. These
Weak Subjectivity Checkpoints are distributed by providers, downloaded by users
and/or distributed as a part of clients, and used as input while syncing a
client.

## Weak Subjectivity Period

The Weak Subjectivity Period is the number of recent epochs within which there
must be a Weak Subjectivity Checkpoint to ensure that an attacker who takes
control of the validator set at the beginning of the period is slashed at least
a minimum threshold in the event that a conflicting `Checkpoint` is finalized.

`SAFETY_DECAY` is defined as the maximum percentage tolerable loss in the
one-third safety margin of FFG finality. Thus, any attack exploiting the Weak
Subjectivity Period has a safety margin of at least `1/3 - SAFETY_DECAY/100`.

### Calculating the Weak Subjectivity Period

A detailed analysis of the calculation of the weak subjectivity period is made
in
[this report](https://github.com/runtimeverification/beacon-chain-verification/blob/master/weak-subjectivity/weak-subjectivity-analysis.pdf).

*Note*: The expressions in the report use fractions, whereas the consensus-specs
only use `uint64` arithmetic. The expressions have been simplified to avoid
computing fractions, and more details can be found
[here](https://www.overleaf.com/read/wgjzjdjpvpsd).

*Note*: The calculations here use `Ether` instead of `Gwei`, because the large
magnitude of balances in `Gwei` can cause an overflow while computing using
`uint64` arithmetic operations. Using `Ether` reduces the magnitude of the
multiplicative factors by an order of `ETH_TO_GWEI` (`= 10**9`) and avoid the
scope for overflows in `uint64`.

#### `compute_weak_subjectivity_period`

```python
def compute_weak_subjectivity_period(state: BeaconState) -> uint64:
    """
    Returns the weak subjectivity period for the current ``state``.
    This computation takes into account the effect of:
        - validator set churn (bounded by ``get_validator_churn_limit()`` per epoch), and
        - validator balance top-ups (bounded by ``MAX_DEPOSITS * SLOTS_PER_EPOCH`` per epoch).
    A detailed calculation can be found at:
    https://github.com/runtimeverification/beacon-chain-verification/blob/master/weak-subjectivity/weak-subjectivity-analysis.pdf
    """
    ws_period = MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    N = len(get_active_validator_indices(state, get_current_epoch(state)))
    t = get_total_active_balance(state) // N // ETH_TO_GWEI
    T = MAX_EFFECTIVE_BALANCE // ETH_TO_GWEI
    delta = get_validator_churn_limit(state)
    Delta = MAX_DEPOSITS * SLOTS_PER_EPOCH
    D = SAFETY_DECAY

    if T * (200 + 3 * D) < t * (200 + 12 * D):
        epochs_for_validator_set_churn = (
            N * (t * (200 + 12 * D) - T * (200 + 3 * D)) // (600 * delta * (2 * t + T))
        )
        epochs_for_balance_top_ups = N * (200 + 3 * D) // (600 * Delta)
        ws_period += max(epochs_for_validator_set_churn, epochs_for_balance_top_ups)
    else:
        ws_period += 3 * N * D * t // (200 * Delta * (T - t))

    return ws_period
```

A brief reference for what these values look like in practice
([reference script](https://gist.github.com/adiasg/3aceab409b36aa9a9d9156c1baa3c248)):

| Safety Decay | Avg. Val. Balance (ETH) | Val. Count | Weak Sub. Period (Epochs) |
| ------------ | ----------------------- | ---------- | ------------------------- |
| 10           | 28                      | 32768      | 504                       |
| 10           | 28                      | 65536      | 752                       |
| 10           | 28                      | 131072     | 1248                      |
| 10           | 28                      | 262144     | 2241                      |
| 10           | 28                      | 524288     | 2241                      |
| 10           | 28                      | 1048576    | 2241                      |
| 10           | 32                      | 32768      | 665                       |
| 10           | 32                      | 65536      | 1075                      |
| 10           | 32                      | 131072     | 1894                      |
| 10           | 32                      | 262144     | 3532                      |
| 10           | 32                      | 524288     | 3532                      |
| 10           | 32                      | 1048576    | 3532                      |

## Weak Subjectivity Sync

Clients should allow users to input a Weak Subjectivity Checkpoint at startup,
and guarantee that any successful sync leads to the given Weak Subjectivity
Checkpoint along the canonical chain. If such a sync is not possible, the client
should treat this as a critical and irrecoverable failure.

### Weak Subjectivity Sync Procedure

1. Input a Weak Subjectivity Checkpoint as a CLI parameter in
   `block_root:epoch_number` format, where `block_root` (an "0x" prefixed
   32-byte hex string) and `epoch_number` (an integer) represent a valid
   `Checkpoint`. Example of the format:

   ```
   0x8584188b86a9296932785cc2827b925f9deebacce6d72ad8d53171fa046b43d9:9544
   ```

2. Check the weak subjectivity requirements:

   - *IF* `epoch_number > store.finalized_checkpoint.epoch`, then *ASSERT*
     during block sync that block with root `block_root` is in the sync path at
     epoch `epoch_number`. Emit descriptive critical error if this assert fails,
     then exit client process.
   - *IF* `epoch_number <= store.finalized_checkpoint.epoch`, then *ASSERT* that
     the block in the canonical chain at epoch `epoch_number` has root
     `block_root`. Emit descriptive critical error if this assert fails, then
     exit client process.

### Checking for Stale Weak Subjectivity Checkpoint

Clients may choose to validate that the input Weak Subjectivity Checkpoint is
not stale at the time of startup. To support this mechanism, the client needs to
take the state at the Weak Subjectivity Checkpoint as a CLI parameter input (or
fetch the state associated with the input Weak Subjectivity Checkpoint from some
source). The check can be implemented in the following way:

#### `is_within_weak_subjectivity_period`

```python
def is_within_weak_subjectivity_period(
    store: Store, ws_state: BeaconState, ws_checkpoint: Checkpoint
) -> bool:
    # Clients may choose to validate the input state against the input Weak Subjectivity Checkpoint
    assert get_block_root(ws_state, ws_checkpoint.epoch) == ws_checkpoint.root
    assert compute_epoch_at_slot(ws_state.slot) == ws_checkpoint.epoch

    ws_period = compute_weak_subjectivity_period(ws_state)
    ws_state_epoch = compute_epoch_at_slot(ws_state.slot)
    current_epoch = compute_epoch_at_slot(get_current_slot(store))
    return current_epoch <= ws_state_epoch + ws_period
```

## Distributing Weak Subjectivity Checkpoints

This section will be updated soon.
