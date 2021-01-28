# Ethereum 2.0 HF1

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Participation flags](#participation-flags)
  - [Participation rewards](#participation-rewards)
  - [Misc](#misc)
- [Configuration](#configuration)
  - [Misc](#misc-1)
  - [Time parameters](#time-parameters)
  - [Domain types](#domain-types)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
  - [New containers](#new-containers)
    - [`SyncCommittee`](#synccommittee)
- [Helper functions](#helper-functions)
  - [`Predicates`](#predicates)
    - [`eth2_fast_aggregate_verify`](#eth2_fast_aggregate_verify)
  - [Misc](#misc-2)
    - [`flags_and_numerators`](#flags_and_numerators)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_sync_committee_indices`](#get_sync_committee_indices)
    - [`get_sync_committee`](#get_sync_committee)
    - [`get_base_reward`](#get_base_reward)
    - [`get_unslashed_participating_indices`](#get_unslashed_participating_indices)
    - [`get_flag_deltas`](#get_flag_deltas)
    - [New `get_inactivity_penalty_deltas`](#new-get_inactivity_penalty_deltas)
  - [Block processing](#block-processing)
    - [New `process_attestation`](#new-process_attestation)
    - [New `process_deposit`](#new-process_deposit)
    - [Sync committee processing](#sync-committee-processing)
  - [Epoch processing](#epoch-processing)
    - [New `process_justification_and_finalization`](#new-process_justification_and_finalization)
    - [New `process_rewards_and_penalties`](#new-process_rewards_and_penalties)
    - [Final updates](#final-updates)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is a patch implementing the first hard fork to the beacon chain, tentatively named HF1 pending a permanent name. It has three main features:

* Light client support via sync committees
* Incentive accounting reforms, reducing spec complexity
  and [TODO] reducing the cost of processing chains that have very little or zero participation for a long span of epochs
* Fork choice rule changes to address weaknesses recently discovered in the existing fork choice

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
| `G2_POINT_AT_INFINITY` | `BLSSignature(b'\xc0' + b'\x00' * 95)` |

## Configuration

### Misc

| Name | Value |
| - | - | 
| `SYNC_COMMITTEE_SIZE` | `uint64(2**10)` (= 1024) |
| `SYNC_COMMITTEE_PUBKEY_AGGREGATES_SIZE` | `uint64(2**6)` (= 64) |
| `LEAK_SCORE_BIAS` | 4 |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `EPOCHS_PER_SYNC_COMMITTEE_PERIOD` | `Epoch(2**8)` (= 256) | epochs | ~27 hours |
| `EPOCHS_PER_ACTIVATION_EXIT_PERIOD` | `Epoch(2**5)` (= 32) | epochs | ~3.4 hours |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_SYNC_COMMITTEE` | `DomainType('0x07000000')` |

## Containers

### Extended containers

*Note*: Extended SSZ containers inherit all fields from the parent in the original
order and append any additional fields to the end.

#### `BeaconBlockBody`

```python
class BeaconBlockBody(phase0.BeaconBlockBody):
    # Sync committee aggregate signature
    sync_committee_bits: Bitvector[SYNC_COMMITTEE_SIZE]
    sync_committee_signature: BLSSignature
```

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
    # Light client sync committees
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # How many inactivity leak epochs have there been in the previous penalty period?
    leak_epoch_counter: uint64
    # Increases when the validator misses epochs in an inactivity leak, decreases when the validator
    # is online in an inactivity leak, inactivity leak penalties are proportional to this value
    leak_score: List[uint64, VALIDATOR_REGISTRY_LIMIT]
```

### New containers

#### `SyncCommittee`

```python
class SyncCommittee(Container):
    pubkeys: Vector[BLSPubkey, SYNC_COMMITTEE_SIZE]
    pubkey_aggregates: Vector[BLSPubkey, SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_PUBKEY_AGGREGATES_SIZE]
```

## Helper functions

### `Predicates`

#### `eth2_fast_aggregate_verify`

```python
def eth2_fast_aggregate_verify(pubkeys: Sequence[BLSPubkey], message: Bytes32, signature: BLSSignature) -> bool:
    """
    Wrapper to ``bls.FastAggregateVerify`` accepting the ``G2_POINT_AT_INFINITY`` signature when ``pubkeys`` is empty.
    """
    if len(pubkeys) == 0 and signature == G2_POINT_AT_INFINITY:
        return True
    return bls.FastAggregateVerify(pubkeys, message, signature)
```

### Misc

#### `flags_and_numerators`

```python
def get_flags_and_numerators() -> Sequence[Tuple[int, int]]:
    return (
        (TIMELY_HEAD_FLAG, TIMELY_HEAD_NUMERATOR),
        (TIMELY_SOURCE_FLAG, TIMELY_SOURCE_NUMERATOR),
        (TIMELY_TARGET_FLAG, TIMELY_TARGET_NUMERATOR)
    )
```



### Beacon state accessors

#### `get_sync_committee_indices`

```python
def get_sync_committee_indices(state: BeaconState, epoch: Epoch) -> Sequence[ValidatorIndex]:
    """
    Return the sync committee indices for a given state and epoch.
    """ 
    MAX_RANDOM_BYTE = 2**8 - 1
    base_epoch = Epoch((max(epoch // EPOCHS_PER_SYNC_COMMITTEE_PERIOD, 1) - 1) * EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
    active_validator_indices = get_active_validator_indices(state, base_epoch)
    active_validator_count = uint64(len(active_validator_indices))
    seed = get_seed(state, base_epoch, DOMAIN_SYNC_COMMITTEE)
    i = 0
    sync_committee_indices: List[ValidatorIndex] = []
    while len(sync_committee_indices) < SYNC_COMMITTEE_SIZE:
        shuffled_index = compute_shuffled_index(uint64(i % active_validator_count), active_validator_count, seed)
        candidate_index = active_validator_indices[shuffled_index]
        random_byte = hash(seed + uint_to_bytes(uint64(i // 32)))[i % 32]
        effective_balance = state.validators[candidate_index].effective_balance
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE * random_byte:
            sync_committee_indices.append(candidate_index)
        i += 1
    return sync_committee_indices
```

#### `get_sync_committee`

```python
def get_sync_committee(state: BeaconState, epoch: Epoch) -> SyncCommittee:
    """
    Return the sync committee for a given state and epoch.
    """
    indices = get_sync_committee_indices(state, epoch)
    validators = [state.validators[index] for index in indices]
    pubkeys = [validator.pubkey for validator in validators]
    aggregates = [
        bls.AggregatePKs(pubkeys[i:i + SYNC_COMMITTEE_PUBKEY_AGGREGATES_SIZE])
        for i in range(0, len(pubkeys), SYNC_COMMITTEE_PUBKEY_AGGREGATES_SIZE)
    ]
    return SyncCommittee(pubkeys=pubkeys, pubkey_aggregates=aggregates)
```

#### `get_base_reward`

*Note*: The function `get_base_reward` is modified with the removal of `BASE_REWARDS_PER_EPOCH`.

```python
def get_base_reward(state: BeaconState, index: ValidatorIndex) -> Gwei:
    total_balance = get_total_active_balance(state)
    effective_balance = state.validators[index].effective_balance
    return Gwei(effective_balance * BASE_REWARD_FACTOR // integer_squareroot(total_balance))
```

#### `get_unslashed_participating_indices`

```python
def get_unslashed_participating_indices(state: BeaconState, flag: uint8, epoch: Epoch) -> Set[ValidatorIndex]:
    assert epoch in (get_previous_epoch(state), get_current_epoch(state))
    if epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation
    participating_indices = [
        index for index in get_active_validator_indices(state, epoch)
        if epoch_participation[index][flag]
    ]
    return set(filter(lambda index: not state.validators[index].slashed, participating_indices))
```

#### `get_flag_rewards`

```python
def get_flag_rewards(state: BeaconState, flag: uint8, numerator: uint64) -> Sequence[Gwei]:
    """
    Computes the rewards and penalties associated with a particular duty, by scanning through the participation
    flags to determine who participated and who did not and assigning them the appropriate rewards and penalties.
    """
    rewards = [Gwei(0)] * len(state.validators)

    unslashed_participating_indices = get_unslashed_participating_indices(state, flag, get_previous_epoch(state))
    increment = EFFECTIVE_BALANCE_INCREMENT  # Factored out from balances to avoid uint64 overflow
    unslashed_participating_increments = get_total_balance(state, unslashed_participating_indices) // increment
    active_increments = get_total_active_balance(state) // increment
    for index in get_eligible_validator_indices(state):
        base_reward = get_base_reward(state, index)
        if index in unslashed_participating_indices:
            penalty_canceling_reward = base_reward * numerator // REWARD_DENOMINATOR
            extra_reward = (
                (base_reward * numerator * unslashed_participating_increments)
                // (active_increments * REWARD_DENOMINATOR)
            )
            if is_in_inactivity_leak(state):
                rewards[index] = penalty_canceling_reward
            else:
                rewards[index] = penalty_canceling_reward + extra_reward
    return rewards
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    # Light client support
    process_sync_committee(state, block.body)
```

#### New `process_attestation`

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

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    # Participation flags
    participation_flags = []
    if is_matching_head and state.slot <= data.slot + MIN_ATTESTATION_INCLUSION_DELAY:
        participation_flags.append(TIMELY_HEAD_FLAG)
    if is_matching_source and state.slot <= data.slot + integer_squareroot(SLOTS_PER_EPOCH):
        participation_flags.append(TIMELY_SOURCE_FLAG)
    if is_matching_target and state.slot <= data.slot + SLOTS_PER_EPOCH:
        participation_flags.append(TIMELY_TARGET_FLAG)

    # Update epoch participation flags
    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, data, attestation.aggregation_bits):
        for flag, numerator in get_flags_and_numerators():
            if flag in participation_flags and not epoch_participation[index][flag]:
                epoch_participation[index][flag] = True
                proposer_reward_numerator += get_base_reward(state, index) * numerator

    # Reward proposer
    proposer_reward = Gwei(proposer_reward_numerator // (REWARD_DENOMINATOR * PROPOSER_REWARD_QUOTIENT))
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
```


#### New `process_deposit`

*Note*: The function `process_deposit` is modified to initialize `previous_epoch_participation` and `current_epoch_participation`.

```python
def process_deposit(state: BeaconState, deposit: Deposit) -> None:
    # Verify the Merkle branch
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(deposit.data),
        branch=deposit.proof,
        depth=DEPOSIT_CONTRACT_TREE_DEPTH + 1,  # Add 1 for the List length mix-in
        index=state.eth1_deposit_index,
        root=state.eth1_data.deposit_root,
    )

    # Deposits must be processed in order
    state.eth1_deposit_index += 1

    pubkey = deposit.data.pubkey
    amount = deposit.data.amount
    validator_pubkeys = [v.pubkey for v in state.validators]
    if pubkey not in validator_pubkeys:
        # Verify the deposit signature (proof of possession) which is not checked by the deposit contract
        deposit_message = DepositMessage(
            pubkey=deposit.data.pubkey,
            withdrawal_credentials=deposit.data.withdrawal_credentials,
            amount=deposit.data.amount,
        )
        domain = compute_domain(DOMAIN_DEPOSIT)  # Fork-agnostic domain since deposits are valid across forks
        signing_root = compute_signing_root(deposit_message, domain)
        if not bls.Verify(pubkey, signing_root, deposit.data.signature):
            return

        # Add validator and balance entries
        state.validators.append(get_validator_from_deposit(state, deposit))
        state.balances.append(amount)
        # [Added in hf-1] Initialize empty participation flags for new validator
        state.previous_epoch_participation.append(Bitvector[PARTICIPATION_FLAGS_LENGTH]())
        state.current_epoch_participation.append(Bitvector[PARTICIPATION_FLAGS_LENGTH]())
    else:
        # Increase balance by deposit amount
        index = ValidatorIndex(validator_pubkeys.index(pubkey))
        increase_balance(state, index, amount)
```

#### Sync committee processing

```python
def process_sync_committee(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify sync committee aggregate signature signing over the previous slot block root
    previous_slot = Slot(max(int(state.slot), 1) - 1)
    committee_indices = get_sync_committee_indices(state, get_current_epoch(state))
    participant_indices = [index for index, bit in zip(committee_indices, body.sync_committee_bits) if bit]
    committee_pubkeys = state.current_sync_committee.pubkeys
    participant_pubkeys = [pubkey for pubkey, bit in zip(committee_pubkeys, body.sync_committee_bits) if bit]
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, compute_epoch_at_slot(previous_slot))
    signing_root = compute_signing_root(get_block_root_at_slot(state, previous_slot), domain)
    assert eth2_fast_aggregate_verify(participant_pubkeys, signing_root, body.sync_committee_signature)

    # Reward sync committee participants
    total_proposer_reward = Gwei(0)
    active_validator_count = uint64(len(get_active_validator_indices(state, get_current_epoch(state))))
    for participant_index in participant_indices:
        base_reward = get_base_reward(state, participant_index)
        proposer_reward = get_proposer_reward(state, participant_index)
        max_participant_reward = base_reward - proposer_reward
        reward = Gwei(max_participant_reward * active_validator_count // len(committee_indices) // SLOTS_PER_EPOCH)
        increase_balance(state, participant_index, reward)
        total_proposer_reward += proposer_reward

    # Reward beacon proposer
    increase_balance(state, get_beacon_proposer_index(state), total_proposer_reward)
```

### Epoch processing

#### New `process_justification_and_finalization`

*Note*: The function `process_justification_and_finalization` is modified with `matching_target_attestations` replaced by `matching_target_indices`.

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

#### New `process_rewards_and_penalties`

*Note*: The function `process_rewards_and_penalties` is modified to use participation flag deltas, and is broken up into the rewards and penalties-focused parts, which now work very differently.

```python
def process_rewards_and_penalties(state: BeaconState) -> None:
    process_rewards(state)
    process_penalties(state)
```

##### `process_rewards`

```
def process_rewards(state: BeaconState) -> None:
    # No rewards are applied at the end of `GENESIS_EPOCH` because rewards are for work done in the previous epoch
    if get_current_epoch(state) == GENESIS_EPOCH:
        return
    flag_rewards = [get_flag_rewards(state, flag, numerator) for (flag, numerator) in get_flags_and_numerators()]
    for rewards in flag_rewards:
        for index in range(len(state.validators)):
            increase_balance(state, ValidatorIndex(index), rewards[index])
```

##### `process_penalties`

```python
def process_penalties(state: BeaconState) -> None:    
    # A validator's leak_score updates as follows:
    # (i)  If there was an inactivity leak in a given epoch, anyone who participated in that epoch
    #      has their score decrease by 1, anyone who did not has their score increase by LEAK_SCORE_BIAS
    # (ii) If there was not an inactivity leak in a given epoch, anyone who participated in that epoch
    #      has their score decrease by 1
    # The code below implements this, though amortizing the "increase if absent" component until the end
    # of the ACTIVATION_EXIT_PERIOD
    
    if is_in_inactivity_leak(state):
        leak_score_decrease = LEAK_SCORE_BIAS + 1
        state.leak_epoch_counter += 1
    else:
        leak_score_decrease = 1
    matching_target_attesting_indices = get_unslashed_participating_indices(
        state, TIMELY_TARGET_FLAG, get_previous_epoch(state)
    )
    for index in get_eligible_validator_indices(state):
        if index in matching_target_attesting_indices:
            if state.leak_score[index] < leak_score_decrease:
                state.leak_score[index] = 0
            else:
                state.leak_score[index] -= leak_score_decrease
    # Penalty processing
    if get_current_epoch(state) % EPOCHS_PER_ACTIVATION_EXIT_PERIOD == 0:
        attestation_numerators = (TIMELY_HEAD_NUMERATOR, TIMELY_SOURCE_NUMERATOR, TIMELY_TARGET_NUMERATOR)
        for index in get_eligible_validator_indices(state):
            # "Regular" penalty
            penalty_per_epoch = get_base_reward(state, index) * sum(attestation_numerators) // REWARD_DENOMINATOR
            decrease_balance(state, ValidatorIndex(index), penalty_per_epoch * EPOCHS_PER_ACTIVATION_EXIT_PERIOD)
            # Inactivity-leak-specific penalty
            if state.leak_score[index] >= EPOCHS_PER_ACTIVATION_EXIT_PERIOD * LEAK_SCORE_BIAS
                # Goal: an offline validator loses (~n^2/2) / INACTIVITY_PENALTY_QUOTIENT after n leak *epochs*
                # `leak_score` roughly represents n * LEAK_SCORE_BIAS
                # In the *period* containing the n'th epoch, we hence leak leak_score * leak_epochs_in_period // LEAK_SCORE_BIAS.
                # This corresponds to leaking leak_score / LEAK_SCORE_BIAS, or n, per epoch.
                # sum[1...n] n ~= n^2/2, as desired
                leak_penalty = state.leak_score[index] * state.leak_epoch_counter // LEAK_SCORE_BIAS // INACTIVITY_PENALTY_QUOTIENT
                decrease_balance(state, ValidatorIndex(index), leak_penalty)
            state.leak_score[index] += LEAK_SCORE_BIAS * state.leak_epoch_counter
        state.leak_epoch_counter = 0
```

#### New `compute_activation_exit_epoch`

```python
def compute_activation_exit_epoch(epoch: Epoch) -> Epoch:
    """
    Return the epoch during which validator activations and exits initiated in ``epoch`` take effect.
    """
    next_period_start = epoch - (epoch % EPOCHS_PER_ACTIVATION_EXIT_PERIOD) + EPOCHS_PER_ACTIVATION_EXIT_PERIOD
    if next_period_start >= epoch + 1 + MAX_SEED_LOOKAHEAD:
        return Epoch(next_period_start)
    else:
        return Epoch(next_period_start + EPOCHS_PER_ACTIVATION_EXIT_PERIOD)
```

#### New `process_registry_updates`

```python
def process_registry_updates(state: BeaconState) -> None:
    if get_current_epoch(state) % EPOCHS_PER_ACTIVATION_EXIT_PERIOD == 0:
        # Process activation eligibility and ejections
        for index, validator in enumerate(state.validators):
            if is_eligible_for_activation_queue(validator):
                validator.activation_eligibility_epoch = get_current_epoch(state) + EPOCHS_PER_ACTIVATION_EXIT_PERIOD

            if is_active_validator(validator, get_current_epoch(state)) and validator.effective_balance <= EJECTION_BALANCE:
                initiate_validator_exit(state, ValidatorIndex(index))
 
        # Queue validators eligible for activation and not yet dequeued for activation
        activation_queue = sorted([
            index for index, validator in enumerate(state.validators)
            if is_eligible_for_activation(state, validator)
            # Order by the sequence of activation_eligibility_epoch setting and then index
        ], key=lambda index: (state.validators[index].activation_eligibility_epoch, index))
        # Dequeued validators for activation up to churn limit
        for index in activation_queue[:get_validator_churn_limit(state) * EPOCHS_PER_ACTIVATION_EXIT_PERIOD]:
            validator = state.validators[index]
            validator.activation_epoch = compute_activation_exit_epoch(get_current_epoch(state))
```

#### New `initiate_validator_exit`

```python
def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the exit of the validator with index ``index``.
    """
    # Return if validator already initiated exit
    validator = state.validators[index]
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Compute exit queue epoch
    exit_epochs = [v.exit_epoch for v in state.validators if v.exit_epoch != FAR_FUTURE_EPOCH]
    exit_queue_epoch = max(exit_epochs + [compute_activation_exit_epoch(get_current_epoch(state))])
    exit_queue_churn = len([v for v in state.validators if v.exit_epoch == exit_queue_epoch])
    if exit_queue_churn >= get_validator_churn_limit(state) * EPOCHS_PER_ACTIVATION_EXIT_PERIOD:
        exit_queue_epoch += Epoch(EPOCHS_PER_ACTIVATION_EXIT_PERIOD)

    # Set validator exit epoch and withdrawable epoch
    validator.exit_epoch = exit_queue_epoch
    validator.withdrawable_epoch = Epoch(validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY)
```


#### Final updates

*Note*: The function `process_final_updates` is modified to handle sync committee updates and with the replacement of `PendingAttestation`s with participation flags.

```python
def process_final_updates(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    next_epoch = Epoch(current_epoch + 1)
    # Reset eth1 data votes
    if next_epoch % EPOCHS_PER_ETH1_VOTING_PERIOD == 0:
        state.eth1_data_votes = []
    # [Added in hf-1] Update sync committees    
    if next_epoch % EPOCHS_PER_SYNC_COMMITTEE_PERIOD == 0:
        state.current_sync_committee = state.next_sync_committee
        state.next_sync_committee = get_sync_committee(state, next_epoch + EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
    # Update effective balances with hysteresis
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        HYSTERESIS_INCREMENT = uint64(EFFECTIVE_BALANCE_INCREMENT // HYSTERESIS_QUOTIENT)
        DOWNWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_DOWNWARD_MULTIPLIER
        UPWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_UPWARD_MULTIPLIER
        if (
            balance + DOWNWARD_THRESHOLD < validator.effective_balance
            or validator.effective_balance + UPWARD_THRESHOLD < balance
        ):
            validator.effective_balance = min(balance - balance % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
    # Reset slashings
    state.slashings[next_epoch % EPOCHS_PER_SLASHINGS_VECTOR] = Gwei(0)
    # Set randao mix
    state.randao_mixes[next_epoch % EPOCHS_PER_HISTORICAL_VECTOR] = get_randao_mix(state, current_epoch)
    # Set historical root accumulator
    if next_epoch % (SLOTS_PER_HISTORICAL_ROOT // SLOTS_PER_EPOCH) == 0:
        historical_batch = HistoricalBatch(block_roots=state.block_roots, state_roots=state.state_roots)
        state.historical_roots.append(hash_tree_root(historical_batch))
    # [Added in hf-1] Rotate current/previous epoch participation flags
    state.previous_epoch_participation = state.current_epoch_participation
    state.current_epoch_participation = [Bitvector[PARTICIPATION_FLAGS_LENGTH]() for _ in range(len(state.validators))]
    # [Removed in hf-1] Rotate current/previous epoch attestations
```
