# EIP-8198 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Preset](#preset)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
  - [Validator cycle](#validator-cycle)
- [Helpers](#helpers)
  - [New `compute_slot_start_time_ms`](#new-compute_slot_start_time_ms)
  - [Modified `compute_time_at_slot_ms`](#modified-compute_time_at_slot_ms)
  - [New `compute_slot_at_time_ms`](#new-compute_slot_at_time_ms)
  - [New `compute_slot_range_duration_ms`](#new-compute_slot_range_duration_ms)
  - [Modified `compute_time_at_slot`](#modified-compute_time_at_slot)
  - [Modified `get_blob_parameters`](#modified-get_blob_parameters)
  - [Modified `get_base_reward_per_increment`](#modified-get_base_reward_per_increment)
  - [Modified `get_inactivity_penalty_deltas`](#modified-get_inactivity_penalty_deltas)
  - [Modified `get_activation_churn_limit`](#modified-get_activation_churn_limit)
  - [Modified `get_exit_churn_limit`](#modified-get_exit_churn_limit)
  - [Modified `get_consolidation_churn_limit`](#modified-get_consolidation_churn_limit)
- [Data availability](#data-availability)

<!-- mdformat-toc end -->

## Introduction

EIP-8198 ("Quick Slots") reduces the slot duration from 12 to 8 seconds. The
slot structure is inherited unchanged from Heze, and all intra-slot deadlines
are expressed in basis points of the slot duration, so they rescale
automatically (see the modified `get_slot_component_duration_ms` in the
fork-choice document).

The parameters below match the EIP-8198 parameter table. Per-epoch issuance and
churn quantities are scaled by `8 / 12 = 2 / 3`; churn quotients are scaled by
the inverse `3 / 2`; and the inactivity penalty quotient is scaled by
`(3 / 2)**2 = 9 / 4`.

## Preset

| Name                                  | Value                              |
| ------------------------------------- | ---------------------------------- |
| `BASE_REWARD_FACTOR_EIP8198`          | `Uint64(42)`                       |
| `INACTIVITY_PENALTY_QUOTIENT_EIP8198` | `Uint64(37748736)` (= `9 * 2**22`) |

*Note*: These values intentionally use the integer-truncated parameters from
EIP-8198. In particular, the effective base reward factor is `42`, not the
unrounded rational value `64 * 2 / 3`.

## Configuration

### Time parameters

| Name                       | Value          | Unit         | Duration  |
| -------------------------- | -------------- | ------------ | --------- |
| `SLOT_DURATION_MS_EIP8198` | `Uint64(8000)` | milliseconds | 8 seconds |

Both `SLOT_DURATION_MS` and `SLOT_DURATION_MS_EIP8198` MUST be positive
multiples of `1000`. Beacon block timestamps are integer Unix seconds, so this
constraint ensures that every slot boundary has an exact timestamp.

### Validator cycle

| Name                                                 | Value                |
| ---------------------------------------------------- | -------------------- |
| `CHURN_LIMIT_QUOTIENT_EIP8198`                       | `Uint64(49152)`      |
| `CONSOLIDATION_CHURN_LIMIT_QUOTIENT_EIP8198`         | `Uint64(98304)`      |
| `MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA_EIP8198`          | `Gwei(85333333333)`  |
| `MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS_EIP8198` | `Gwei(170666666666)` |

*Note*: The published EIP-8198 table scales the pre-Gloas `CHURN_LIMIT_QUOTIENT`
from `65536` to `98304`. This feature is based on Heze, where Gloas has already
split churn: activation and exit use `CHURN_LIMIT_QUOTIENT_GLOAS = 32768`, while
consolidation retains the `65536` quotient. Applying the same `3 / 2` scaling
therefore yields `49152` for activation and exit and `98304` for consolidation.

## Helpers

### New `compute_slot_start_time_ms`

```python
def compute_slot_start_time_ms(genesis_time: Uint64, slot: Slot) -> Uint64:
    """
    Return the absolute Unix time in milliseconds at the start of ``slot``.
    """
    slots_since_genesis = slot - GENESIS_SLOT
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return Uint64(genesis_time * 1000 + slots_since_genesis * SLOT_DURATION_MS)
    fork_slot = EIP8198_FORK_EPOCH * SLOTS_PER_EPOCH
    if slot < fork_slot:
        return Uint64(genesis_time * 1000 + slots_since_genesis * SLOT_DURATION_MS)
    time_before_fork_ms = fork_slot * SLOT_DURATION_MS
    time_after_fork_ms = (slots_since_genesis - fork_slot) * SLOT_DURATION_MS_EIP8198
    return Uint64(genesis_time * 1000 + time_before_fork_ms + time_after_fork_ms)
```

### Modified `compute_time_at_slot_ms`

*Note*: This is the canonical EIP-8198 mapping from slots to wall-clock time.
Fork choice, networking, honest-validator scheduling, and execution timestamp
derivation all use this helper rather than independently reproducing the
piecewise timeline.

```python
def compute_time_at_slot_ms(state: BeaconState, slot: Slot) -> Uint64:
    """
    Return the time in milliseconds at the start of the given slot.
    """
    # [Modified in EIP8198]
    return compute_slot_start_time_ms(state.genesis_time, slot)
```

### New `compute_slot_at_time_ms`

```python
def compute_slot_at_time_ms(genesis_time: Uint64, time_ms: Uint64) -> Slot:
    """
    Return the slot corresponding to absolute Unix time ``time_ms``.
    """
    assert time_ms >= genesis_time * 1000
    time_since_genesis_ms = time_ms - genesis_time * 1000
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return Slot(GENESIS_SLOT + time_since_genesis_ms // SLOT_DURATION_MS)
    fork_slot = EIP8198_FORK_EPOCH * SLOTS_PER_EPOCH
    time_before_fork_ms = fork_slot * SLOT_DURATION_MS
    if time_since_genesis_ms < time_before_fork_ms:
        return Slot(GENESIS_SLOT + time_since_genesis_ms // SLOT_DURATION_MS)
    return Slot(
        fork_slot + (time_since_genesis_ms - time_before_fork_ms) // SLOT_DURATION_MS_EIP8198
    )
```

### New `compute_slot_range_duration_ms`

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

### Modified `compute_time_at_slot`

*Note*: Slots after `EIP8198_FORK_EPOCH` start at `SLOT_DURATION_MS_EIP8198`
intervals from the fork time, not at `SLOT_DURATION_MS` intervals from genesis.
Without this override, the execution payload timestamp — validated in
`process_execution_payload` against `compute_time_at_slot` — would drift ahead
of wall-clock time by `(SLOT_DURATION_MS - SLOT_DURATION_MS_EIP8198)` per slot,
without bound. The inherited `process_execution_payload` and validator block
preparation are correct as-is once this function accounts for the duration
change.

```python
def compute_time_at_slot(state: BeaconState, slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    return compute_time_at_slot_ms(state, slot) // 1000
```

### Modified `get_blob_parameters`

*Note*: The synthetic EIP-8198 entry below is executable-equivalent to appending
the entry required by EIP-8198 to `BLOB_SCHEDULE`. A later explicit blob
schedule entry takes precedence.

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

### Modified `get_base_reward_per_increment`

*Note*: The function `get_base_reward_per_increment` is modified to use the
EIP-8198 base reward factor.

```python
def get_base_reward_per_increment(state: BeaconState) -> Gwei:
    return Gwei(
        EFFECTIVE_BALANCE_INCREMENT
        # [Modified in EIP8198]
        * BASE_REWARD_FACTOR_EIP8198
        // integer_squareroot(get_total_active_balance(state))
    )
```

### Modified `get_inactivity_penalty_deltas`

*Note*: The function `get_inactivity_penalty_deltas` is modified to use the
EIP-8198 inactivity penalty quotient. This pre-scaled divisor avoids introducing
larger arithmetic intermediates in client implementations.

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
            penalty_denominator = INACTIVITY_SCORE_BIAS * INACTIVITY_PENALTY_QUOTIENT_EIP8198
            penalties[index] += Gwei(penalty_numerator // penalty_denominator)
    return rewards, penalties
```

### Modified `get_activation_churn_limit`

*Note*: The function is modified to use the EIP-8198 churn parameters.

```python
def get_activation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit for activations. The uncapped dynamic churn is
    rounded to ``EFFECTIVE_BALANCE_INCREMENT`` before applying the exact
    configured cap.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA_EIP8198,
        get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT_EIP8198,
    )
    # [Modified in EIP8198]
    churn = churn - churn % EFFECTIVE_BALANCE_INCREMENT
    return min(MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS_EIP8198, churn)
```

### Modified `get_exit_churn_limit`

*Note*: The function is modified to use the EIP-8198 churn parameters.

```python
def get_exit_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit for exits, rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA_EIP8198,
        get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT_EIP8198,
    )
    return Gwei(churn - churn % EFFECTIVE_BALANCE_INCREMENT)
```

### Modified `get_consolidation_churn_limit`

*Note*: The function is modified to use the EIP-8198 consolidation churn
quotient.

```python
def get_consolidation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit reserved for consolidations (EIP-7521).
    Derived from total active balance and rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    # [Modified in EIP8198]
    churn = get_total_active_balance(state) // CONSOLIDATION_CHURN_LIMIT_QUOTIENT_EIP8198
    return Gwei(churn - churn % EFFECTIVE_BALANCE_INCREMENT)
```

## Data availability

*Note*: The modified `get_blob_parameters` helper materializes the EIP-8198
schedule entry at `EIP8198_FORK_EPOCH`, scaling the preceding maximum by `2 / 3`
(`21 * 2 // 3 = 14` on mainnet). This is equivalent to appending the
EIP-8198-required entry while allowing tests and unscheduled configurations to
override only the fork epoch. Later explicit schedule entries take precedence.

*Note*: Likewise, the steady-state blob and data-column sidecar retention
windows are increased from `4096` to `6144` epochs, preserving the pre-fork
wall-clock retention period once the entire window is post-fork. The post-fork
values are configured as `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS_EIP8198` and
`MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS_EIP8198`; the networking document
defines the pre-fork retention ramp, backfill requirement, and fork-aware
selectors used by inherited request validation and retention guidance.

*Note*: The first post-fork execution payload sets its gas limit to
`parent_gas_limit * 8000 // 12000`, preserving the per-second gas throughput
target immediately rather than through gradual gas-limit voting. The execution
layer enforces the payload rule; the EIP-8198 builder and networking documents
override inherited bid construction and gossip compatibility so the consensus
layer accepts and propagates the required one-time change.
