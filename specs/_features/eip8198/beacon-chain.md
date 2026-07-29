# EIP-8198 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Slot duration schedule](#slot-duration-schedule)
- [Helpers](#helpers)
  - [Misc](#misc)
    - [New `get_slot_duration_ms`](#new-get_slot_duration_ms)
    - [New `compute_slot_start_time_ms`](#new-compute_slot_start_time_ms)
    - [New `compute_slot_at_time_ms`](#new-compute_slot_at_time_ms)
    - [New `compute_slot_range_duration_ms`](#new-compute_slot_range_duration_ms)
    - [Modified `compute_time_at_slot`](#modified-compute_time_at_slot)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_base_reward_per_increment`](#modified-get_base_reward_per_increment)
    - [Modified `get_inactivity_penalty_deltas`](#modified-get_inactivity_penalty_deltas)
    - [Modified `get_activation_churn_limit`](#modified-get_activation_churn_limit)
    - [Modified `get_exit_churn_limit`](#modified-get_exit_churn_limit)
    - [Modified `get_consolidation_churn_limit`](#modified-get_consolidation_churn_limit)

<!-- mdformat-toc end -->

## Introduction

EIP-8198 ("Quick Slots") makes the slot duration schedulable, with a first
reduction from 12 to 10 seconds intended at the fork epoch. The slot structure
is unchanged, and all intra-slot deadlines are expressed in basis points of the
slot duration, so they rescale automatically. The remaining duration-dependent
parameters are rescaled by the ratio
`r = get_slot_duration_ms(epoch) / SLOT_DURATION_MS` to keep their wall-clock
behavior constant: issuance and churn are per-epoch rates and scale by `r`,
while the inactivity penalty scales by `r**2` so that the cumulative leak over a
fixed wall-clock duration is unchanged. Rather than pre-computing rounded
constants, each formula applies the ratio inline, keeping the slot duration
schedule the single source of truth for the slot duration. Epoch- and
slot-denominated quantities — withdrawability and slashing windows, sync
committee periods, per-payload and per-epoch processing limits — keep their
counts, so their wall-clock spans scale with the slot duration.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Configuration

### Slot duration schedule

*[New in EIP8198]* This schedule defines the slot duration for a given epoch.
Epochs before the first entry use `SLOT_DURATION_MS`.

There MUST NOT exist multiple slot duration schedule entries with the same epoch
value. The epoch value in each entry MUST be greater than or equal to
`EIP8198_FORK_EPOCH`; an entry with an epoch of `FAR_FUTURE_EPOCH` is not
scheduled and has no effect. The slot duration in each entry MUST be a positive
multiple of `1000`, so that every slot boundary has an exact integer-second
timestamp. The slot duration schedule entries SHOULD be sorted by epoch in
ascending order. The slot duration schedule MAY be empty. Once scheduled, an
entry that changes the slot duration MUST be accompanied by a `BLOB_SCHEDULE`
entry at the same epoch that scales the maximum blobs per block by the
slot-duration ratio (rounding down), keeping blob throughput per unit time
constant.

The epoch of the mainnet entry below is **TBD** and is intended to be the fork
epoch.

<!-- list-of-records:slot_duration_schedule -->

|                Epoch | Slot Duration Ms | Description |
| -------------------: | ---------------: | ----------- |
| 18446744073709551615 |            10000 | 10 seconds  |

## Helpers

### Misc

#### New `get_slot_duration_ms`

```python
def get_slot_duration_ms(epoch: Epoch) -> Uint64:
    """
    Return the slot duration in effect at ``epoch``, per
    ``SLOT_DURATION_SCHEDULE``. Epochs before the first schedule entry use
    ``SLOT_DURATION_MS``.
    """
    duration_ms = SLOT_DURATION_MS
    for entry in sorted(SLOT_DURATION_SCHEDULE, key=lambda entry: entry["EPOCH"]):
        if entry["EPOCH"] == FAR_FUTURE_EPOCH or epoch < entry["EPOCH"]:
            break
        duration_ms = entry["SLOT_DURATION_MS"]
    return duration_ms
```

#### New `compute_slot_start_time_ms`

```python
def compute_slot_start_time_ms(genesis_time: Uint64, slot: Slot) -> Uint64:
    """
    Return the absolute Unix time in milliseconds at the start of ``slot``,
    accumulating the eras of ``SLOT_DURATION_SCHEDULE``.
    """
    time_ms = genesis_time * 1000
    era_start_slot = GENESIS_SLOT
    era_duration_ms = SLOT_DURATION_MS
    for entry in sorted(SLOT_DURATION_SCHEDULE, key=lambda entry: entry["EPOCH"]):
        if entry["EPOCH"] == FAR_FUTURE_EPOCH:
            break
        entry_slot = compute_start_slot_at_epoch(entry["EPOCH"])
        if slot < entry_slot:
            break
        time_ms += (entry_slot - era_start_slot) * era_duration_ms
        era_start_slot = entry_slot
        era_duration_ms = entry["SLOT_DURATION_MS"]
    return Uint64(time_ms + (slot - era_start_slot) * era_duration_ms)
```

#### New `compute_slot_at_time_ms`

```python
def compute_slot_at_time_ms(genesis_time: Uint64, time_ms: Uint64) -> Slot:
    """
    Return the slot corresponding to absolute Unix time ``time_ms``. Inverse
    of ``compute_slot_start_time_ms``.
    """
    assert time_ms >= genesis_time * 1000
    remaining_ms = time_ms - genesis_time * 1000
    era_start_slot = GENESIS_SLOT
    era_duration_ms = SLOT_DURATION_MS
    for entry in sorted(SLOT_DURATION_SCHEDULE, key=lambda entry: entry["EPOCH"]):
        if entry["EPOCH"] == FAR_FUTURE_EPOCH:
            break
        entry_slot = compute_start_slot_at_epoch(entry["EPOCH"])
        era_length_ms = (entry_slot - era_start_slot) * era_duration_ms
        if remaining_ms < era_length_ms:
            break
        remaining_ms -= era_length_ms
        era_start_slot = entry_slot
        era_duration_ms = entry["SLOT_DURATION_MS"]
    return Slot(era_start_slot + remaining_ms // era_duration_ms)
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
`compute_time_at_slot` in `process_execution_payload`, would drift away from
wall-clock time without bound after a slot duration change.

```python
def compute_time_at_slot(state: BeaconState, slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    return compute_slot_start_time_ms(state.genesis_time, slot) // 1000
```

### Beacon state accessors

#### Modified `get_base_reward_per_increment`

*Note*: The division is deferred so that the exact
`get_slot_duration_ms(epoch) / SLOT_DURATION_MS` ratio applies, rather than
rounding `BASE_REWARD_FACTOR` to a new integer constant.

```python
def get_base_reward_per_increment(state: BeaconState) -> Gwei:
    return Gwei(
        EFFECTIVE_BALANCE_INCREMENT
        * BASE_REWARD_FACTOR
        # [Modified in EIP8198]
        * get_slot_duration_ms(get_current_epoch(state))
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
            slot_duration_ms = get_slot_duration_ms(get_current_epoch(state))
            penalty_denominator = (
                INACTIVITY_SCORE_BIAS
                * INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
                * SLOT_DURATION_MS
                * SLOT_DURATION_MS
                // (slot_duration_ms * slot_duration_ms)
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
    churn = churn * get_slot_duration_ms(get_current_epoch(state)) // SLOT_DURATION_MS
    return Gwei(churn - churn % EFFECTIVE_BALANCE_INCREMENT)
```

#### Modified `get_exit_churn_limit`

*Note*: Exit and consolidation epochs assigned before a duration change keep
their assigned epochs and consumed quota, so around a change the inherited queue
allocation transiently deviates from the new per-epoch rate by at most the
backlog queued at the change.

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
    churn = churn * get_slot_duration_ms(get_current_epoch(state)) // SLOT_DURATION_MS
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
    churn = churn * get_slot_duration_ms(get_current_epoch(state)) // SLOT_DURATION_MS
    return Gwei(churn - churn % EFFECTIVE_BALANCE_INCREMENT)
```
