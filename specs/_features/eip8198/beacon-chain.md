# EIP-8198 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
- [Helpers](#helpers)
  - [Misc](#misc)
    - [New `compute_slot_start_time_ms`](#new-compute_slot_start_time_ms)
    - [New `compute_slot_at_time_ms`](#new-compute_slot_at_time_ms)
    - [New `compute_slot_range_duration_ms`](#new-compute_slot_range_duration_ms)
    - [Modified `compute_time_at_slot`](#modified-compute_time_at_slot)
    - [Modified `get_blob_parameters`](#modified-get_blob_parameters)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_base_reward_per_increment`](#modified-get_base_reward_per_increment)
    - [Modified `get_inactivity_penalty_deltas`](#modified-get_inactivity_penalty_deltas)
    - [Modified `get_activation_churn_limit`](#modified-get_activation_churn_limit)
    - [Modified `get_exit_churn_limit`](#modified-get_exit_churn_limit)
    - [Modified `get_consolidation_churn_limit`](#modified-get_consolidation_churn_limit)

<!-- mdformat-toc end -->

## Introduction

EIP-8198 ("Quick Slots") reduces the slot duration from 12 to 10 seconds. The
slot structure is unchanged, and all intra-slot deadlines are expressed in basis
points of the slot duration, so they rescale automatically. The remaining
duration-dependent parameters are rescaled by the slot-duration ratio
`r = SLOT_DURATION_MS_EIP8198 / SLOT_DURATION_MS` to keep their wall-clock
behavior constant: issuance and churn are per-epoch rates and scale by `r`,
while the inactivity penalty scales by `r**2` so that the cumulative leak over a
fixed wall-clock duration is unchanged. Rather than pre-computing rounded
constants, each formula applies the ratio inline, keeping
`SLOT_DURATION_MS_EIP8198` the single source of truth for the target slot
duration.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Configuration

### Time parameters

| Name                       | Value           | Unit         | Duration   |
| -------------------------- | --------------- | ------------ | ---------- |
| `SLOT_DURATION_MS_EIP8198` | `Uint64(10000)` | milliseconds | 10 seconds |

*Note*: `SLOT_DURATION_MS_EIP8198` MUST be less than `SLOT_DURATION_MS`, and
both MUST be positive multiples of `1000`, so that every slot boundary has an
exact integer-second timestamp.

## Helpers

### Misc

#### New `compute_slot_start_time_ms`

```python
def compute_slot_start_time_ms(genesis_time: Uint64, slot: Slot) -> Uint64:
    """
    Return the absolute Unix time in milliseconds at the start of ``slot``.
    """
    slots_since_genesis = slot - GENESIS_SLOT
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return Uint64(genesis_time * 1000 + slots_since_genesis * SLOT_DURATION_MS)
    fork_slot = compute_start_slot_at_epoch(EIP8198_FORK_EPOCH)
    if slot < fork_slot:
        return Uint64(genesis_time * 1000 + slots_since_genesis * SLOT_DURATION_MS)
    time_before_fork_ms = (fork_slot - GENESIS_SLOT) * SLOT_DURATION_MS
    time_after_fork_ms = (slot - fork_slot) * SLOT_DURATION_MS_EIP8198
    return Uint64(genesis_time * 1000 + time_before_fork_ms + time_after_fork_ms)
```

#### New `compute_slot_at_time_ms`

```python
def compute_slot_at_time_ms(genesis_time: Uint64, time_ms: Uint64) -> Slot:
    """
    Return the slot corresponding to absolute Unix time ``time_ms``.
    """
    assert time_ms >= genesis_time * 1000
    time_since_genesis_ms = time_ms - genesis_time * 1000
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return Slot(GENESIS_SLOT + time_since_genesis_ms // SLOT_DURATION_MS)
    fork_slot = compute_start_slot_at_epoch(EIP8198_FORK_EPOCH)
    time_before_fork_ms = (fork_slot - GENESIS_SLOT) * SLOT_DURATION_MS
    if time_since_genesis_ms < time_before_fork_ms:
        return Slot(GENESIS_SLOT + time_since_genesis_ms // SLOT_DURATION_MS)
    return Slot(
        fork_slot + (time_since_genesis_ms - time_before_fork_ms) // SLOT_DURATION_MS_EIP8198
    )
```

#### New `compute_slot_range_duration_ms`

```python
def compute_slot_range_duration_ms(start_slot: Slot, end_slot: Slot) -> Uint64:
    """
    Return the duration of ``[start_slot, end_slot)`` in milliseconds.
    """
    assert start_slot <= end_slot
    return compute_slot_start_time_ms(Uint64(0), end_slot) - compute_slot_start_time_ms(
        Uint64(0), start_slot
    )
```

#### Modified `compute_time_at_slot`

*Note*: Without this override the execution payload timestamp, validated against
`compute_time_at_slot` in `process_execution_payload`, would drift ahead of
wall-clock time by `SLOT_DURATION_MS - SLOT_DURATION_MS_EIP8198` per post-fork
slot.

```python
def compute_time_at_slot(state: BeaconState, slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    return compute_time_at_slot_ms(state, slot) // 1000
```

#### Modified `get_blob_parameters`

*Note*: The synthetic entry at `EIP8198_FORK_EPOCH` scales the preceding maximum
by the slot-duration ratio and is equivalent to appending it to `BLOB_SCHEDULE`;
a later explicit schedule entry takes precedence.

```python
def get_blob_parameters(epoch: Epoch) -> BlobParameters:
    """
    Return the blob parameters at a given epoch.
    """
    for entry in sorted(BLOB_SCHEDULE, key=lambda e: e["EPOCH"], reverse=True):
        if epoch >= entry["EPOCH"] and entry["EPOCH"] >= EIP8198_FORK_EPOCH:
            return BlobParameters(entry["EPOCH"], entry["MAX_BLOBS_PER_BLOCK"])

    if epoch >= EIP8198_FORK_EPOCH:
        pre_fork_epoch = Epoch(EIP8198_FORK_EPOCH - 1)
        pre_fork_parameters = get_blob_parameters(pre_fork_epoch)
        return BlobParameters(
            EIP8198_FORK_EPOCH,
            pre_fork_parameters.max_blobs_per_block * SLOT_DURATION_MS_EIP8198 // SLOT_DURATION_MS,
        )

    for entry in sorted(BLOB_SCHEDULE, key=lambda e: e["EPOCH"], reverse=True):
        if epoch >= entry["EPOCH"]:
            return BlobParameters(entry["EPOCH"], entry["MAX_BLOBS_PER_BLOCK"])
    return BlobParameters(ELECTRA_FORK_EPOCH, MAX_BLOBS_PER_BLOCK_ELECTRA)
```

### Beacon state accessors

#### Modified `get_base_reward_per_increment`

*Note*: The division is deferred so that the exact
`SLOT_DURATION_MS_EIP8198 / SLOT_DURATION_MS` ratio applies, rather than
rounding `BASE_REWARD_FACTOR` to a new integer constant.

```python
def get_base_reward_per_increment(state: BeaconState) -> Gwei:
    return Gwei(
        EFFECTIVE_BALANCE_INCREMENT
        * BASE_REWARD_FACTOR
        # [Modified in EIP8198]
        * SLOT_DURATION_MS_EIP8198
        // SLOT_DURATION_MS
        // integer_squareroot(get_total_active_balance(state))
    )
```

#### Modified `get_inactivity_penalty_deltas`

*Note*: The inactivity penalty scales with the square of the epoch duration, so
that the cumulative penalty over a fixed wall-clock leak duration is unchanged;
the squared ratio is folded into the penalty denominator.

```python
def get_inactivity_penalty_deltas(state: BeaconState) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return the inactivity penalty deltas by considering timely target participation flags and inactivity scores.
    """
    rewards = [Gwei(0) for _ in range(len(state.validators))]
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    previous_epoch = get_previous_epoch(state)
    matching_target_indices = get_unslashed_participating_indices(
        state, TIMELY_TARGET_FLAG_INDEX, previous_epoch
    )
    for index in get_eligible_validator_indices(state):
        if index not in matching_target_indices:
            penalty_numerator = (
                state.validators[index].effective_balance * state.inactivity_scores[index]
            )
            # [Modified in EIP8198]
            penalty_denominator = (
                INACTIVITY_SCORE_BIAS
                * INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
                * SLOT_DURATION_MS
                * SLOT_DURATION_MS
                // (SLOT_DURATION_MS_EIP8198 * SLOT_DURATION_MS_EIP8198)
            )
            penalties[index] += Gwei(penalty_numerator // penalty_denominator)
    return rewards, penalties
```

#### Modified `get_activation_churn_limit`

*Note*: The cap is applied before scaling, so the maximum activation rate is
scaled too, and the increment rounding is applied once, after scaling.

```python
def get_activation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit for activations, rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    # [Modified in EIP8198]
    churn = min(MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS, churn)
    churn = churn * SLOT_DURATION_MS_EIP8198 // SLOT_DURATION_MS
    return Gwei(churn - churn % EFFECTIVE_BALANCE_INCREMENT)
```

#### Modified `get_exit_churn_limit`

```python
def get_exit_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit for exits, rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    # [Modified in EIP8198]
    churn = churn * SLOT_DURATION_MS_EIP8198 // SLOT_DURATION_MS
    return Gwei(churn - churn % EFFECTIVE_BALANCE_INCREMENT)
```

#### Modified `get_consolidation_churn_limit`

```python
def get_consolidation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit reserved for consolidations (EIP-7521).
    Derived from total active balance and rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = get_total_active_balance(state) // CONSOLIDATION_CHURN_LIMIT_QUOTIENT
    # [Modified in EIP8198]
    churn = churn * SLOT_DURATION_MS_EIP8198 // SLOT_DURATION_MS
    return Gwei(churn - churn % EFFECTIVE_BALANCE_INCREMENT)
```
