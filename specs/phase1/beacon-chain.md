# Ethereum 2.0 Phase 1 -- The Beacon Chain with Shards

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Configuration](#configuration)
  - [Misc](#misc)
  - [Shard block configs](#shard-block-configs)
  - [Gwei values](#gwei-values)
  - [Initial values](#initial-values)
  - [Time parameters](#time-parameters)
  - [Domain types](#domain-types)
  - [Reward flag locations](#reward-flag-locations)
- [Updated containers](#updated-containers)
  - [Extended `AttestationData`](#extended-attestationdata)
  - [Extended `Attestation`](#extended-attestation)
  - [Extended `PendingAttestation`](#extended-pendingattestation)
  - [Extended `IndexedAttestation`](#extended-indexedattestation)
  - [Extended `AttesterSlashing`](#extended-attesterslashing)
  - [Extended `Validator`](#extended-validator)
  - [Extended `BeaconBlockBody`](#extended-beaconblockbody)
  - [Extended `BeaconBlock`](#extended-beaconblock)
    - [Extended `SignedBeaconBlock`](#extended-signedbeaconblock)
  - [Extended `BeaconState`](#extended-beaconstate)
- [New containers](#new-containers)
  - [`ShardBlock`](#shardblock)
  - [`SignedShardBlock`](#signedshardblock)
  - [`ShardBlockHeader`](#shardblockheader)
  - [`ShardState`](#shardstate)
  - [`ShardTransition`](#shardtransition)
  - [`ShardTransitionCandidate`](#shardtransitioncandidate)
  - [`CompactCommittee`](#compactcommittee)
- [Helper functions](#helper-functions)
  - [Misc](#misc-1)
  - [`bitwise_or`](#bitwise_or)
    - [`compute_previous_slot`](#compute_previous_slot)
    - [`pack_compact_validator`](#pack_compact_validator)
    - [`unpack_compact_validator`](#unpack_compact_validator)
    - [`committee_to_compact_committee`](#committee_to_compact_committee)
    - [`compute_shard_from_committee_index`](#compute_shard_from_committee_index)
    - [`compute_admissible_slots`](#compute_admissible_slots)
    - [`compute_updated_gasprice`](#compute_updated_gasprice)
    - [`compute_committee_source_epoch`](#compute_committee_source_epoch)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Updated `get_committee_count_per_slot`](#updated-get_committee_count_per_slot)
    - [`get_active_shard_count`](#get_active_shard_count)
    - [`get_online_validator_indices`](#get_online_validator_indices)
    - [`get_shard_committee`](#get_shard_committee)
    - [`get_light_client_committee`](#get_light_client_committee)
    - [`get_shard_proposer_index`](#get_shard_proposer_index)
    - [`get_committee_count_delta`](#get_committee_count_delta)
    - [`get_start_shard`](#get_start_shard)
    - [`get_latest_slot_for_shard`](#get_latest_slot_for_shard)
  - [Predicates](#predicates)
    - [`is_candidate_for_attestation_data`](#is_candidate_for_attestation_data)
    - [`optional_aggregate_verify`](#optional_aggregate_verify)
    - [`optional_fast_aggregate_verify`](#optional_fast_aggregate_verify)
  - [Block processing](#block-processing)
    - [Operations](#operations)
      - [New Attestation processing](#new-attestation-processing)
        - [`process_attestation`](#process_attestation)
      - [Shard transition processing](#shard-transition-processing)
        - [`get_online_beacon_committee`](#get_online_beacon_committee)
        - [`validate_shard_transition`](#validate_shard_transition)
        - [`execute_shard_transition`](#execute_shard_transition)
        - [`process_shard_transition`](#process_shard_transition)
      - [Verify ShardTransition uniqueness](#verify-shardtransition-uniqueness)
        - [`verify_shard_transition_uniqueness`](#verify_shard_transition_uniqueness)
      - [New default validator for deposits](#new-default-validator-for-deposits)
    - [Light client processing](#light-client-processing)
  - [Epoch transition](#epoch-transition)
    - [New rewards processing](#new-rewards-processing)
      - [`get_crosslink_deltas`](#get_crosslink_deltas)
      - [`process_rewards_and_penalties`](#process_rewards_and_penalties)
    - [Phase 1 final updates](#phase-1-final-updates)
    - [Custody game updates](#custody-game-updates)
    - [Online-tracking](#online-tracking)
    - [Crosslink-related final updates](#crosslink-related-final-updates)
    - [Light client committee updates](#light-client-committee-updates)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the extensions made to the Phase 0 design of The Beacon Chain
 to facilitate the new shards as part of Phase 1 of Eth2.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `Shard` | `uint64` | a shard number |
| `OnlineEpochs` | `uint8` | online countdown epochs |

## Configuration

Configuration is not namespaced. Instead it is strictly an extension;
 no constants of phase 0 change, but new constants are adopted for changing behaviors.

### Misc

| Name | Value |
| - | - | 
| `MAX_SHARDS` | `2**10` (= 1024) |
| `INITIAL_ACTIVE_SHARDS` | `2**6` (= 64) |
| `LIGHT_CLIENT_COMMITTEE_SIZE` | `2**7` (= 128) |
| `GASPRICE_ADJUSTMENT_COEFFICIENT` | `2**3` (= 8) | 
| `MAX_ACTIVE_VALIDATORS` | `MAX_VALIDATORS_PER_COMMITTEE * SLOTS_PER_EPOCH * INITIAL_ACTIVE_SHARDS` (= 4,194,304) |

### Shard block configs

| Name | Value | Unit |
| - | - | - |
| `MAX_SHARD_BLOCK_SIZE` | `2**20` (= 1,048,576) | bytes |
| `TARGET_SHARD_BLOCK_SIZE` | `2**18` (= 262,144) |  bytes |
| `SHARD_BLOCK_OFFSETS` | `[1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]` | - |
| `MAX_SHARD_BLOCKS_PER_ATTESTATION` | `len(SHARD_BLOCK_OFFSETS)` | - |
| `BYTES_PER_CUSTODY_CHUNK` | `2**12` (= 4,096) | bytes |
| `CUSTODY_RESPONSE_DEPTH` | `ceillog2(MAX_SHARD_BLOCK_SIZE // BYTES_PER_CUSTODY_CHUNK)` | - | 

### Gwei values

| Name | Value |
| - | - |
| `MAX_GASPRICE` | `Gwei(2**14)` (= 16,384) | Gwei | 
| `MIN_GASPRICE` | `Gwei(2**3)` (= 8) | Gwei | 

### Initial values

| Name | Value |
| - | - |
| `NO_SIGNATURE` | `BLSSignature(b'\x00' * 96)` | 

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `ONLINE_PERIOD` | `OnlineEpochs(2**3)` (= 8) | online epochs | ~51 mins |
| `LIGHT_CLIENT_COMMITTEE_PERIOD` | `Epoch(2**8)` (= 256) | epochs | ~27 hours |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_SHARD_PROPOSAL` | `DomainType('0x80000000')` |
| `DOMAIN_SHARD_COMMITTEE` | `DomainType('0x81000000')` |
| `DOMAIN_LIGHT_CLIENT` | `DomainType('0x82000000')` |
| `DOMAIN_CUSTODY_BIT_SLASHING` | `DomainType('0x83000000')` |
| `DOMAIN_LIGHT_SELECTION_PROOF` | `DomainType('0x84000000')` |
| `DOMAIN_LIGHT_AGGREGATE_AND_PROOF` | `DomainType('0x85000000')` |

### Reward flag locations

| Name | Value |
| - | - |
| `FLAG_CROSSLINK` | 1 |
| `FLAG_SOURCE` | 2 |
| `FLAG_TARGET` | 4 |
| `FLAG_HEAD` | 8 |
| `FLAG_VERY_TIMELY` | 16 |
| `FLAG_TIMELY` | 32 |

## Updated containers

The following containers have updated definitions in Phase 1.

### Extended `AttestationData`

```python
class AttestationData(Container):
    slot: Slot
    index: CommitteeIndex
    # LMD GHOST vote
    beacon_block_root: Root
    # FFG vote
    source: Checkpoint
    target: Checkpoint
    # Current-slot shard block root
    shard_head_root: Root
    # Shard transition root
    shard_transition_root: Root
```

### Extended `Attestation`

```python
class Attestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    signature: BLSSignature
```

### Extended `IndexedAttestation`

```python
class IndexedAttestation(Container):
    attesting_indices: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    signature: BLSSignature
```

### Extended `AttesterSlashing`

Note that the `attestation_1` and `attestation_2` have a new `IndexedAttestation` definition.

```python
class AttesterSlashing(Container):
    attestation_1: IndexedAttestation
    attestation_2: IndexedAttestation
```

### Extended `Validator`

```python
class Validator(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32  # Commitment to pubkey for withdrawals
    effective_balance: Gwei  # Balance at stake
    slashed: boolean
    # Status epochs
    activation_eligibility_epoch: Epoch  # When criteria for activation were met
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch  # When validator can withdraw funds
    # Custody game
    # next_custody_secret_to_reveal is initialised to the custody period
    # (of the particular validator) in which the validator is activated
    # = get_custody_period_for_validator(...)
    next_custody_secret_to_reveal: uint64
    # TODO: The max_reveal_lateness doesn't really make sense anymore.
    # So how do we incentivise early custody key reveals now?
    all_custody_secrets_revealed_epoch: Epoch  # to be initialized to FAR_FUTURE_EPOCH
```

### Extended `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Slashings
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    # Attesting
    attestations: List[Attestation, MAX_ATTESTATIONS]
    # Entry & exit
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    # Custody game
    chunk_challenges: List[CustodyChunkChallenge, MAX_CUSTODY_CHUNK_CHALLENGES]
    chunk_challenge_responses: List[CustodyChunkResponse, MAX_CUSTODY_CHUNK_CHALLENGE_RESPONSES]
    custody_key_reveals: List[CustodyKeyReveal, MAX_CUSTODY_KEY_REVEALS]
    early_derived_secret_reveals: List[EarlyDerivedSecretReveal, MAX_EARLY_DERIVED_SECRET_REVEALS]
    custody_slashings: List[SignedCustodySlashing, MAX_CUSTODY_SLASHINGS]
    # Shards
    shard_transitions: Vector[ShardTransition, MAX_SHARDS]
    # Light clients
    light_client_bits: Bitvector[LIGHT_CLIENT_COMMITTEE_SIZE]
    light_client_signature: BLSSignature
```

### Extended `BeaconBlock`

Note that the `body` has a new `BeaconBlockBody` definition.

```python
class BeaconBlock(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    parent_root: Root
    state_root: Root
    body: BeaconBlockBody
```

#### Extended `SignedBeaconBlock`

Note that the `message` has a new `BeaconBlock` definition.

```python
class SignedBeaconBlock(Container):
    message: BeaconBlock
    signature: BLSSignature
```

### Extended `BeaconState`

Note that aside from the new additions, `Validator` has a new definition.

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
    randao_mixes: Vector[Root, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint  # Previous epoch snapshot
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Phase 1
    current_epoch_start_shard: Shard
    shard_states: List[ShardState, MAX_SHARDS]
    online_countdown: List[OnlineEpochs, VALIDATOR_REGISTRY_LIMIT]  # not a raw byte array, considered its large size.
    current_light_committee: CompactCommittee
    next_light_committee: CompactCommittee
    current_shard_transition_candidates: List[ShardTransitionCandidate, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    previous_shard_transition_candidates: List[ShardTransitionCandidate, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    current_epoch_reward_flags: List[Bitvector[8], MAX_ACTIVE_VALIDATORS] 
    previous_epoch_reward_flags: List[Bitvector[8], MAX_ACTIVE_VALIDATORS] 
    # Custody game
    # Future derived secrets already exposed; contains the indices of the exposed validator
    # at RANDAO reveal period % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS
    exposed_derived_secrets: Vector[List[ValidatorIndex, MAX_EARLY_DERIVED_SECRET_REVEALS * SLOTS_PER_EPOCH],
                                    EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS]
    custody_chunk_challenge_records: List[CustodyChunkChallengeRecord, MAX_CUSTODY_CHUNK_CHALLENGE_RECORDS]
    custody_chunk_challenge_index: uint64
```

## New containers

The following containers are new in Phase 1.

### `ShardBlock`

```python
class ShardBlock(Container):
    shard_parent_root: Root
    beacon_parent_root: Root
    slot: Slot
    shard: Shard
    proposer_index: ValidatorIndex
    body: ByteList[MAX_SHARD_BLOCK_SIZE]
```

### `SignedShardBlock`

```python
class SignedShardBlock(Container):
    message: ShardBlock
    signature: BLSSignature
```

### `ShardBlockHeader`

```python
class ShardBlockHeader(Container):
    shard_parent_root: Root
    beacon_parent_root: Root
    slot: Slot
    shard: Shard
    proposer_index: ValidatorIndex
    body_root: Root
```

### `ShardState`

```python
class ShardState(Container):
    slot: Slot
    gasprice: Gwei
    latest_block_root: Root
```

### `ShardTransition`

```python
class ShardTransition(Container):
    # Starting from slot
    start_slot: Slot
    # Shard
    shard: Shard
    # Shard block lengths
    shard_block_lengths: List[uint64, MAX_SHARD_BLOCKS_PER_ATTESTATION]
    # Shard data roots
    # The root is of ByteList[MAX_SHARD_BLOCK_SIZE]
    shard_data_roots: List[Bytes32, MAX_SHARD_BLOCKS_PER_ATTESTATION]
    # Intermediate shard states
    shard_states: List[ShardState, MAX_SHARD_BLOCKS_PER_ATTESTATION]
    # Proposer signature aggregate
    proposer_signature_aggregate: BLSSignature
```

### `ShardTransitionCandidate`

```python
class ShardTransitionCandidate(Container):
    transition_root: Root
    block_root: Root
    slot: Slot
    index: CommitteeIndex
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
```

### `CompactCommittee`

```python
class CompactCommittee(Container):
    pubkeys: List[BLSPubkey, MAX_VALIDATORS_PER_COMMITTEE]
    compact_validators: List[uint64, MAX_VALIDATORS_PER_COMMITTEE]
```

## Helper functions

### Misc

### `bitwise_or`

```python
def bitwise_or(a: Bitlist, b: Bitlist) -> Bitlist:
    return Bitlist([a_item | b_item for a_item, b_item in zip(a, b)])
```

#### `compute_previous_slot`

```python
def compute_previous_slot(slot: Slot) -> Slot:
    if slot > 0:
        return Slot(slot - 1)
    else:
        return Slot(0)
```

#### `pack_compact_validator`

```python
def pack_compact_validator(index: ValidatorIndex, slashed: bool, balance_in_increments: uint64) -> uint64:
    """
    Create a compact validator object representing index, slashed status, and compressed balance.
    Takes as input balance-in-increments (// EFFECTIVE_BALANCE_INCREMENT) to preserve symmetry with
    the unpacking function.
    """
    return (index << 16) + (slashed << 15) + balance_in_increments
```

#### `unpack_compact_validator`

```python
def unpack_compact_validator(compact_validator: uint64) -> Tuple[ValidatorIndex, bool, uint64]:
    """
    Return validator index, slashed, balance // EFFECTIVE_BALANCE_INCREMENT
    """
    return (
        ValidatorIndex(compact_validator >> 16),
        bool((compact_validator >> 15) % 2),
        compact_validator & (2**15 - 1),
    )
```

#### `committee_to_compact_committee`

```python
def committee_to_compact_committee(state: BeaconState, committee: Sequence[ValidatorIndex]) -> CompactCommittee:
    """
    Given a state and a list of validator indices, outputs the ``CompactCommittee`` representing them.
    """
    validators = [state.validators[i] for i in committee]
    compact_validators = [
        pack_compact_validator(i, v.slashed, v.effective_balance // EFFECTIVE_BALANCE_INCREMENT)
        for i, v in zip(committee, validators)
    ]
    pubkeys = [v.pubkey for v in validators]
    return CompactCommittee(pubkeys=pubkeys, compact_validators=compact_validators)
```

#### `compute_shard_from_committee_index`

```python
def compute_shard_from_committee_index(state: BeaconState, index: CommitteeIndex, slot: Slot) -> Shard:
    active_shards = get_active_shard_count(state)
    return Shard((index + get_start_shard(state, slot)) % active_shards)
```

#### `compute_admissible_slots`

```python
def compute_admissible_slots(start_slot: Slot) -> Sequence[Slot]:
    """
    Return the admissible slots for shard blocks, assuming the most recent shard state
    was at slot `start_slot`
    """
    return [Slot(start_slot + x) for x in SHARD_BLOCK_OFFSETS]
```

#### `compute_updated_gasprice`

```python
def compute_updated_gasprice(prev_gasprice: Gwei, shard_block_length: uint64) -> Gwei:
    if shard_block_length > TARGET_SHARD_BLOCK_SIZE:
        delta = (prev_gasprice * (shard_block_length - TARGET_SHARD_BLOCK_SIZE)
                 // TARGET_SHARD_BLOCK_SIZE // GASPRICE_ADJUSTMENT_COEFFICIENT)
        return min(prev_gasprice + delta, MAX_GASPRICE)
    else:
        delta = (prev_gasprice * (TARGET_SHARD_BLOCK_SIZE - shard_block_length)
                 // TARGET_SHARD_BLOCK_SIZE // GASPRICE_ADJUSTMENT_COEFFICIENT)
        return max(prev_gasprice, MIN_GASPRICE + delta) - delta
```

#### `compute_committee_source_epoch`

```python
def compute_committee_source_epoch(epoch: Epoch, period: uint64) -> Epoch:
    """
    Return the source epoch for computing the committee.
    """
    source_epoch = epoch - epoch % period
    if source_epoch >= period:
        source_epoch -= period  # `period` epochs lookahead
    return source_epoch
```

### Beacon state accessors

#### Updated `get_committee_count_per_slot`

```python
def get_committee_count_per_slot(state: BeaconState, epoch: Epoch) -> uint64:
    """
    Return the number of committees in each slot for the given ``epoch``.
    """
    return max(uint64(1), min(
        get_active_shard_count(state),
        uint64(len(get_active_validator_indices(state, epoch))) // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE,
    ))
```

#### `get_active_shard_count`

```python
def get_active_shard_count(state: BeaconState) -> uint64:
    """
    Return the number of active shards.
    Note that this puts an upper bound on the number of committees per slot.
    """
    return INITIAL_ACTIVE_SHARDS
```

#### `get_online_validator_indices`

```python
def get_online_validator_indices(state: BeaconState) -> Set[ValidatorIndex]:
    active_validators = get_active_validator_indices(state, get_current_epoch(state))
    return set(i for i in active_validators if state.online_countdown[i] != 0)  # non-duplicate
```

#### `get_shard_committee`

```python
def get_shard_committee(beacon_state: BeaconState, epoch: Epoch, shard: Shard) -> Sequence[ValidatorIndex]:
    """
    Return the shard committee of the given ``epoch`` of the given ``shard``.
    """
    source_epoch = compute_committee_source_epoch(epoch, SHARD_COMMITTEE_PERIOD)
    active_validator_indices = get_active_validator_indices(beacon_state, source_epoch)
    seed = get_seed(beacon_state, source_epoch, DOMAIN_SHARD_COMMITTEE)
    return compute_committee(
        indices=active_validator_indices,
        seed=seed,
        index=shard,
        count=get_active_shard_count(beacon_state),
    )
```

#### `get_light_client_committee`

```python
def get_light_client_committee(beacon_state: BeaconState, epoch: Epoch) -> Sequence[ValidatorIndex]:
    """
    Return the light client committee of no more than ``LIGHT_CLIENT_COMMITTEE_SIZE`` validators.
    """
    source_epoch = compute_committee_source_epoch(epoch, LIGHT_CLIENT_COMMITTEE_PERIOD)
    active_validator_indices = get_active_validator_indices(beacon_state, source_epoch)
    seed = get_seed(beacon_state, source_epoch, DOMAIN_LIGHT_CLIENT)
    return compute_committee(
        indices=active_validator_indices,
        seed=seed,
        index=0,
        count=get_active_shard_count(beacon_state),
    )[:LIGHT_CLIENT_COMMITTEE_SIZE]
```

#### `get_shard_proposer_index`

```python
def get_shard_proposer_index(beacon_state: BeaconState, slot: Slot, shard: Shard) -> ValidatorIndex:
    """
    Return the proposer's index of shard block at ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    committee = get_shard_committee(beacon_state, epoch, shard)
    seed = hash(get_seed(beacon_state, epoch, DOMAIN_SHARD_COMMITTEE) + uint_to_bytes(slot))
    r = bytes_to_uint64(seed[:8])
    return committee[r % len(committee)]
```

#### `get_committee_count_delta`

```python
def get_committee_count_delta(state: BeaconState, start_slot: Slot, stop_slot: Slot) -> uint64:
    """
    Return the sum of committee counts in range ``[start_slot, stop_slot)``.
    """
    return sum(
        get_committee_count_per_slot(state, compute_epoch_at_slot(Slot(slot)))
        for slot in range(start_slot, stop_slot)
    )
```

#### `get_start_shard`

```python
def get_start_shard(state: BeaconState, slot: Slot) -> Shard:
    """
    Return the start shard at ``slot``.
    """
    current_epoch_start_slot = compute_start_slot_at_epoch(get_current_epoch(state))
    active_shard_count = get_active_shard_count(state)
    if current_epoch_start_slot == slot:
        return state.current_epoch_start_shard
    elif slot > current_epoch_start_slot:
        # Current epoch or the next epoch lookahead
        shard_delta = get_committee_count_delta(state, start_slot=current_epoch_start_slot, stop_slot=slot)
        return Shard((state.current_epoch_start_shard + shard_delta) % active_shard_count)
    else:
        # Previous epoch
        shard_delta = get_committee_count_delta(state, start_slot=slot, stop_slot=current_epoch_start_slot)
        max_committees_per_slot = active_shard_count
        max_committees_in_span = max_committees_per_slot * (current_epoch_start_slot - slot)
        return Shard(
            # Ensure positive
            (state.current_epoch_start_shard + max_committees_in_span - shard_delta)
            % active_shard_count
        )
```

#### `get_latest_slot_for_shard`

```python
def get_latest_slot_for_shard(state: BeaconState, shard: Shard) -> Slot:
    """
    Return the latest slot number of the given ``shard``.
    """
    return state.shard_states[shard].slot
```

### Predicates

#### `is_candidate_for_attestation_data`

```python
def is_candidate_for_attestation_data(candidate: ShardTransitionCandidate, data: AttestationData) -> bool:
    """
    Return whether the ``candidate`` is for the supplied ``data``
    """
    return (
        (candidate.transition_root, candidate.block_root, candidate.slot, candidate.index)
        == (data.shard_transition_root, data.shard_block_root, data.slot, data.index)
    )
```

#### `optional_aggregate_verify`

```python
def optional_aggregate_verify(pubkeys: Sequence[BLSPubkey],
                              messages: Sequence[Bytes32],
                              signature: BLSSignature) -> bool:
    """
    If ``pubkeys`` is an empty list, the given ``signature`` should be a stub ``NO_SIGNATURE``.
    Otherwise, verify it with standard BLS AggregateVerify API.
    """
    if len(pubkeys) == 0:
        return signature == NO_SIGNATURE
    else:
        return bls.AggregateVerify(pubkeys, messages, signature)
```

#### `optional_fast_aggregate_verify`

```python
def optional_fast_aggregate_verify(pubkeys: Sequence[BLSPubkey], message: Bytes32, signature: BLSSignature) -> bool:
    """
    If ``pubkeys`` is an empty list, the given ``signature`` should be a stub ``NO_SIGNATURE``.
    Otherwise, verify it with standard BLS FastAggregateVerify API.
    """
    if len(pubkeys) == 0:
        return signature == NO_SIGNATURE
    else:
        return bls.FastAggregateVerify(pubkeys, message, signature)
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_light_client_aggregate(state, block.body)
    process_operations(state, block.body)
```

#### Operations

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify that outstanding deposits are processed up to the maximum number of deposits
    assert len(body.deposits) == min(MAX_DEPOSITS, state.eth1_data.deposit_count - state.eth1_deposit_index)

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    # New attestation processing
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)

    # See custody game spec.
    process_custody_game_operations(state, body)

    verify_shard_transition_uniqueness(state, body.shard_transitions)
    for_ops(body.shard_transitions, process_shard_transition)

    # TODO process_operations(body.shard_receipt_proofs, process_shard_receipt_proofs)
```

##### New Attestation processing

###### `process_attestation`

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.index < get_committee_count_per_slot(state, data.target.epoch)
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot <= data.slot + SLOTS_PER_EPOCH

    committee = get_beacon_committee(state, data.slot, data.index)
    assert len(attestation.aggregation_bits) == len(committee)

    is_current_epoch_attestation = (data.target.epoch == get_current_epoch(state))

    if is_current_epoch_attestation:
        assert data.source == state.current_justified_checkpoint
        shard_transition_candidates = state.current_shard_transition_candidates
    else:
        assert data.source == state.previous_justified_checkpoint
        shard_transition_candidates = state.previous_shard_transition_candidates

    # Signature check
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    # Process target, source, head, timeliness
    flags_to_set = FLAG_SOURCE
    if attestation.data.target.root == get_block_root(state, attestation.data.target.epoch):
        flags_to_set |= FLAG_TARGET
    if attestation.data.beacon_block_root == get_block_root_at_slot(state, attestation.data.slot):
        flags_to_set |= FLAG_HEAD
    if state.slot - attestation.data.slot == 1:
        flags_to_set |= FLAG_VERY_TIMELY
    if state.slot - attestation.data.slot <= integer_squareroot(SLOTS_PER_EPOCH):
        flags_to_set |= FLAG_TIMELY

    flags = (state.current_epoch_reward_flags if is_current_epoch_attestation else state.previous_epoch_reward_flags)

    for participant in get_attesting_indices(state, attestation.data, attestation.aggregation_bits):
        active_position = get_active_validator_indices(state, data.target.epoch).index(participant)
        flags[active_position] |= flags_to_set

    # Process shard transition
    candidate_exists = False
    for candidate in shard_transition_candidates:
        if is_candidate_for_attestation_data(candidate, data):
            candidate.aggregation_bits = bitwise_or(candidate.aggregation_bits, attestation.aggregation_bits)
            candidate_exists = True
            # Invariant: `shard_transition_candidates` contains <= 1 item with any given `data`
    if not candidate_exists:
        shard_transition_candidates.append(ShardTransitionCandidate(
            transition_root=data.shard_transition_root,
            block_root=data.shard_block_root,
            slot=data.slot,
            index=data.index,
            aggregation_bits=attestation.aggregation_bits
        ))
```

##### Shard transition processing

###### `get_online_beacon_committee`

```python
def get_online_beacon_committee(state: BeaconState, slot: Slot, index: CommitteeIndex) -> List[ValidatorIndex]:
    committee = get_beacon_committee(state, slot, index)
    online_indices = get_online_validator_indices(state)
    return online_indices.intersection(committee)
```

```python
def get_online_transition_participants(state: BeaconState, candidate: ShardTransitionCandidate) -> List[ValidatorIndex]:
    committee = get_beacon_committee(state, candidate.slot, candidate.index)
    participants = [committee[i] for i in range(len(committee)) if candidate.aggregation_bits[i]]
    online_indices = get_online_validator_indices(state)
    return online_indices.intersection(participants)
```

###### `validate_shard_transition`

```python
def validate_shard_transition(state: BeaconState,
                              transition: ShardTransition,
                              candidate: ShardTransitionCandidate) -> None:
    """
    Validates that the given ShardTransition is sufficiently voted upon, is self consistent,
    and matchines the transition candidate.
    """
    # Validate transition and candidate shard coherence
    shard = (get_start_shard(state, transition.slot) + candidate.index) % get_active_shard_count(state)
    assert shard == transition.shard < get_active_shard_count(state)

    # Confirm sufficient balance
    online_committee = get_online_beacon_committee(state, candidate.slot, candidate.index)
    online_participants = get_online_transition_participants(state, candidate)
    assert get_total_balance(state, online_participants) * 3 >= get_total_balance(state, online_committee) * 2

    # Validate transition lengths adhere to expected slot range
    admissible_slots = compute_admissible_slots(transition.start_slot)[:len(transition.shard_data_roots)]
    assert (
        len(transition.shard_data_roots)
        == len(transition.shard_states)
        == len(transition.shard_block_lengths)
        == len(admissible_slots)
    )

    shard_state = state.shard_states[shard]

    # Process the shard transition;
    # in the mean time, reconstruct the headers for signature verification
    prev_gasprice = shard_state.gasprice
    shard_parent_root = shard_state.latest_block_root
    headers = []
    proposers = []
    for i, slot in enumerate(admissible_slots):
        shard_block_length = transition.shard_block_lengths[i]
        shard_state = transition.shard_states[i]
        # Verify correct calculation of gas prices and slots
        assert shard_state.gasprice == compute_updated_gasprice(prev_gasprice, shard_block_length)
        assert shard_state.slot == slot
        # Collect the non-empty proposals result
        if shard_block_length > 0:
            shard_proposer_index = get_shard_proposer_index(state, slot, shard)
            # Reconstruct shard headers
            header = ShardBlockHeader(
                shard_parent_root=shard_parent_root,
                beacon_parent_root=get_block_root_at_slot(state, slot),
                slot=slot,
                shard=shard,
                proposer_index=shard_proposer_index,
                body_root=transition.shard_data_roots[i]
            )
            shard_parent_root = hash_tree_root(header)
            headers.append(header)
            proposers.append(shard_proposer_index)
        else:
            # Must have a stub for `shard_data_root` if empty slot
            assert transition.shard_data_roots[i] == Root()
        prev_gasprice = shard_state.gasprice

    # Verify last header root is correct with respect to the transition candidate
    assert hash_tree_root(headers[-1]) == candidate.block_root

    # Verify combined proposer signature
    pubkeys = [state.validators[proposer].pubkey for proposer in proposers]
    signing_roots = [
        compute_signing_root(header, get_domain(state, DOMAIN_SHARD_PROPOSAL, compute_epoch_at_slot(header.slot)))
        for header in headers
    ]
    assert optional_aggregate_verify(pubkeys, signing_roots, transition.proposer_signature_aggregate)
```

###### `execute_shard_transition`

```python
def apply_shard_transition_updates(state: BeaconState,
                                   transition: ShardTransition,
                                   candidate: ShardTransitionCandidate) -> None:
    """
    Applies the given ShardTransition to the appropriate ShardState. Also processes shard proposer rewards and fees.
    """
    shard = transition.shard
    admissible_slots = compute_admissible_slots(transition.start_slot)[:len(transition.shard_data_roots)]

    # Shard proposer rewards and block size cost
    states_slots_lengths = zip(
        transition.shard_states,
        admissible_slots,
        transition.shard_block_lengths
    )
    for shard_state, slot, length in states_slots_lengths:
        proposer_index = get_shard_proposer_index(state, slot, shard)
        proposer_reward = (
            get_base_reward(state, proposer_index)
            * get_online_validator_indices(state)
            // get_active_shard_count(state)
        )
        increase_balance(state, proposer_index, proposer_reward)
        decrease_balance(state, proposer_index, shard_state.gasprice * length // TARGET_SHARD_BLOCK_SIZE)

    # Copy and save updated shard state
    shard_state = copy(transition.shard_states[len(transition.shard_states) - 1])
    shard_state.slot = compute_previous_slot(state.slot)
    state.shard_states[shard] = shard_state

    # Save attester and beacon proposer rewards
    is_current = compute_epoch_at_slot(candidate.slot) == get_current_epoch(state)
    flags = (state.current_epoch_reward_flags if is_current else state.previous_epoch_reward_flags)
    online_participants = get_online_transition_participants(state, candidate)
    for validator_index in online_participants:
        epoch = compute_epoch_at_slot(candidate.slot)
        shuffled_position = get_active_validator_indices(state, epoch).index(validator_index)
        flags[shuffled_position] |= FLAG_CROSSLINK
    estimated_attester_reward = sum([get_base_reward(state, attester) for attester in online_participants])
    proposer_reward = Gwei(estimated_attester_reward // PROPOSER_REWARD_QUOTIENT)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
```

###### `process_shard_transition`

```python
def process_shard_transition(state: BeaconState, transition: ShardTransition) -> None:
    # TODO: only need to check it once when phase 1 starts
    assert state.slot > PHASE_1_FORK_SLOT

    # Extract matching ShardTransitionCandidate
    all_candidates = state.current_shard_transition_candidates + state.previous_shard_transition_candidates
    matching_candidates = [c for c in all_candidates if c.shard_transition_root == hash_tree_root(transition)]
    assert len(matching_candidates) == 1
    matching_candidate = matching_candidates[0]

    # Validate the shard transition
    validate_shard_transition(state, transition, matching_candidate)

    # Apply the transition updates
    apply_shard_transition_updates(state, transition, matching_candidate)
```

##### Verify ShardTransition uniqueness

###### `verify_shard_transition_uniqueness`

```python
def verify_shard_transition_uniqueness(state: BeaconState, shard_transitions: List[ShardTransition]) -> None:
    for shard in range(get_active_shard_count(state)):
        transitions_for_shard = [transition for transition in shard_transitions if transition.shard == shard]
        assert len(transitions_for_shard) <= 1
```

##### New default validator for deposits

```python
def get_validator_from_deposit(state: BeaconState, deposit: Deposit) -> Validator:
    amount = deposit.data.amount
    effective_balance = min(amount - amount % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
    next_custody_secret_to_reveal = get_custody_period_for_validator(
        ValidatorIndex(len(state.validators)),
        get_current_epoch(state),
    )

    return Validator(
        pubkey=deposit.data.pubkey,
        withdrawal_credentials=deposit.data.withdrawal_credentials,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
        effective_balance=effective_balance,
        next_custody_secret_to_reveal=next_custody_secret_to_reveal,
        all_custody_secrets_revealed_epoch=FAR_FUTURE_EPOCH,
    )
```

#### Light client processing

```python
def process_light_client_aggregate(state: BeaconState, block_body: BeaconBlockBody) -> None:
    committee = get_light_client_committee(state, get_current_epoch(state))
    previous_slot = compute_previous_slot(state.slot)
    previous_block_root = get_block_root_at_slot(state, previous_slot)

    total_reward = Gwei(0)
    signer_pubkeys = []
    for bit_index, participant_index in enumerate(committee):
        if block_body.light_client_bits[bit_index]:
            signer_pubkeys.append(state.validators[participant_index].pubkey)
            if not state.validators[participant_index].slashed:
                increase_balance(state, participant_index, get_base_reward(state, participant_index))
                total_reward += get_base_reward(state, participant_index)

    increase_balance(state, get_beacon_proposer_index(state), Gwei(total_reward // PROPOSER_REWARD_QUOTIENT))

    signing_root = compute_signing_root(previous_block_root,
                                        get_domain(state, DOMAIN_LIGHT_CLIENT, compute_epoch_at_slot(previous_slot)))
    assert optional_fast_aggregate_verify(signer_pubkeys, signing_root, block_body.light_client_signature)
```

### Epoch transition

This epoch transition overrides the phase0 epoch transition:

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_reveal_deadlines(state)
    process_challenge_deadlines(state)
    process_slashings(state)
    process_final_updates(state)  # phase 0 final updates
    process_phase_1_final_updates(state)
```

#### New rewards and penalties processing

##### `get_unslashed_participant_indices`

```python
def get_unslashed_participant_indices(state: BeaconState, flag: uint8) -> Set[ValidatorIndex]:
    participant_indices = [
        index for i, index in enumerate(get_active_validator_indices(state, get_previous_epoch(state)))
        if state.previous_epoch_reward_flags[i] & flag
    ]
    return set(filter(lambda index: not state.validators[index].slashed, participant_indices))
```

##### `get_standard_flag_deltas`

```python
def get_standard_flag_deltas(state: BeaconState, flag: uint8) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    rewards = [Gwei(0)] * len(state.validators)
    penalties = [Gwei(0)] * len(state.validators)
    unslashed_participant_indices = get_unslashed_participant_indices(state, flag)
    for index in get_eligible_validator_indices(state):
        if index in unslashed_participant_indices:
            if is_in_inactivity_leak(state):
                # Since full base reward will be canceled out by inactivity penalty deltas,
                # optimal participation receives full base reward compensation here.
                rewards[index] += get_base_reward(state, index)
            else:
                increment = EFFECTIVE_BALANCE_INCREMENT  # Factored out from balance totals to avoid uint64 overflow
                total_participating_balance = get_total_balance(state, unslashed_participant_indices) // increment
                total_balance = get_total_active_balance(state) // increment
                rewards[index] += get_base_reward(state, index) * total_participating_balance // total_balance
        else:
            penalties[index] += get_base_reward(state, index)
    return rewards, penalties
```

##### `get_inactivity_penalty_deltas`

```python
def get_inactivity_penalty_deltas(state: BeaconState) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return inactivity reward/penalty deltas for each validator.
    """
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    if is_in_inactivity_leak(state):
        matching_target_attesting_indices = set([
            index for i, index in enumerate(get_active_validator_indices(state, get_previous_epoch(state)))
            if state.previous_epoch_reward_flags[i] & FLAG_TARGET
        ])
        for index in get_eligible_validator_indices(state):
            # If validator is performing optimally this cancels all rewards for a neutral balance
            base_reward = get_base_reward(state, index)
            penalties[index] += Gwei(BASE_REWARDS_PER_EPOCH * base_reward - get_proposer_reward(state, index))
            if index not in matching_target_attesting_indices:
                effective_balance = state.validators[index].effective_balance
                penalties[index] += Gwei(effective_balance * get_finality_delay(state) // INACTIVITY_PENALTY_QUOTIENT)

    # No rewards associated with inactivity penalties
    rewards = [Gwei(0) for _ in range(len(state.validators))]
    return rewards, penalties
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
    matching_target_attestering_indices = set([
        index for i, index in enumerate(get_active_validator_indices(state, get_previous_epoch(state)))
        if state.previous_epoch_reward_flags[i] & FLAG_TARGET
    ])
    if get_total_balance(state, matching_target_attestering_indices) * 3 >= get_total_active_balance(state) * 2:
        state.current_justified_checkpoint = Checkpoint(epoch=previous_epoch,
                                                        root=get_block_root(state, previous_epoch))
        state.justification_bits[1] = 0b1
    matching_target_attestering_indices = set([
        index for i, index in enumerate(get_active_validator_indices(state, get_current_epoch(state)))
        if state.current_epoch_reward_flags[i] & FLAG_TARGET
    ])
    if get_total_balance(state, matching_target_attestering_indices) * 3 >= get_total_active_balance(state) * 2:
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

##### `process_rewards_and_penalties`

```python
def process_rewards_and_penalties(state: BeaconState) -> None:
    # No rewards are applied at the end of `GENESIS_EPOCH` because rewards are for work done in the previous epoch
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    rewards_and_penalties = [
        get_standard_flag_deltas(state, FLAG_CROSSLINK),
        get_standard_flag_deltas(state, FLAG_SOURCE),
        get_standard_flag_deltas(state, FLAG_TARGET),
        get_standard_flag_deltas(state, FLAG_HEAD),
        get_standard_flag_deltas(state, FLAG_VERY_TIMELY),
        get_standard_flag_deltas(state, FLAG_TIMELY),
        get_inactivity_penalty_deltas(state),
    ]
    for (rewards, penalties) in rewards_and_penalties:
        for index in range(len(state.validators)):
            increase_balance(state, ValidatorIndex(index), rewards[index])
            decrease_balance(state, ValidatorIndex(index), penalties[index])
```

#### Phase 1 final updates

```python
def process_phase_1_final_updates(state: BeaconState) -> None:
    process_custody_final_updates(state)
    process_online_tracking(state)
    process_crosslink_final_updates(state)
    process_light_client_committee_updates(state)

    # Update current_epoch_start_shard
    state.current_epoch_start_shard = get_start_shard(state, Slot(state.slot + 1))
```

#### Custody game updates

`process_reveal_deadlines`, `process_challenge_deadlines` and `process_custody_final_updates` are defined in [the Custody Game spec](./custody-game.md), 

#### Online-tracking

```python
def process_online_tracking(state: BeaconState) -> None:
    # Slowly remove validators from the "online" set if they do not show up
    for index in range(len(state.validators)):
        if state.online_countdown[index] != 0:
            state.online_countdown[index] = state.online_countdown[index] - 1

    # Process pending attestations
    # TODO REDO
    for pending_attestation in state.current_epoch_attestations + state.previous_epoch_attestations:
        for index in get_attesting_indices(state, pending_attestation.data, pending_attestation.aggregation_bits):
            state.online_countdown[index] = ONLINE_PERIOD
```

#### Crosslink-related final updates

```python
def process_crosslink_final_updates(state: BeaconState) -> None:
    state.previous_shard_transition_candidates = state.current_shard_transition_candidates
    state.current_shard_transition_candidates = []
    
    state.previous_epoch_reward_flags = state.current_epoch_reward_flags
    state.current_epoch_reward_flags = List[Bitvector[8], MAX_ACTIVE_VALIDATORS](
        [0] * len(get_active_validator_indices(state, get_current_epoch(state) + 1))
    )
```

#### Light client committee updates

```python
def process_light_client_committee_updates(state: BeaconState) -> None:
    """
    Update light client committees.
    """
    next_epoch = compute_epoch_at_slot(Slot(state.slot + 1))
    if next_epoch % LIGHT_CLIENT_COMMITTEE_PERIOD == 0:
        state.current_light_committee = state.next_light_committee
        new_committee = get_light_client_committee(state, next_epoch + LIGHT_CLIENT_COMMITTEE_PERIOD)
        state.next_light_committee = committee_to_compact_committee(state, new_committee)
```
