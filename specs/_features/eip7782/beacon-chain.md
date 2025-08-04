# Phase 0 -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Time parameters](#time-parameters)
- [Rewards and penalties](#rewards-and-penalties)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters-1)
  - [EIP-7782 timing parameters](#eip-7782-timing-parameters)
  - [EIP-7782 churn limit parameters](#eip-7782-churn-limit-parameters)
  - [Modified churn limit functions](#modified-churn-limit-functions)
    - [Modified `get_validator_churn_limit`](#modified-get_validator_churn_limit)
    - [Modified `get_validator_activation_churn_limit`](#modified-get_validator_activation_churn_limit)
    - [Modified `get_balance_churn_limit`](#modified-get_balance_churn_limit)
    - [Modified `get_activation_exit_churn_limit`](#modified-get_activation_exit_churn_limit)
- [Rewards and penalties](#rewards-and-penalties-1)
  - [Helpers](#helpers)
    - [`get_base_reward_per_increment`](#get_base_reward_per_increment)

<!-- mdformat-toc end -->

### Time parameters

### Rewards and penalties

| Name                         | Value                 |
| ---------------------------- | --------------------- |
| `BASE_REWARD_FACTOR_EIP7782` | `uint64(2**5)` (= 32) |

## Configuration

### Time parameters

| Name                       | Value          |     Unit     | Duration  |
| -------------------------- | -------------- | :----------: | :-------: |
| `SLOT_DURATION_MS_EIP7782` | `uint64(6000)` | milliseconds | 6 seconds |

### EIP-7782 timing parameters

| Name                           | Value          |     Unit     |   Duration   |
| ------------------------------ | -------------- | :----------: | :----------: |
| `ATTESTATION_DUE_BPS_EIP7782`  | `uint64(5000)` | basis points | ~50% of slot |
| `AGGREGRATE_DUE_BPS_EIP7782`   | `uint64(7500)` | basis points | ~75% of slot |
| `SYNC_MESSAGE_DUE_BPS_EIP7782` | `uint64(3333)` | basis points | ~33% of slot |
| `CONTRIBUTION_DUE_BPS_EIP7782` | `uint64(6667)` | basis points | ~67% of slot |

*Note*: EIP-7782 uses the blob schedule mechanism to reduce blob throughput. The
blob schedule entry for EIP-7782 sets `MAX_BLOBS_PER_BLOCK` to 3 (half of the
current 6 blobs) to maintain constant throughput per unit time with 6-second
slots. Transaction limits remain unchanged.

*Note*: EIP-7782 also halves the churn limits to maintain timing constants with
6-second slots. This ensures that validator activation/exit rates remain
proportional to time rather than slot count.

### EIP-7782 churn limit parameters

| Name                                                | Value                |    Unit    |               Description                |
| --------------------------------------------------- | -------------------- | :--------: | :--------------------------------------: |
| `MIN_PER_EPOCH_CHURN_LIMIT_EIP7782`                 | `uint64(2)`          | validators |  Minimum validators per epoch (halved)   |
| `MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_EIP7782`      | `uint64(4)`          | validators |  Maximum activations per epoch (halved)  |
| `MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA_EIP7782`         | `Gwei(64000000000)`  |    Gwei    |    Minimum balance per epoch (halved)    |
| `MAX_PER_EPOCH_ACTIVATION_EXIT_CHURN_LIMIT_EIP7782` | `Gwei(128000000000)` |    Gwei    | Maximum activation/exit balance (halved) |

### Modified churn limit functions

#### Modified `get_validator_churn_limit`

```python
def get_validator_churn_limit(state: BeaconState) -> uint64:
    """
    Return the validator churn limit for the current epoch.
    """
    active_validator_indices = get_active_validator_indices(state, get_current_epoch(state))
    return max(
        MIN_PER_EPOCH_CHURN_LIMIT_EIP7782,
        uint64(len(active_validator_indices)) // CHURN_LIMIT_QUOTIENT,
    )
```

#### Modified `get_validator_activation_churn_limit`

```python
def get_validator_activation_churn_limit(state: BeaconState) -> uint64:
    """
    Return the validator activation churn limit for the current epoch.
    """
    return min(MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_EIP7782, get_validator_churn_limit(state))
```

#### Modified `get_balance_churn_limit`

```python
def get_balance_churn_limit(state: BeaconState) -> Gwei:
    """
    Return the churn limit for the current epoch.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA_EIP7782,
        get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT,
    )
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT
```

#### Modified `get_activation_exit_churn_limit`

```python
def get_activation_exit_churn_limit(state: BeaconState) -> Gwei:
    """
    Return the churn limit for the current epoch dedicated to activations and exits.
    """
    return min(MAX_PER_EPOCH_ACTIVATION_EXIT_CHURN_LIMIT_EIP7782, get_balance_churn_limit(state))
```

## Rewards and penalties

### Helpers

#### `get_base_reward_per_increment`

```python
def get_base_reward_per_increment(state: BeaconState) -> Gwei:
    return Gwei(
        EFFECTIVE_BALANCE_INCREMENT
        * BASE_REWARD_FACTOR_EIP7782
        // integer_squareroot(get_total_active_balance(state))
    )
```
