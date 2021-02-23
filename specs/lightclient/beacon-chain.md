# Ethereum 2.0 HF1

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Validator action flags](#validator-action-flags)
  - [Participation rewards](#participation-rewards)
  - [Misc](#misc)
- [Configuration](#configuration)
  - [Updated penalty values](#updated-penalty-values)
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
  - [Beacon state mutators](#beacon-state-mutators)
    - [New `slash_validator`](#new-slash_validator)
  - [Block processing](#block-processing)
    - [New `process_attestation`](#new-process_attestation)
    - [New `process_deposit`](#new-process_deposit)
    - [Sync committee processing](#sync-committee-processing)
  - [Epoch processing](#epoch-processing)
    - [New `process_justification_and_finalization`](#new-process_justification_and_finalization)
    - [New `process_rewards_and_penalties`](#new-process_rewards_and_penalties)
    - [New `process_slashings`](#new-process_slashings)
    - [Sync committee updates](#sync-committee-updates)
    - [Participation flags updates](#participation-flags-updates)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is a patch implementing the first hard fork to the beacon chain, tentatively named HF1 pending a permanent name.
It has four main features:

* Light client support via sync committees
* Incentive accounting reforms, reducing spec complexity
  and [TODO] reducing the cost of processing chains that have very little or zero participation for a long span of epochs
* Update penalty configuration values, moving them toward their planned maximally punitive configuration
* Fork choice rule changes to address weaknesses recently discovered in the existing fork choice

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `ValidatorFlag` | `uint8` | Bitflags to track validator actions with |

## Constants

### Validator action flags

This is formatted as an enum, with values `2**i` that can be combined as bit-flags.
The `0` value is reserved as default. Remaining bits in `ValidatorFlag` may be used in future hardforks.

**Note**: Unlike Phase0, a `TIMELY_TARGET_FLAG` does not necessarily imply a `TIMELY_SOURCE_FLAG`
due to the varying slot delay requirements of each.

| Name | Value |
| - | - |
| `TIMELY_HEAD_FLAG`   | `ValidatorFlag(2**0)` (= 1) |
| `TIMELY_SOURCE_FLAG` | `ValidatorFlag(2**1)` (= 2) |
| `TIMELY_TARGET_FLAG` | `ValidatorFlag(2**2)` (= 4) |

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
| `G2_POINT_AT_INFINITY` | `BLSSignature(b'\xc0' + b'\x00' * 95)` |

## Configuration

### Updated penalty values

This patch updates a few configuration values to move penalty constants toward their final, maxmium security values.

*Note*: The spec does *not* override previous configuration values but instead creates new values and replaces usage throughout.

| Name | Value |
| - | - |
| `HF1_INACTIVITY_PENALTY_QUOTIENT` | `uint64(3 * 2**24)` (= 50,331,648) |
| `HF1_MIN_SLASHING_PENALTY_QUOTIENT` | `uint64(2**6)` (=64) |
| `HF1_PROPORTIONAL_SLASHING_MULTIPLIER` | `uint64(2)` |

### Misc

| Name | Value |
| - | - | 
| `SYNC_COMMITTEE_SIZE` | `uint64(2**10)` (= 1024) |
| `SYNC_COMMITTEE_PUBKEY_AGGREGATES_SIZE` | `uint64(2**6)` (= 64) |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `EPOCHS_PER_SYNC_COMMITTEE_PERIOD` | `Epoch(2**8)` (= 256) | epochs | ~27 hours |

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
    previous_epoch_participation: List[ValidatorFlag, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ValidatorFlag, VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Light client sync committees
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
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
def get_flags_and_numerators() -> Sequence[Tuple[ValidatorFlag, int]]:
    return (
        (TIMELY_HEAD_FLAG, TIMELY_HEAD_NUMERATOR),
        (TIMELY_SOURCE_FLAG, TIMELY_SOURCE_NUMERATOR),
        (TIMELY_TARGET_FLAG, TIMELY_TARGET_NUMERATOR)
    )
```

```python
def add_validator_flags(flags: ValidatorFlag, add: ValidatorFlag) -> ValidatorFlag:
    return flags | add
```

```python
def has_validator_flags(flags: ValidatorFlag, has: ValidatorFlag) -> bool:
    return flags & has == has
```

### Beacon state accessors

#### `get_sync_committee_indices`

```python
def get_sync_committee_indices(state: BeaconState, epoch: Epoch) -> Sequence[ValidatorIndex]:
    """
    Return the sequence of sync committee indices (which may include duplicate indices) for a given state and epoch.
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
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE * random_byte:  # Sample with replacement
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
def get_unslashed_participating_indices(state: BeaconState, flags: ValidatorFlag, epoch: Epoch) -> Set[ValidatorIndex]:
    """
    Retrieve the active validator indices of the given epoch, which are not slashed, and have all of the given flags. 
    """
    assert epoch in (get_previous_epoch(state), get_current_epoch(state))
    if epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation
    participating_indices = [
        index for index in get_active_validator_indices(state, epoch)
        if has_validator_flags(epoch_participation[index], flags)
    ]
    return set(filter(lambda index: not state.validators[index].slashed, participating_indices))
```

#### `get_flag_deltas`

```python
def get_flag_deltas(state: BeaconState,
                    flag: ValidatorFlag,
                    numerator: uint64) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Compute the rewards and penalties associated with a particular duty, by scanning through the participation
    flags to determine who participated and who did not and assigning them the appropriate rewards and penalties.
    """
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
                # Optimal participation is fully rewarded to cancel the inactivity penalty
                rewards[index] = base_reward * numerator // REWARD_DENOMINATOR
            else:
                rewards[index] = (
                    (base_reward * numerator * unslashed_participating_increments)
                    // (active_increments * REWARD_DENOMINATOR)
                )
        else:
            penalties[index] = base_reward * numerator // REWARD_DENOMINATOR
    return rewards, penalties
```

#### New `get_inactivity_penalty_deltas`

*Note*: The function `get_inactivity_penalty_deltas` is modified in the selection of matching target indices
and the removal of `BASE_REWARDS_PER_EPOCH`.

```python
def get_inactivity_penalty_deltas(state: BeaconState) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Compute the penalties associated with the inactivity leak, by scanning through the participation
    flags to determine who participated and who did not, applying the leak penalty globally and applying
    compensatory rewards to participants.
    """
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    if is_in_inactivity_leak(state):
        reward_numerator_sum = sum(numerator for (_, numerator) in get_flags_and_numerators())
        matching_target_attesting_indices = get_unslashed_participating_indices(
            state, TIMELY_TARGET_FLAG, get_previous_epoch(state)
        )
        for index in get_eligible_validator_indices(state):
            # If validator is performing optimally this cancels all attestation rewards for a neutral balance
            penalties[index] += Gwei(get_base_reward(state, index) * reward_numerator_sum // REWARD_DENOMINATOR)
            if index not in matching_target_attesting_indices: 
                effective_balance = state.validators[index].effective_balance
                penalties[index] += Gwei(
                    effective_balance * get_finality_delay(state)
                    // HF1_INACTIVITY_PENALTY_QUOTIENT
                )

    rewards = [Gwei(0) for _ in range(len(state.validators))]
    return rewards, penalties
```

### Beacon state mutators

#### New `slash_validator`

*Note*: The function `slash_validator` is modified
with the substitution of `MIN_SLASHING_PENALTY_QUOTIENT` with `HF1_MIN_SLASHING_PENALTY_QUOTIENT`.

```python
def slash_validator(state: BeaconState,
                    slashed_index: ValidatorIndex,
                    whistleblower_index: ValidatorIndex=None) -> None:
    """
    Slash the validator with index ``slashed_index``.
    """
    epoch = get_current_epoch(state)
    initiate_validator_exit(state, slashed_index)
    validator = state.validators[slashed_index]
    validator.slashed = True
    validator.withdrawable_epoch = max(validator.withdrawable_epoch, Epoch(epoch + EPOCHS_PER_SLASHINGS_VECTOR))
    state.slashings[epoch % EPOCHS_PER_SLASHINGS_VECTOR] += validator.effective_balance
    decrease_balance(state, slashed_index, validator.effective_balance // HF1_MIN_SLASHING_PENALTY_QUOTIENT)

    # Apply proposer and whistleblower rewards
    proposer_index = get_beacon_proposer_index(state)
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    whistleblower_reward = Gwei(validator.effective_balance // WHISTLEBLOWER_REWARD_QUOTIENT)
    proposer_reward = Gwei(whistleblower_reward // PROPOSER_REWARD_QUOTIENT)
    increase_balance(state, proposer_index, proposer_reward)
    increase_balance(state, whistleblower_index, Gwei(whistleblower_reward - proposer_reward))
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
    if is_matching_head and is_matching_target and state.slot <= data.slot + MIN_ATTESTATION_INCLUSION_DELAY:
        participation_flags.append(TIMELY_HEAD_FLAG)
    if is_matching_source and state.slot <= data.slot + integer_squareroot(SLOTS_PER_EPOCH):
        participation_flags.append(TIMELY_SOURCE_FLAG)
    if is_matching_target and state.slot <= data.slot + SLOTS_PER_EPOCH:
        participation_flags.append(TIMELY_TARGET_FLAG)

    # Update epoch participation flags
    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, data, attestation.aggregation_bits):
        for flag, numerator in get_flags_and_numerators():
            if flag in participation_flags and not has_validator_flags(epoch_participation[index], flag):
                epoch_participation[index] = add_validator_flags(epoch_participation[index], flag)
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
        state.previous_epoch_participation.append(ValidatorFlag(0))
        state.current_epoch_participation.append(ValidatorFlag(0))
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

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)  # [Updated in HF1]
    process_rewards_and_penalties(state)  # [Updated in HF1]
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_roots_update(state)
    # [Removed in HF1] -- process_participation_record_updates(state)
    # [Added in HF1]
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
```

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

*Note*: The function `process_rewards_and_penalties` is modified to use participation flag deltas.

```python
def process_rewards_and_penalties(state: BeaconState) -> None:
    # No rewards are applied at the end of `GENESIS_EPOCH` because rewards are for work done in the previous epoch
    if get_current_epoch(state) == GENESIS_EPOCH:
        return
    flag_deltas = [get_flag_deltas(state, flag, numerator) for (flag, numerator) in get_flags_and_numerators()]
    deltas = flag_deltas + [get_inactivity_penalty_deltas(state)]
    for (rewards, penalties) in deltas:
        for index in range(len(state.validators)):
            increase_balance(state, ValidatorIndex(index), rewards[index])
            decrease_balance(state, ValidatorIndex(index), penalties[index])
```

#### New `process_slashings`

*Note*: The function `process_slashings` is modified
with the substitution of `PROPORTIONAL_SLASHING_MULTIPLIER` with `HF1_PROPORTIONAL_SLASHING_MULTIPLIER`.

```python
def process_slashings(state: BeaconState) -> None:
    epoch = get_current_epoch(state)
    total_balance = get_total_active_balance(state)
    adjusted_total_slashing_balance = min(sum(state.slashings) * HF1_PROPORTIONAL_SLASHING_MULTIPLIER, total_balance)
    for index, validator in enumerate(state.validators):
        if validator.slashed and epoch + EPOCHS_PER_SLASHINGS_VECTOR // 2 == validator.withdrawable_epoch:
            increment = EFFECTIVE_BALANCE_INCREMENT  # Factored out from penalty numerator to avoid uint64 overflow
            penalty_numerator = validator.effective_balance // increment * adjusted_total_slashing_balance
            penalty = penalty_numerator // total_balance * increment
            decrease_balance(state, ValidatorIndex(index), penalty)
```

#### Sync committee updates

```python
def process_sync_committee_updates(state: BeaconState) -> None:
    """
    Call to ``proces_sync_committee_updates`` added to ``process_epoch`` in HF1
    """
    next_epoch = get_current_epoch(state) + Epoch(1)
    if next_epoch % EPOCHS_PER_SYNC_COMMITTEE_PERIOD == 0:
        state.current_sync_committee = state.next_sync_committee
        state.next_sync_committee = get_sync_committee(state, next_epoch + EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
```

#### Participation flags updates

```python
def process_participation_flag_updates(state: BeaconState) -> None:
    """
    Call to ``process_participation_flag_updates`` added to ``process_epoch`` in HF1
    """
    state.previous_epoch_participation = state.current_epoch_participation
    state.current_epoch_participation = [ValidatorFlag(0) for _ in range(len(state.validators))]
```
