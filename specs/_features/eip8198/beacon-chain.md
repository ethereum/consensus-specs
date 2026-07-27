# EIP-8198 -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Rewards and penalties](#rewards-and-penalties)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
  - [Validator cycle](#validator-cycle)
- [Helpers](#helpers)
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
fork-choice document). This document only covers the parameters whose values
must be rescaled to preserve their wall-clock behavior with the shorter slot:
issuance, the inactivity penalty and the validator churn limits.

The ratio between the new and old slot durations is `8 / 12 = 2 / 3`. Per-epoch
quantities that should stay constant per unit of time are scaled by this ratio;
churn quotients (which divide the active balance to yield a per-epoch rate) are
scaled by its inverse `3 / 2`; and the inactivity penalty quotient is scaled by
the square of the inverse ratio `(3 / 2)**2 = 9 / 4` to keep cumulative leak
penalties constant in wall-clock terms.

## Rewards and penalties

| Name                                  | Value                              |
| ------------------------------------- | ---------------------------------- |
| `BASE_REWARD_FACTOR_EIP8198`          | `Uint64(42)`                       |
| `INACTIVITY_PENALTY_QUOTIENT_EIP8198` | `Uint64(37748736)` (= `9 * 2**22`) |

*Note*: `BASE_REWARD_FACTOR` (`= 64`) scales linearly with epoch duration to
preserve annualized issuance: `64 * 2 // 3 = 42`.
`INACTIVITY_PENALTY_QUOTIENT_BELLATRIX` (`= 2**24`) scales by the square of the
inverse ratio: `16777216 * 9 // 4 = 37748736`.

## Configuration

### Time parameters

| Name                       | Value          | Unit         | Duration  |
| -------------------------- | -------------- | ------------ | --------- |
| `SLOT_DURATION_MS_EIP8198` | `Uint64(8000)` | milliseconds | 8 seconds |

### Validator cycle

*Note*: The churn limits are rescaled so that validator activation/exit rates
and the weak-subjectivity period remain proportional to wall-clock time rather
than to slot count. The churn quotients are scaled by `3 / 2`, while the
per-epoch Gwei limits are scaled by `2 / 3`.
`CONSOLIDATION_CHURN_LIMIT_QUOTIENT` is a per-epoch rate quotient introduced
after EIP-8198 was drafted; it is scaled on the same basis to keep consolidation
churn wall-clock-invariant.

| Name                                                 | Value                |
| ---------------------------------------------------- | -------------------- |
| `CHURN_LIMIT_QUOTIENT_EIP8198`                       | `Uint64(49152)`      |
| `CONSOLIDATION_CHURN_LIMIT_QUOTIENT_EIP8198`         | `Uint64(98304)`      |
| `MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA_EIP8198`          | `Gwei(85333333333)`  |
| `MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS_EIP8198` | `Gwei(170666666666)` |

## Helpers

### Modified `get_base_reward_per_increment`

*Note*: The function `get_base_reward_per_increment` is modified to use
`BASE_REWARD_FACTOR_EIP8198`.

```python
def get_base_reward_per_increment(state: BeaconState) -> Gwei:
    return Gwei(
        EFFECTIVE_BALANCE_INCREMENT
        * BASE_REWARD_FACTOR_EIP8198
        // integer_squareroot(get_total_active_balance(state))
    )
```

### Modified `get_inactivity_penalty_deltas`

*Note*: The function `get_inactivity_penalty_deltas` is modified to use
`INACTIVITY_PENALTY_QUOTIENT_EIP8198`.

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

*Note*: The function `get_activation_churn_limit` is modified to use the
rescaled churn parameters.

```python
def get_activation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit for activations, rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA_EIP8198,
        get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT_EIP8198,
    )
    churn = churn - churn % EFFECTIVE_BALANCE_INCREMENT
    return min(MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS_EIP8198, churn)
```

### Modified `get_exit_churn_limit`

*Note*: The function `get_exit_churn_limit` is modified to use the rescaled
churn parameters.

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
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT
```

### Modified `get_consolidation_churn_limit`

*Note*: The function `get_consolidation_churn_limit` is modified to use the
rescaled `CONSOLIDATION_CHURN_LIMIT_QUOTIENT_EIP8198`.

```python
def get_consolidation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit reserved for consolidations (EIP-7521).
    Derived from total active balance and rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = get_total_active_balance(state) // CONSOLIDATION_CHURN_LIMIT_QUOTIENT_EIP8198
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT
```

## Data availability

*Note*: EIP-8198 uses the blob schedule mechanism (EIP-7892) to keep blob
throughput per unit time constant: a `BLOB_SCHEDULE` entry for
`EIP8198_FORK_EPOCH` sets `MAX_BLOBS_PER_BLOCK` to the current maximum scaled by
`2 / 3` (`21 * 2 // 3 = 14` on mainnet).

*Note*: The blob and data-column sidecar retention windows
(`MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` and
`MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS`) are scaled by `3 / 2` to `6144`
epochs each, preserving the ~18-day wall-clock retention period.

*Note*: At fork activation the execution layer sets the first block's gas limit
to `parent_gas_limit * 8000 // 12000`, preserving the per-second gas throughput
target immediately rather than through gradual gas-limit voting. This is an
execution-layer rule and is out of scope for this document.
