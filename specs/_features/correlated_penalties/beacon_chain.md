# EIP-correlated-penalties -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Containers](#containers)
  - [Extended Containers](#extended-containers)
    - [`BeaconState`](#beaconstate)
- [Helper functions](#helper-functions)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_slot_committees`](#new-get_slot_committees)
    - [New `get_slot_committee_balance`](#new-get_slot_committee_balance)
    - [New `participating_balance_slot`](#new-participating_balance_slot)
    - [New `committee_slot_of_validator`](#new-committee_slot_of_validator)
    - [New `compute_penalty_factor`](#new-compute_penalty_factor)
    - [Modified `get_flag_index_deltas`](#modified-get_flag_index_deltas)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [New `process_net_excess_penalties`](#new-process_net_excess_penalties)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to introduce attestation correlated penalties. Refers to [EIP-9999](https://github.com/ethereum/EIPs/pull/9999).

*Note:* This specification is built upon [Electra](../../electra/beacon_chain.md) and is under active development.

## Configuration

| Name | Value |
| - | - |
| `PENALTY_ADJUSTMENT_FACTOR` | `2**12` (= 4096) |
| `MAX_PENALTY_FACTOR` | `2**2` (= 4) |
| `PENALTY_RECOVERY_RATE` | `2**0` (= 1) |

## Containers

### Extended Containers

#### `BeaconState`

```python
class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    # Eth1
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Participation
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Inactivity
    inactivity_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    # Sync
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # Execution
    latest_execution_payload_header: ExecutionPayloadHeader
    # Withdrawals
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    # Deep history valid from Capella onwards
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    deposit_receipts_start_index: uint64
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_balance_deposits: List[PendingBalanceDeposit, PENDING_BALANCE_DEPOSITS_LIMIT]
    pending_partial_withdrawals: List[PendingPartialWithdrawal, PENDING_PARTIAL_WITHDRAWALS_LIMIT]
    pending_consolidations: List[PendingConsolidation, PENDING_CONSOLIDATIONS_LIMIT]
    net_excess_penalties: Vector[uint64, TIMELY_HEAD_FLAG_INDEX]  # [New in correlated_penalties]
```

## Helper functions

### Beacon state accessors

#### New `get_slot_committees`

```python
def get_slot_committees(state: BeaconState, slot: Slot) -> Sequence[ValidatorIndex]:
    epoch = compute_epoch_at_slot(slot)
    committees_per_slot = get_committee_count_per_slot(state, epoch)
    return sum(
        (get_beacon_committee(state, slot, index)
         for index in range(committees_per_slot)),
        []
    )
```

#### New `get_slot_committee_balance`

```python
def get_slot_committee_balance(state: BeaconState, slot: Slot) -> Gwei:
    return get_total_balance(get_slot_committees(state, slot))
```

#### New `participating_balance_slot`

```python
def participating_balance_slot(state: BeaconState, slot: Slot, flag_index: int) -> Gwei:
    if compute_epoch_at_slot(slot) == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation
    participating_indexes = [
        index for index in get_slot_committees(state, slot)
        if has_flag(epoch_participation[index], flag_index)
    ]
    return get_total_balance(participating_indexes)
```

#### New `committee_slot_of_validator`

```python
def committee_slot_of_validator(state: BeaconState, index: ValidatorIndex, epoch: Epoch) -> Slot:
    committees_per_slot = get_committee_count_per_slot(state, epoch)
    for slot in range(epoch * SLOTS_PER_EPOCH, (epoch + 1) * SLOTS_PER_EPOCH):
        for committee_index in range(committees_per_slot):
            committee = get_beacon_committee(state, slot, committee_index)
            if validator_index in committee:
                return slot
```

#### New `compute_penalty_factor`

```python
def compute_penalty_factor(state: BeaconState, at_slot: Slot, flag_index: int):
    net_excess_penalties = state.net_excess_penalties[flag_index]
    for slot in range(compute_start_slot_at_epoch(compute_epoch_at_slot(at_slot)), at_slot):
        total_balance = get_slot_committee_balance(state, slot)
        participating_balance = participating_balance_slot(state, slot, flag_index)
        penalty_factor = min(
            ((total_balance - participating_balance) * PENALTY_ADJUSTMENT_FACTOR)
            // (net_excess_penalties * total_balance + 1),
            MAX_PENALTY_FACTOR
        )
        net_excess_penalties = max(PENALTY_RECOVERY_RATE, 
                                   net_excess_penalties + penalty_factor) - PENALTY_RECOVERY_RATE
    return penalty_factor, net_excess_penalties
```

#### Modified `get_flag_index_deltas`

```python
def get_flag_index_deltas(state: BeaconState, flag_index: int) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return the deltas for a given ``flag_index`` by scanning through the participation flags.
    """
    rewards = [Gwei(0)] * len(state.validators)
    penalties = [Gwei(0)] * len(state.validators)
    previous_epoch = get_previous_epoch(state)
    unslashed_participating_indices = get_unslashed_participating_indices(state, flag_index, previous_epoch)
    weight = PARTICIPATION_FLAG_WEIGHTS[flag_index]
    unslashed_participating_balance = get_total_balance(state, unslashed_participating_indices)
    unslashed_participating_increments = unslashed_participating_balance // EFFECTIVE_BALANCE_INCREMENT
    active_increments = get_total_active_balance(state) // EFFECTIVE_BALANCE_INCREMENT
    for index in get_eligible_validator_indices(state):
        base_reward = get_base_reward(state, index)
        if index in unslashed_participating_indices:
            if not is_in_inactivity_leak(state):
                reward_numerator = base_reward * weight * unslashed_participating_increments
                rewards[index] += Gwei(reward_numerator // (active_increments * WEIGHT_DENOMINATOR))
        elif flag_index != TIMELY_HEAD_FLAG_INDEX:
            # [New in correlated_penalties]
            slot = committee_slot_of_validator(state, index, previous_epoch)
            penalty_factor = compute_penalty_factor(state, slot, flag_index) 
            penalties[index] += Gwei(penalty_factor * base_reward * weight // WEIGHT_DENOMINATOR)
    return rewards, penalties
```

### Epoch processing

#### Modified `process_epoch`

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_pending_balance_deposits(state)
    process_pending_consolidations(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_net_excess_penalties(state)  # [New in correlated_penalties]
```

#### New `process_net_excess_penalties`

```python
def process_net_excess_penalties(state: BeaconState):
    for flag_index in range(len(PARTICIPATION_FLAG_WEIGHTS)):
        last_slot_prev_epoch = get_previous_epoch(state) + SLOTS_PER_EPOCH - 1
        _, net_excess_penalties = compute_penalty_factor(state, last_slot_prev_epoch, flag_index)
        net_excess_penalties[flag_index] = net_excess_penalties
```


