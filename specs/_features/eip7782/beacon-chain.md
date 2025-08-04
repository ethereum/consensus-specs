# Phase 0 -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Time parameters](#time-parameters)
- [Rewards and penalties](#rewards-and-penalties)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters-1)

<!-- mdformat-toc end -->

### Time parameters

### Rewards and penalties

| Name | Value |
| ---------------------------------- | ------------------------------ |
| `BASE_REWARD_FACTOR_EIP7782` | `uint64(2**5)` (= 32) |

## Configuration

### Time parameters

| Name | Value | Unit | Duration |
| ------------------------------------- | ------------------------- | :----------: | :--------: |
| `SLOT_DURATION_MS_EIP7782` | `uint64(6000)` | milliseconds | 6 seconds |

### EIP-7782 timing parameters

| Name | Value | Unit | Duration |
| ------------------------------------- | ------------------------- | :----------: | :--------: |
| `ATTESTATION_DUE_BPS_EIP7782` | `uint64(5000)` | basis points | ~50% of slot |
| `AGGREGRATE_DUE_BPS_EIP7782` | `uint64(7500)` | basis points | ~75% of slot |
| `SYNC_MESSAGE_DUE_BPS_EIP7782` | `uint64(3333)` | basis points | ~33% of slot |
| `CONTRIBUTION_DUE_BPS_EIP7782` | `uint64(6667)` | basis points | ~67% of slot |

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
