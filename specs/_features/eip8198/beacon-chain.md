# EIP-8198 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
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

EIP-8198 ("Quick Slots") reduces the slot duration from 12 to 10 seconds. The
slot structure is inherited unchanged from Heze, and all intra-slot deadlines
are expressed in basis points of the slot duration, so they rescale
automatically (see the modified `get_slot_component_duration_ms` in the
fork-choice document).

The remaining parameters -- issuance, the inactivity penalty, and the validator
churn limits -- must be rescaled by the slot-duration ratio
`r = SLOT_DURATION_MS_EIP8198 / SLOT_DURATION_MS` to keep their wall-clock
behavior constant.

Rather than pre-computing rounded `*_EIP8198` constants, this document applies
the exact ratio **inside** each formula, deferring integer division until after
multiplication wherever possible. `SLOT_DURATION_MS_EIP8198` is therefore the
single source of truth for the target slot duration. Changing it in a network
configuration automatically updates every executable duration-dependent rule
defined by this feature; no derived protocol parameter needs a separate edit.

The rescaling directions are:

- **Issuance** (base reward) scales linearly with epoch duration: multiply by
  `r`.
- **Inactivity penalty** scales with the square of epoch duration, so that the
  cumulative leak over a fixed wall-clock duration is unchanged: multiply by
  `r**2`.
- **Churn** (a per-epoch rate) scales by `r`, so activation, exit, and
  consolidation rates stay proportional to wall-clock time.

## Configuration

### Time parameters

| Name                       | Value           | Unit         | Duration   |
| -------------------------- | --------------- | ------------ | ---------- |
| `SLOT_DURATION_MS_EIP8198` | `Uint64(10000)` | milliseconds | 10 seconds |

Both `SLOT_DURATION_MS` and `SLOT_DURATION_MS_EIP8198` MUST be positive
multiples of `1000`. Beacon block timestamps are integer Unix seconds, so this
constraint ensures that every slot boundary has an exact timestamp.
`SLOT_DURATION_MS_EIP8198` MUST be less than `SLOT_DURATION_MS`.

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

*Note*: The base reward per increment is scaled by
`SLOT_DURATION_MS_EIP8198 / SLOT_DURATION_MS`. The base reward factor is left
unchanged and the integer division is deferred until after multiplication by
`EFFECTIVE_BALANCE_INCREMENT`. This preserves the fractional effective factor
instead of rounding it to a new integer constant.

```python
def get_base_reward_per_increment(state: BeaconState) -> Gwei:
    return Gwei(
        EFFECTIVE_BALANCE_INCREMENT
        # [Modified in EIP8198]
        * BASE_REWARD_FACTOR
        * SLOT_DURATION_MS_EIP8198
        // SLOT_DURATION_MS
        // integer_squareroot(get_total_active_balance(state))
    )
```

### Modified `get_inactivity_penalty_deltas`

*Note*: The inactivity leak penalty is scaled by
`(SLOT_DURATION_MS_EIP8198 / SLOT_DURATION_MS)**2` so that the cumulative
penalty over a fixed wall-clock leak duration is unchanged. The quotient and
remainder decomposition below computes the exact rational floor while keeping
every intermediate within the inherited `Uint64` arithmetic range.

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
            slot_duration = SLOT_DURATION_MS_EIP8198 // 1000
            pre_fork_slot_duration = SLOT_DURATION_MS // 1000
            scaled_denominator = (
                INACTIVITY_SCORE_BIAS
                * INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
                * pre_fork_slot_duration
                * pre_fork_slot_duration
            )
            penalty = (
                penalty_numerator // scaled_denominator * slot_duration * slot_duration
                + penalty_numerator
                % scaled_denominator
                * slot_duration
                * slot_duration
                // scaled_denominator
            )
            penalties[index] += Gwei(penalty)
    return rewards, penalties
```

### Modified `get_activation_churn_limit`

*Note*: The per-epoch activation churn is scaled by
`SLOT_DURATION_MS_EIP8198 / SLOT_DURATION_MS` to keep the activation rate
proportional to wall-clock time, then rounded down to
`EFFECTIVE_BALANCE_INCREMENT`.

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

### Modified `get_exit_churn_limit`

*Note*: The per-epoch exit churn is scaled by
`SLOT_DURATION_MS_EIP8198 / SLOT_DURATION_MS`.

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

### Modified `get_consolidation_churn_limit`

*Note*: The per-epoch consolidation churn is scaled by
`SLOT_DURATION_MS_EIP8198 / SLOT_DURATION_MS`.

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

## Data availability

*Note*: The modified `get_blob_parameters` helper materializes the EIP-8198
schedule entry at `EIP8198_FORK_EPOCH`, scaling the preceding maximum by
`pre_fork_parameters.max_blobs_per_block * SLOT_DURATION_MS_EIP8198 // SLOT_DURATION_MS`.
This is equivalent to appending the EIP-8198-required entry while allowing tests
and unscheduled configurations to override only the fork epoch. Later explicit
schedule entries take precedence.

*Note*: Likewise, the steady-state blob and data-column sidecar retention
targets are computed as
`inherited_window * SLOT_DURATION_MS // SLOT_DURATION_MS_EIP8198`, approximately
preserving the pre-fork wall-clock retention period once the entire window is
post-fork. The networking document derives both targets and defines the pre-fork
retention ramp, backfill requirement, and fork-aware selectors used by inherited
request validation and retention guidance.

*Note*: The first post-fork execution payload sets its gas limit to
`parent_gas_limit * SLOT_DURATION_MS_EIP8198 // SLOT_DURATION_MS`, preserving
the per-second gas throughput target immediately rather than through gradual
gas-limit voting. The execution layer enforces the payload rule; the EIP-8198
builder and networking documents override inherited bid construction and gossip
compatibility so the consensus layer accepts and propagates the required
one-time change.
