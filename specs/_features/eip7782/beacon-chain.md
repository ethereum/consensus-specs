# Phase 0 -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Time parameters](#time-parameters)
- [Rewards and penalties](#rewards-and-penalties)
- [Max operations per block](#max-operations-per-block)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters-1)

<!-- mdformat-toc end -->

### Time parameters

### Rewards and penalties

| Name | Value |
| ---------------------------------- | ------------------------------ |
| `BASE_REWARD_FACTOR_EIP7782` | `uint64(2**5)` (= 32) |

### Max operations per block

| Name | Value |
| ------------------------ | -------------- |
| `MAX_PROPOSER_SLASHINGS` | `2**4` (= 16) |
| `MAX_ATTESTER_SLASHINGS` | `2**1` (= 2) |
| `MAX_ATTESTATIONS` | `2**7` (= 128) |
| `MAX_DEPOSITS` | `2**4` (= 16) |
| `MAX_VOLUNTARY_EXITS` | `2**4` (= 16) |

## Configuration

### Time parameters

| Name | Value | Unit | Duration |
| ------------------------------------- | ------------------------- | :----------: | :--------: |
| `SLOT_DURATION_MS_EIP7782` | `uint64(6000)` | milliseconds | 6 seconds |
