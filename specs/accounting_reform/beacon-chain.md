# Incentive accounting  reforms

## Table of contents

**TODO**: Generate table of contents with doctoc.

## Introduction

This is a proposed incentive accounting simplification which replaces `PendingAttestation` with epoch participation flags.

## Constants

### Participation flags

| Name | Value |
| - | - |
| `TIMELY_HEAD_FLAG` | `0` |
| `TIMELY_SOURCE_FLAG` | `1` |
| `TIMELY_TARGET_FLAG` | `2` |

### Participation rewards

| Name | Value |
| - | - |
| `TIMELY_HEAD_NUMERATOR` | `12` |
| `TIMELY_SOURCE_NUMERATOR` | `12` |
| `TIMELY_TARGET_NUMERATOR` | `32` |
| `REWARD_DENOMINATOR` | `64` |

The reward fractions add up to 7/8, leaving the remaining 1/8 for proposer rewards and other future micro-rewards.

### Misc

| Name | Value |
| - | - |
| `PARTICIPATION_FLAGS_LENGTH` | `8` |
| `FLAGS_AND_NUMERATORS` | `((TIMELY_HEAD_FLAG, TIMELY_HEAD_NUMERATOR)), (TIMELY_TARGET_FLAG, TIMELY_TARGET_NUMERATOR), (TIMELY_SOURCE_FLAG, TIMELY_SOURCE_NUMERATOR)` |

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
    # Participation
    previous_epoch_participation: List[Bitvector[PARTICIPATION_FLAGS_LENGTH], VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[Bitvector[PARTICIPATION_FLAGS_LENGTH], VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
```

###  Helpers

##### `get_base_reward`

*Note*: The function `get_base_reward` is modified with the removal of `BASE_REWARDS_PER_EPOCH`.

```python
def get_base_reward(state: BeaconState, index: ValidatorIndex) -> Gwei:
    total_balance = get_total_active_balance(state)
    effective_balance = state.validators[index].effective_balance
    return Gwei(effective_balance * BASE_REWARD_FACTOR // integer_squareroot(total_balance))
```

##### `process_attestation`

*Note*: The function `process_attestation` is modified to do incentive accounting with epoch participation flags.

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
        epoch_participation = state.current_epoch_participation
        justified_checkpoint = state.current_justified_checkpoint
    else:
        epoch_participation = state.previous_epoch_participation
        justified_checkpoint = state.previous_justified_checkpoint

    # Matching roots
    is_matching_head = data.beacon_block_root == get_block_root_at_slot(state, data.slot)
    is_matching_source = data.source == justified_checkpoint
    is_matching_target = data.target.root == get_block_root(state, data.target.epoch)
    assert is_matching_source

    # Participation flags
    participation_flags = []
    if is_matching_head and state.slot <= data.slot + MIN_ATTESTATION_INCLUSION_DELAY:
        participation_flags.append(TIMELY_HEAD_FLAG)
    if is_matching_source and state.slot <= data.slot + integer_squareroot(SLOTS_PER_EPOCH):
        participation_flags.append(TIMELY_SOURCE_FLAG)
    if is_matching_target and state.slot <= data.slot + SLOTS_PER_EPOCH:
        participation_flags.append(TIMELY_TARGET_FLAG)

    # Update epoch participation
    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, data, attestation.aggregation_bits):
        for flag, numerator in FLAGS_AND_NUMERATORS:
            if flag in participation_flags and not epoch_participation[index][flag]:
                epoch_participation[index][flag] = True
                proposer_reward_numerator += get_base_reward(state, index) * numerator
    # Reward proposer
    proposer_reward = Gwei(proposer_reward_numerator // (REWARD_DENOMINATOR * PROPOSER_REWARD_QUOTIENT))
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))
```

##### `get_unslashed_participating_indices`

```python
def get_unslashed_participating_indices(state: BeaconState, flag: uint8, epoch: Epoch) -> Set[ValidatorIndex]:
    assert epoch in (get_current_epoch(state), get_previous_epoch(state))
    if epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation
    participating_indices = [index in get_active_validator_indices(state, epoch) if epoch_participation[index][flag]]
    return set(filter(lambda index: not state.validators[index].slashed, participating_indices))
```

##### `process_justification_and_finalization`

*Note*: The function `process_justification_and_finalization` is modified to replace `matching_target_attestations` with `matching_target_indices`.

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
    matching_target_indices = get_unslashed_participating_indices(state, TIMELY_TARGET_FLAG, previous_epoch)
    if get_total_balance(state, matching_target_indices) * 3 >= get_total_active_balance(state) * 2:
        state.current_justified_checkpoint = Checkpoint(epoch=previous_epoch,
                                                        root=get_block_root(state, previous_epoch))
        state.justification_bits[1] = 0b1
    matching_target_indices = get_unslashed_participating_indices(state, TIMELY_TARGET_FLAG, current_epoch)
    if get_total_balance(state, matching_target_indices) * 3 >= get_total_active_balance(state) * 2:
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

##### `get_flag_deltas`

```python
def get_flag_deltas(state: BeaconState,
                    flag: uint8,
                    numerator: uint64) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    rewards = [Gwei(0)] * len(state.validators)
    penalties = [Gwei(0)] * len(state.validators)
    unslashed_participating_indices = get_unslashed_participating_indices(state, flag, get_previous_epoch(state))

    increment = EFFECTIVE_BALANCE_INCREMENT  # Factored out from balances to avoid uint64 overflow
    unslashed_participating_increments = get_total_balance(state, unslashed_participating_indices) // increment
    active_increments = get_total_active_balance(state) // increment
    for index in get_eligible_validator_indices(state):
        base_reward = get_base_reward(state, index)
        if index in unslashed_participating_indices:
            if is_in_inactivity_leak(state):
                # Optimal participatition fully rewarded to cancel inactivity penalty
                rewards[index] = base_reward * numerator // REWARD_DENOMINATOR
            else:
                rewards[index] = base_reward * numerator * unslashed_participating_increments
                // (active_increments * REWARD_DENOMINATOR)
        else:
            penalties[index] = base_reward * numerator // REWARD_DENOMINATOR
    return rewards, penalties
```

##### `get_inactivity_penalty_deltas`

*Note*: The function `get_inactivity_penalty_deltas` is modified in the selection of matching target indices and the removal of `BASE_REWARDS_PER_EPOCH`.

```python
def get_inactivity_penalty_deltas(state: BeaconState) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return inactivity reward/penalty deltas for each validator.
    """
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    if is_in_inactivity_leak(state):
        reward_numerator_sum = sum(numerator for (_, numerator) in FLAGS_AND_NUMERATORS)
        matching_target_indices = get_unslashed_participating_indices(state, TIMELY_TARGET_FLAG, get_previous_epoch(state))
        for index in get_eligible_validator_indices(state):
            # If validator is performing optimally this cancels all attestation rewards for a neutral balance
            penalties[index] += get_base_reward(state, index) * reward_numerator_sum // REWARD_DENOMINATOR
            if index not in matching_target_indices:
                effective_balance = state.validators[index].effective_balance
                penalties[index] += Gwei(effective_balance * get_finality_delay(state) // INACTIVITY_PENALTY_QUOTIENT)

    # No rewards associated with inactivity penalties
    rewards = [Gwei(0) for _ in range(len(state.validators))]
    return rewards, penalties
```

##### `process_rewards_and_penalties`

*Note*: The function `process_rewards_and_penalties` is modified to use participation flag deltas.

```python
def process_rewards_and_penalties(state: BeaconState) -> None:
    # No rewards are applied at the end of `GENESIS_EPOCH` because rewards are for work done in the previous epoch
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    flag_deltas = [get_flag_deltas(state, flag, numerator) for (flag, numerator) in FLAGS_AND_NUMERATORS]
    deltas = flag_deltas + [get_inactivity_penalty_deltas]
    for (rewards, penalties) in deltas:
        for index in range(len(state.validators)):
            increase_balance(state, ValidatorIndex(index), rewards[index])
            decrease_balance(state, ValidatorIndex(index), penalties[index])
```
