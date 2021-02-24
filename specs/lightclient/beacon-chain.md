# Ethereum 2.0--Hard Fork 1 (HF1)

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Participation flag indices](#participation-flag-indices)
  - [Participation flag fractions](#participation-flag-fractions)
  - [Misc](#misc)
- [Configuration](#configuration)
  - [Updated penalty values](#updated-penalty-values)
  - [Misc](#misc-1)
  - [Time parameters](#time-parameters)
  - [Domain types](#domain-types)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
  - [New containers](#new-containers)
    - [`SyncCommittee`](#synccommittee)
- [Helper functions](#helper-functions)
  - [`Predicates`](#predicates)
    - [`eth2_fast_aggregate_verify`](#eth2_fast_aggregate_verify)
    - [`is_activation_exit_epoch`](#is_activation_exit_epoch)
    - [`is_leak_active`](#is_leak_active)
  - [Misc](#misc-2)
    - [`get_flag_indices_and_numerators`](#get_flag_indices_and_numerators)
    - [`add_flag`](#add_flag)
    - [`has_flag`](#has_flag)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_sync_committee_indices`](#get_sync_committee_indices)
    - [`get_sync_committee`](#get_sync_committee)
    - [`get_base_reward`](#get_base_reward)
    - [`get_unslashed_participating_indices`](#get_unslashed_participating_indices)
    - [`get_flag_index_rewards`](#get_flag_index_rewards)
    - [`get_flag_penalties`](#get_flag_penalties)
    - [`get_leak_penalties`](#get_leak_penalties)
  - [Beacon state mutators](#beacon-state-mutators)
    - [New `slash_validator`](#new-slash_validator)
  - [Block processing](#block-processing)
    - [Modified `process_attestation`](#modified-process_attestation)
    - [Modified `process_deposit`](#modified-process_deposit)
    - [Sync committee processing](#sync-committee-processing)
  - [Modified helpers](#modified-helpers)
    - [Modified `compute_activation_exit_epoch`](#modified-compute_activation_exit_epoch)
    - [Modified `initiate_validator_exit`](#modified-initiate_validator_exit)
  - [Epoch processing](#epoch-processing)
    - [Justification and finalization](#justification-and-finalization)
    - [Leak updates](#leak-updates)
    - [Rewards and penalties](#rewards-and-penalties)
    - [Registry updates](#registry-updates)
    - [Slashings](#slashings)
    - [Effective balances updates](#effective-balances-updates)
    - [Participation flags updates](#participation-flags-updates)
    - [Sync committee updates](#sync-committee-updates)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document specifies the beacon chain changes in the first Eth2 hard fork, tentatively named Hard Fork 1 (HF1). The FH1 highlights are:

* sync committees to support light clients
* incentive accounting reforms to reduce spec complexity
* updated penalty configuration values, moving them toward their planned maximally punitive configuration
* fork choice rule fixes to mitigate attacks

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `ParticipationFlags` | `uint8` | a succint representation of 8 boolean participation flags |

## Constants

### Participation flag indices

| Name | Value |
| - | - |
| `TIMELY_HEAD_FLAG_INDEX` | `0` |
| `TIMELY_SOURCE_FLAG_INDEX` | `1` |
| `TIMELY_TARGET_FLAG_INDEX` | `2` |

### Participation flag fractions

| Name | Value |
| - | - |
| `TIMELY_HEAD_FLAG_NUMERATOR` | `12` |
| `TIMELY_SOURCE_FLAG_NUMERATOR` | `12` |
| `TIMELY_TARGET_FLAG_NUMERATOR` | `32` |
| `FLAG_DENOMINATOR` | `64` |

**Note**: The participatition flag fractions add up to 7/8. The remaining 1/8 is for proposer incentives and other future micro-incentives.

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
| `SYNC_COMMITTEE_SIZE` | `uint64(2**10)` (= 1,024) |
| `SYNC_SUBCOMMITTEE_SIZE` | `uint64(2**6)` (= 64) |
| `LEAK_SCORE_BIAS` | `uint64(2**2)` (= 4) |
| `LEAK_PENALTY_QUOTIENT` | `uint64(2**28)` (= 268,435,456) |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `EPOCHS_TO_LEAK_PENALTIES` | `uint64(2**2)` (= 4) | epochs | 25.6 minutes |
| `EPOCHS_PER_SYNC_COMMITTEE_PERIOD` | `uint64(2**8)` (= 256) | epochs | ~27 hours |
| `EPOCHS_PER_ACTIVATION_EXIT_PERIOD` | `uint64(2**6)` (= 64) | epochs | ~6.8 hours |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_SYNC_COMMITTEE` | `DomainType('0x07000000')` |

## Containers

### Modified containers

#### `BeaconBlockBody`

```python
class BeaconBlockBody(phase0.BeaconBlockBody):
    # Sync committee aggregate signature
    sync_committee_bits: Bitvector[SYNC_COMMITTEE_SIZE]  # [New in HF1]
    sync_committee_signature: BLSSignature  # [New in HF1]
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
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]  # [New in HF1]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]  # [New in HF1]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Leak
    leak_epochs_counter: Epoch  # [New in HF1]
    leak_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]  # [New in HF1]
    # Sync
    current_sync_committee: SyncCommittee  # [New in HF1]
    next_sync_committee: SyncCommittee  # [New in HF1]
```

### New containers

#### `SyncCommittee`

```python
class SyncCommittee(Container):
    pubkeys: Vector[BLSPubkey, SYNC_COMMITTEE_SIZE]
    pubkey_aggregates: Vector[BLSPubkey, SYNC_COMMITTEE_SIZE // SYNC_SUBCOMMITTEE_SIZE]
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

#### `is_activation_exit_epoch`

```python
def is_activation_exit_epoch(state: BeaconState) -> bool:
    return get_current_epoch(state) % EPOCHS_PER_ACTIVATION_EXIT_PERIOD == 0
```

#### `is_leak_active`

```python
def is_leak_active(state: BeaconState) -> bool:
    return get_finality_delay(state) > EPOCHS_TO_LEAK_PENALTIES
```

### Misc

#### `get_flag_indices_and_numerators`

```python
def get_flag_indices_and_numerators() -> Sequence[Tuple[int, int]]:
    return (
        (TIMELY_HEAD_FLAG_INDEX, TIMELY_HEAD_FLAG_NUMERATOR),
        (TIMELY_SOURCE_FLAG_INDEX, TIMELY_SOURCE_FLAG_NUMERATOR),
        (TIMELY_TARGET_FLAG_INDEX, TIMELY_TARGET_FLAG_NUMERATOR),
    )
```

#### `add_flag`

```python
def add_flag(flags: ParticipationFlags, flag_index: int) -> ParticipationFlags:
    flag = ParticipationFlags(2**flag_index)
    return flags | flag
```

#### `has_flag`

```python
def has_flag(flags: ParticipationFlags, flag_index: int) -> bool:
    flag = ParticipationFlags(2**flag_index)
    return flags & flag == flag
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
    pubkeys = [state.validators[index].pubkey for index in indices]
    subcommitees = [pubkeys[i:i + SYNC_SUBCOMMITTEE_SIZE] for i in range(0, len(pubkeys), SYNC_SUBCOMMITTEE_SIZE)]
    pubkey_aggregates = [bls.AggregatePKs(subcommitee) for subcommitee in subcommitees]
    return SyncCommittee(pubkeys=pubkeys, pubkey_aggregates=pubkey_aggregates)
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
def get_unslashed_participating_indices(state: BeaconState, flag_index: int, epoch: Epoch) -> Set[ValidatorIndex]:
    """
    Retrieve the active and unslashed validator indices for the given epoch and flag index.
    """
    assert epoch in (get_previous_epoch(state), get_current_epoch(state))
    if epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation
    active_validator_indices = get_active_validator_indices(state, epoch)
    participating_indices = [i for i in active_validator_indices if has_flag(epoch_participation[i], flag_index)]
    return set(filter(lambda index: not state.validators[index].slashed, participating_indices))
```

#### `get_flag_index_rewards`

```python
def get_flag_index_rewards(state: BeaconState, flag_index: int, numerator: uint64) -> Sequence[Gwei]:
    rewards = [Gwei(0)] * len(state.validators)
    unslashed_participating_indices = get_unslashed_participating_indices(state, flag_index, get_previous_epoch(state))
    increment = EFFECTIVE_BALANCE_INCREMENT  # Factored out from balances to avoid uint64 overflow
    unslashed_participating_increments = get_total_balance(state, unslashed_participating_indices) // increment
    active_increments = get_total_active_balance(state) // increment
    for index in unslashed_participating_indices:
        base_reward = get_base_reward(state, index)
        # Cancel equivalent flag penalty
        rewards[index] += Gwei(base_reward * numerator // FLAG_DENOMINATOR)
        if not is_leak_active(state):
            reward_numerator = base_reward * numerator * unslashed_participating_increments
            rewards[index] += Gwei(reward_numerator // (active_increments * FLAG_DENOMINATOR))
    return rewards
```

#### `get_flag_penalties`

```python
def get_flag_penalties(state: BeaconState) -> Sequence[Gwei]:
    penalties = [Gwei(0)] * len(state.validators)
    flag_numerators = [numerator for _, numerator in get_flag_indices_and_numerators()]
    for index in get_eligible_validator_indices(state):
        base_reward = get_base_reward(state, index)
        penalty_per_epoch = sum(base_reward * numerator // FLAG_DENOMINATOR for numerator in flag_numerators)
        # Cancel equivalent flag reward
        penalties[index] += Gwei(penalty_per_epoch * EPOCHS_PER_ACTIVATION_EXIT_PERIOD)
    return penalties
```

#### `get_leak_penalties`

```python
def get_leak_penalties(state: BeaconState) -> Sequence[Gwei]:
    penalties = [Gwei(0)] * len(state.validators)
    for index in get_eligible_validator_indices(state):
        leak_score = state.leak_scores[index]
        if leak_score >= EPOCHS_PER_ACTIVATION_EXIT_PERIOD * LEAK_SCORE_BIAS:
            penalties[index] += Gwei(leak_score * state.leak_epochs_counter // LEAK_PENALTY_QUOTIENT)
    return penalties
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
    process_operations(state, block.body)  # [Modified in HF1]
    process_sync_committee(state, block.body)  # [New in HF1]
```

#### Modified `process_attestation`

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

    # Participation flag indices
    participation_flag_indices = []
    if is_matching_head and is_matching_target and state.slot <= data.slot + MIN_ATTESTATION_INCLUSION_DELAY:
        participation_flag_indices.append(TIMELY_HEAD_FLAG_INDEX)
    if is_matching_source and state.slot <= data.slot + integer_squareroot(SLOTS_PER_EPOCH):
        participation_flag_indices.append(TIMELY_SOURCE_FLAG_INDEX)
    if is_matching_target and state.slot <= data.slot + SLOTS_PER_EPOCH:
        participation_flag_indices.append(TIMELY_TARGET_FLAG_INDEX)

    # Update epoch participation flags
    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, data, attestation.aggregation_bits):
        for flag_index, flag_numerator in get_flag_indices_and_numerators():
            if flag_index in participation_flag_indices and not has_flag(epoch_participation[index], flag_index):
                add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * flag_numerator

    # Reward proposer
    proposer_reward = Gwei(proposer_reward_numerator // (FLAG_DENOMINATOR * PROPOSER_REWARD_QUOTIENT))
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
```

#### Modified `process_deposit`

*Note*: The function `process_deposit` is modified to initialize `leak_scores`, `previous_epoch_participation`, `current_epoch_participation`.

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
        # Initialize validator if the deposit signature is valid
        if bls.Verify(pubkey, signing_root, deposit.data.signature):
            state.validators.append(get_validator_from_deposit(state, deposit))
            state.balances.append(amount)
            state.leak_scores.append(0)
            state.previous_epoch_participation.append(ParticipationFlags(0b0000_0000))
            state.current_epoch_participation.append(ParticipationFlags(0b0000_0000))
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
    proposer_rewards = Gwei(0)
    active_validator_count = uint64(len(get_active_validator_indices(state, get_current_epoch(state))))
    for participant_index in participant_indices:
        proposer_reward = get_proposer_reward(state, participant_index)
        proposer_rewards += proposer_reward
        base_reward = get_base_reward(state, participant_index)
        max_participant_reward = base_reward - proposer_reward
        reward = Gwei(max_participant_reward * active_validator_count // (len(committee_indices) * SLOTS_PER_EPOCH))
        increase_balance(state, participant_index, reward)

    # Reward beacon proposer
    increase_balance(state, get_beacon_proposer_index(state), proposer_rewards)
```

### Modified helpers

#### Modified `compute_activation_exit_epoch`

```python
def compute_activation_exit_epoch(epoch: Epoch) -> Epoch:
    """
    Return the epoch during which validator activations and exits initiated in ``epoch`` take effect.
    """
    def round_up(x: uint64, step: uint64) -> uint64:
        return x if x % step == 0 else x - (x % step) + step
    return Epoch(round_up(epoch + 1 + MAX_SEED_LOOKAHEAD, EPOCHS_PER_ACTIVATION_EXIT_PERIOD))
```

#### Modified `initiate_validator_exit`

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

### Epoch processing

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)  # [Modified in HF1]
    process_leak_updates(state)  # [New in HF1]
    process_rewards_and_penalties(state)  # [Modified in HF1]
    process_registry_updates(state)  # [Modified in HF1]
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)  # [Modified in HF1]
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_roots_update(state)
    process_participation_flag_updates(state)  # [New in HF1]
    process_sync_committee_updates(state)  # [New in HF1]
```

#### Justification and finalization

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
    matching_target_indices = get_unslashed_participating_indices(state, TIMELY_TARGET_FLAG_INDEX, previous_epoch)
    if get_total_balance(state, matching_target_indices) * 3 >= get_total_active_balance(state) * 2:
        state.current_justified_checkpoint = Checkpoint(epoch=previous_epoch,
                                                        root=get_block_root(state, previous_epoch))
        state.justification_bits[1] = 0b1
    matching_target_indices = get_unslashed_participating_indices(state, TIMELY_TARGET_FLAG_INDEX, current_epoch)
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

#### Leak updates

*Note*: The function `process_leak_updates` is new.

```python
def process_leak_updates(state: BeaconState) -> None:
    # In a given epoch the leak score of a validator:
    #    (a) decreases by 1 if the validator participates
    #    (b) increases by LEAK_SCORE_BIAS if is_leak_active(state) and the validator does not participate
    # For efficiency rule (b) increases are batched at activation-exit epochs using the leak epochs counter.

    # Decrease leak score per rule (a)
    decrease_amount = 1
    if is_leak_active(state):
        decrease_amount += LEAK_SCORE_BIAS  # Cancel corresponding increase at activation-exit epochs
    for index in get_unslashed_participating_indices(state, TIMELY_TARGET_FLAG_INDEX, get_previous_epoch(state)):
        if state.leak_scores[index] < decrease_amount:
            state.leak_scores[index] = 0
        else:
            state.leak_scores[index] -= decrease_amount

    # Increase leak score per rule (b)
    if is_leak_active(state):
        state.leak_epochs_counter += Epoch(1)
    if is_activation_exit_epoch(state):
        for index in get_eligible_validator_indices(state):
            state.leak_scores[index] += LEAK_SCORE_BIAS * state.leak_epochs_counter
        state.leak_epochs_counter = Epoch(0)
```

#### Rewards and penalties

*Note*: The function `process_rewards_and_penalties` is modified to support the incentive reforms.

```python
def process_rewards_and_penalties(state: BeaconState) -> None:
    # No rewards are applied at the end of `GENESIS_EPOCH` because rewards are for work done in the previous epoch
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    # Process flag rewards across every flag index
    for (flag_index, flag_numerator) in get_flag_indices_and_numerators():
        flag_index_rewards = get_flag_index_rewards(state, flag_index, flag_numerator)
        for index in range(len(state.validators)):
            increase_balance(state, ValidatorIndex(index), flag_index_rewards[index])

    # Process flag penalties and leak penalties at activation-exit epochs
    if is_activation_exit_epoch(state):
        flag_penalties = get_flag_penalties(state)
        leak_penalties = get_leak_penalties(state)
        for index in range(len(state.validators)):
            decrease_balance(state, ValidatorIndex(index), flag_penalties[index] + leak_penalties[index])
```

#### Registry updates

*Note*: The function `process_registry_updates` is modified for processing every `EPOCHS_PER_ACTIVATION_EXIT_PERIOD` epochs.

```python
def process_registry_updates(state: BeaconState) -> None:
    if not is_activation_exit_epoch(state):
        return

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

#### Slashings

*Note*: The function `process_slashings` is modified to use `HF1_PROPORTIONAL_SLASHING_MULTIPLIER`.

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

#### Effective balances updates

*Note*: The function `process_effective_balance_updates` is modified for processing every `EPOCHS_PER_ACTIVATION_EXIT_PERIOD` epochs.

```python
def process_effective_balance_updates(state: BeaconState) -> None:
    if not is_activation_exit_epoch(state):
        return

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
```

#### Participation flags updates

*Note*: The function `process_participation_flag_updates` is new.

```python
def process_participation_flag_updates(state: BeaconState) -> None:
    state.previous_epoch_participation = state.current_epoch_participation
    state.current_epoch_participation = [ParticipationFlags(0b0000_0000) for _ in range(len(state.validators))]
```

#### Sync committee updates

*Note*: The function `process_sync_committee_updates` is new.

```python
def process_sync_committee_updates(state: BeaconState) -> None:
    next_epoch = get_current_epoch(state) + Epoch(1)
    if next_epoch % EPOCHS_PER_SYNC_COMMITTEE_PERIOD == 0:
        state.current_sync_committee = state.next_sync_committee
        state.next_sync_committee = get_sync_committee(state, next_epoch + EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
```
