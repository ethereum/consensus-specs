# EIP-8198 -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
- [Helpers](#helpers)
  - [Modified `compute_time_at_slot`](#modified-compute_time_at_slot)
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
`r = SLOT_DURATION_MS_EIP8198 / SLOT_DURATION_MS` (`= 10000 / 12000 = 5 / 6`) to
keep their wall-clock behavior constant.

Rather than pre-computing rounded `*_EIP8198` constants (e.g. a base reward
factor of `64 * 5 / 6 = 53.33...` rounded to `53`, a ~0.6% issuance error), this
document applies the exact ratio **inside** each formula, deferring the single
integer division to the end. `SLOT_DURATION_MS_EIP8198` is therefore the only
new parameter, and it is the single source of truth: changing the target slot
duration is a one-line config edit and every derived quantity follows exactly.

The rescaling directions are:

- **Issuance** (base reward) scales linearly with epoch duration: multiply by
  `r`.
- **Inactivity penalty** scales with the square of epoch duration, so that the
  cumulative leak over a fixed wall-clock duration is unchanged: multiply by
  `r**2`.
- **Churn** (a per-epoch rate) scales by `r`, so activation/exit/consolidation
  rates stay proportional to wall-clock time.

## Configuration

### Time parameters

| Name                       | Value           | Unit         | Duration   |
| -------------------------- | --------------- | ------------ | ---------- |
| `SLOT_DURATION_MS_EIP8198` | `Uint64(10000)` | milliseconds | 10 seconds |

## Helpers

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
    slots_since_genesis = slot - GENESIS_SLOT
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return Uint64(state.genesis_time + slots_since_genesis * SLOT_DURATION_MS // 1000)
    fork_slot = EIP8198_FORK_EPOCH * SLOTS_PER_EPOCH
    if slot < fork_slot:
        return Uint64(state.genesis_time + slots_since_genesis * SLOT_DURATION_MS // 1000)
    time_before_fork = fork_slot * SLOT_DURATION_MS // 1000
    time_after_fork = (slots_since_genesis - fork_slot) * SLOT_DURATION_MS_EIP8198 // 1000
    return Uint64(state.genesis_time + time_before_fork + time_after_fork)
```

### Modified `get_base_reward_per_increment`

*Note*: The base reward per increment is scaled by
`SLOT_DURATION_MS_EIP8198 / SLOT_DURATION_MS`. The base reward factor is left
unchanged and the integer division is deferred until after the multiplication by
`EFFECTIVE_BALANCE_INCREMENT`, which preserves the fractional effective factor
(`64 * 10000 / 12000 = 53.33...` on mainnet) instead of rounding it to a
pre-computed integer constant (`53`, a ~0.6% issuance error).

```python
def get_base_reward_per_increment(state: BeaconState) -> Gwei:
    return Gwei(
        EFFECTIVE_BALANCE_INCREMENT
        * BASE_REWARD_FACTOR
        * SLOT_DURATION_MS_EIP8198
        // SLOT_DURATION_MS
        // integer_squareroot(get_total_active_balance(state))
    )
```

### Modified `get_inactivity_penalty_deltas`

*Note*: The inactivity leak penalty is scaled by
`(SLOT_DURATION_MS_EIP8198 / SLOT_DURATION_MS)**2` so that the cumulative
penalty over a fixed wall-clock leak duration is unchanged. The ratio is applied
as two interleaved multiply-then-divide steps to avoid overflowing intermediate
values.

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
            penalty_denominator = INACTIVITY_SCORE_BIAS * INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
            base_penalty = penalty_numerator // penalty_denominator
            # [Modified in EIP8198]
            penalty = (
                base_penalty
                * SLOT_DURATION_MS_EIP8198
                // SLOT_DURATION_MS
                * SLOT_DURATION_MS_EIP8198
                // SLOT_DURATION_MS
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
    churn = churn - churn % EFFECTIVE_BALANCE_INCREMENT
    churn = min(MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS, churn)
    # [Modified in EIP8198]
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
    churn = churn - churn % EFFECTIVE_BALANCE_INCREMENT
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
    churn = churn - churn % EFFECTIVE_BALANCE_INCREMENT
    # [Modified in EIP8198]
    churn = churn * SLOT_DURATION_MS_EIP8198 // SLOT_DURATION_MS
    return Gwei(churn - churn % EFFECTIVE_BALANCE_INCREMENT)
```

## Data availability

*Note*: EIP-8198 will use the blob schedule mechanism (EIP-7892) to keep blob
throughput per unit time constant: when `EIP8198_FORK_EPOCH` is scheduled, a
`BLOB_SCHEDULE` entry for that epoch must set `MAX_BLOBS_PER_BLOCK` to the
then-current maximum scaled by `5 / 6` (e.g. `21 * 10 // 12 = 17` at today's
mainnet maximum). Because the blob count must be an integer, this scaling is
inherently approximate. No `BLOB_SCHEDULE` entry exists yet; it is added
together with the fork epoch.

*Note*: Likewise, the blob and data-column sidecar retention windows
(`MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` and
`MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS`) must be scaled by `6 / 5` —
`4096 * 12 // 10 = 4915` epochs each at today's values — to preserve the ~18-day
wall-clock retention period. The configuration files in this repository still
carry the pre-fork values; the override is scheduled together with the fork
epoch.

*Note*: At fork activation the execution layer sets the first block's gas limit
to `parent_gas_limit * 10000 // 12000`, preserving the per-second gas throughput
target immediately rather than through gradual gas-limit voting. This is an
execution-layer rule and is out of scope for this document.
