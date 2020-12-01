# Incentive accounting  reforms

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Constants](#constants)
  - [Flags](#flags)
- [Containers](#containers)
  - [Modified containers](#extended-containers)
    - [`BeaconState`](#beaconstate)
- [Helper functions](#helper-functions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is a proposed reform to the eth2 spec that significantly simplifies incentive accounting, removing PendingAttestations.

## Constants

### Rewards

| Constant | Value |
| - | - |
| `TARGET_NUMERATOR` | 32 |
| `TIMELY_NUMERATOR` | 12 |
| `HEAD_AND_VERY_TIMELY_NUMERATOR` | 12 |
| `REWARD_DENOMINATOR` | 64 |

The numerators add up to 7/8, leaving the remaining 1/8 for proposer rewards and other micro rewards to be added in the future.

### Flags

| Flag | Value |
| - | - |
| `FLAG_TARGET` | 0 |
| `FLAG_TIMELY` | 1 |
| `FLAG_HEAD_AND_VERY_TIMELY` | 2 |

### Convenience structure for flags and numerators

| Name | Value |
| - | - |
| `FLAGS_AND_NUMERATORS` | `((FLAG_TARGET, TARGET_NUMERATOR), (FLAG_TIMELY, TIMELY_NUMERATOR), (FLAG_HEAD_AND_VERY_TIMELY, HEAD_AND_VERY_TIMELY_NUMERATOR))` |

## Containers

### Modified containers

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
    # Current and previous epoch participation flags
    previous_epoch_flags: List[Bitvector[8], VALIDATOR_REGISTRY_LIMIT]
    current_epoch_flags: List[Bitvector[8], VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
```

###  Helpers

##### `get_base_reward`

```python
def get_base_reward(state: BeaconState, index: ValidatorIndex) -> Gwei:
    total_balance = get_total_active_balance(state)
    effective_balance = state.validators[index].effective_balance
    return Gwei(effective_balance * BASE_REWARD_FACTOR // integer_squareroot(total_balance))
```

Note: remove the `// BASE_REWARDS_PER_EPOCH`

##### `process_attestation`

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot <= data.slot + SLOTS_PER_EPOCH
    assert data.index < get_committee_count_per_slot(state, data.target.epoch)

    committee = get_beacon_committee(state, data.slot, data.index)
    assert len(attestation.aggregation_bits) == len(committee)
        
    if data.target.epoch == get_current_epoch(state):
        flags = state.current_epoch_flags
        assert data.source == state.current_justified_checkpoint
    else:
        flags = state.previous_epoch_flags
        assert data.source == state.previous_justified_checkpoint    

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))
        
    # Process flags
    flags_to_set = []
    if data.target.root == get_block_root(state, data.target.epoch):
        flags_to_set.append(FLAG_TARGET)

        is_correct_head = data.beacon_block_root == get_block_root_at_slot(state, data.slot)
        is_very_timely = state.slot == data.slot + MIN_ATTESTATION_INCLUSION_DELAY
        if is_correct_head and is_very_timely:
            flags_to_set.append(FLAG_HEAD_AND_VERY_TIMELY)

    if state.slot <= data.slot + integer_squareroot(SLOTS_PER_EPOCH):
        flags_to_set.append(FLAG_TIMELY)

    # Update participation flags
    for participant in get_attesting_indices(state, data, attestation.aggregation_bits):
        active_position = get_active_validator_indices(state, data.target.epoch).index(participant)
        for flag, numerator in FLAGS_AND_NUMERATORS:
            if flag in flags_to_set and not flags[active_position][flag]:
                flags[active_position][flag] = True
                # Give proposer reward for new flags
                proposer_reward = Gwei(
                    get_base_reward(state, participant) * numerator
                    // (REWARD_DENOMINATOR * PROPOSER_REWARD_DENOMINATOR)
                )
                increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
```

##### `get_unslashed_participant_indices`

```python
def get_unslashed_participant_indices(state: BeaconState, flag: uint8, epoch: Epoch) -> Set[ValidatorIndex]:
    assert epoch in [get_current_epoch(state), get_previous_epoch(state)]

    flags = state.current_epoch_reward_flags if epoch == get_current_epoch(state) else state.previous_epoch_reward_flags
    participant_indices = [
        index for i, index in enumerate(get_active_validator_indices(state, epoch))
        if flags[i][flag]
    ]
    return set(filter(lambda index: not state.validators[index].slashed, participant_indices))
```

##### `process_justification_and_finalization`

```python
def process_justification_and_finalization(state: BeaconState) -> None:
    # Initial FFG checkpoint values have a `0x00` stub for `root`.
    # Skip FFG updates in the first two epochs to avoid corner cases that might result in modifying this stub.
    if get_current_epoch(state) <= GENESIS_EPOCH + 1:
        return

    previous_epoch = get_previous_epoch(state)
    current_epoch = get_current_epoch(state)
    old_previous_justified_checkpoint = state.previous_justified_checkpoint
    old_current_justified_checkpoint = state.current_justified_checkpoint

    # Process justifications
    state.previous_justified_checkpoint = state.current_justified_checkpoint
    state.justification_bits[1:] = state.justification_bits[:JUSTIFICATION_BITS_LENGTH - 1]
    state.justification_bits[0] = 0b0
    matching_target_participants = get_unslashed_participant_indices(state, FLAG_TARGET, get_previous_epoch(state))
    if get_total_balance(state, matching_target_participants) * 3 >= get_total_active_balance(state) * 2:
        state.current_justified_checkpoint = Checkpoint(epoch=previous_epoch,
                                                        root=get_block_root(state, previous_epoch))
        state.justification_bits[1] = 0b1
    matching_target_participants = get_unslashed_participant_indices(state, FLAG_TARGET, get_current_epoch(state))
    if get_total_balance(state, matching_target_participants) * 3 >= get_total_active_balance(state) * 2:
        state.current_justified_checkpoint = Checkpoint(epoch=current_epoch,
                                                        root=get_block_root(state, current_epoch))
        state.justification_bits[0] = 0b1

    # Process finalizations
    bits = state.justification_bits
    # The 2nd/3rd/4th most recent epochs are justified, the 2nd using the 4th as source
    if all(bits[1:4]) and old_previous_justified_checkpoint.epoch + 3 == current_epoch:
        state.finalized_checkpoint = old_previous_justified_checkpoint
    # The 2nd/3rd most recent epochs are justified, the 2nd using the 3rd as source
    if all(bits[1:3]) and old_previous_justified_checkpoint.epoch + 2 == current_epoch:
        state.finalized_checkpoint = old_previous_justified_checkpoint
    # The 1st/2nd/3rd most recent epochs are justified, the 1st using the 3rd as source
    if all(bits[0:3]) and old_current_justified_checkpoint.epoch + 2 == current_epoch:
        state.finalized_checkpoint = old_current_justified_checkpoint
    # The 1st/2nd most recent epochs are justified, the 1st using the 2nd as source
    if all(bits[0:2]) and old_current_justified_checkpoint.epoch + 1 == current_epoch:
        state.finalized_checkpoint = old_current_justified_checkpoint
```

##### `get_standard_flag_deltas`

```python
def get_standard_flag_deltas(state: BeaconState,
                             flag: uint8,
                             numerator: uint64) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    rewards = [Gwei(0)] * len(state.validators)
    penalties = [Gwei(0)] * len(state.validators)
    unslashed_participant_indices = get_unslashed_participant_indices(state, flag, get_previous_epoch(state))

    increment = EFFECTIVE_BALANCE_INCREMENT  # Factored out from balance totals to avoid uint64 overflow
    total_participating_balance = get_total_balance(state, unslashed_participant_indices) // increment
    total_balance = get_total_active_balance(state) // increment
    for index in get_eligible_validator_indices(state):
        if index in unslashed_participant_indices:
            if is_in_inactivity_leak(state):
                # Since full base reward will be canceled out by inactivity penalty deltas,
                # optimal participation receives full base reward compensation here.
                rewards[index] += get_base_reward(state, index) // denominator
            else:
                rewards[index] += (
                    (get_base_reward(state, index) * total_participating_balance // total_balance)
                    * numerator // REWARD_DENOMINATOR
                )
        else:
            penalties[index] += get_base_reward(state, index) * numerator // REWARD_DENOMINATOR
    return rewards, penalties
```

##### `get_inactivity_penalty_deltas`

```python
def get_inactivity_penalty_deltas(state: BeaconState) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return inactivity reward/penalty deltas for each validator.
    Note: function exactly the same as Phase 0 other than the selection of `matching_target_attesting_indices`
    """
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    
    total_usual_reward_numerator = sum([numerator for (flag, numerator) in FLAGS_AND_NUMERATORS])

    if is_in_inactivity_leak(state):
        previous_epoch = get_previous_epoch(state)
        matching_target_attesting_indices = get_unslashed_participant_indices(state, FLAG_TARGET, previous_epoch)
        for index in get_eligible_validator_indices(state):
            # If validator is performing optimally this cancels all attestation rewards for a neutral balance
            penalties[index] += Gwei(get_base_reward(state, index) * total_usual_reward_numerator // INACTIVITY_PENALTY_QUOTIENT))
            if index not in matching_target_attesting_indices:
                effective_balance = state.validators[index].effective_balance
                penalties[index] += Gwei(effective_balance * get_finality_delay(state) // INACTIVITY_PENALTY_QUOTIENT)

    # No rewards associated with inactivity penalties
    rewards = [Gwei(0) for _ in range(len(state.validators))]
    return rewards, penalties
```

##### `process_rewards_and_penalties`

```python
def process_rewards_and_penalties(state: BeaconState) -> None:
    # No rewards are applied at the end of `GENESIS_EPOCH` because rewards are for work done in the previous epoch
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    flag_deltas = [
        get_standard_flag_deltas(state, flag, numerator) for (flag, numerator) in FLAGS_AND_NUMERATORS
    ]
    deltas = flag_deltas + [get_inactivity_penalty_deltas]
    for (rewards, penalties) in deltas:
        for index in range(len(state.validators)):
            increase_balance(state, ValidatorIndex(index), rewards[index])
            decrease_balance(state, ValidatorIndex(index), penalties[index])
```
