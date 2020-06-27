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
  - [`CompactCommittee`](#compactcommittee)
  - [`AttestationCustodyBitWrapper`](#attestationcustodybitwrapper)
- [Helper functions](#helper-functions)
  - [Misc](#misc-1)
    - [`compute_previous_slot`](#compute_previous_slot)
    - [`pack_compact_validator`](#pack_compact_validator)
    - [`unpack_compact_validator`](#unpack_compact_validator)
    - [`committee_to_compact_committee`](#committee_to_compact_committee)
    - [`compute_shard_from_committee_index`](#compute_shard_from_committee_index)
    - [`compute_offset_slots`](#compute_offset_slots)
    - [`compute_updated_gasprice`](#compute_updated_gasprice)
    - [`compute_committee_source_epoch`](#compute_committee_source_epoch)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_active_shard_count`](#get_active_shard_count)
    - [`get_online_validator_indices`](#get_online_validator_indices)
    - [`get_shard_committee`](#get_shard_committee)
    - [`get_light_client_committee`](#get_light_client_committee)
    - [`get_shard_proposer_index`](#get_shard_proposer_index)
    - [`get_committee_count_delta`](#get_committee_count_delta)
    - [`get_start_shard`](#get_start_shard)
    - [`get_latest_slot_for_shard`](#get_latest_slot_for_shard)
    - [`get_offset_slots`](#get_offset_slots)
  - [Predicates](#predicates)
    - [`is_on_time_attestation`](#is_on_time_attestation)
    - [`is_winning_attestation`](#is_winning_attestation)
    - [`optional_aggregate_verify`](#optional_aggregate_verify)
    - [`optional_fast_aggregate_verify`](#optional_fast_aggregate_verify)
  - [Block processing](#block-processing)
    - [Operations](#operations)
      - [New Attestation processing](#new-attestation-processing)
        - [`validate_attestation`](#validate_attestation)
        - [Updated `process_attestation`](#updated-process_attestation)
      - [Shard transition processing](#shard-transition-processing)
        - [`apply_shard_transition`](#apply_shard_transition)
        - [`process_crosslink_for_shard`](#process_crosslink_for_shard)
        - [`process_crosslinks`](#process_crosslinks)
        - [`verify_empty_shard_transition`](#verify_empty_shard_transition)
        - [`process_shard_transitions`](#process_shard_transitions)
      - [New default validator for deposits](#new-default-validator-for-deposits)
    - [Light client processing](#light-client-processing)
  - [Epoch transition](#epoch-transition)
    - [Phase 1 final updates](#phase-1-final-updates)
    - [Custody game updates](#custody-game-updates)
    - [Online-tracking](#online-tracking)
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
| `LIGHT_CLIENT_COMMITTEE_SIZE` | `2**7` (= 128) |
| `GASPRICE_ADJUSTMENT_COEFFICIENT` | `2**3` (= 8) | 

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
    # Shard vote
    shard: Shard
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

### Extended `PendingAttestation`

```python
class PendingAttestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    inclusion_delay: Slot
    proposer_index: ValidatorIndex
    # Phase 1
    crosslink_success: boolean
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

Note that aside from the new additions, `Validator` and `PendingAttestation` have new definitions.

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
    # Attestations
    previous_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    current_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
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

### `CompactCommittee`

```python
class CompactCommittee(Container):
    pubkeys: List[BLSPubkey, LIGHT_CLIENT_COMMITTEE_SIZE]
    compact_validators: List[uint64, LIGHT_CLIENT_COMMITTEE_SIZE]
```

### `AttestationCustodyBitWrapper`

```python
class AttestationCustodyBitWrapper(Container):
    attestation_data_root: Root
    block_index: uint64
    bit: boolean
```

## Helper functions

### Misc

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

#### `compute_offset_slots`

```python
def compute_offset_slots(start_slot: Slot, end_slot: Slot) -> Sequence[Slot]:
    """
    Return the offset slots that are greater than ``start_slot`` and less than ``end_slot``.
    """
    return [Slot(start_slot + x) for x in SHARD_BLOCK_OFFSETS if start_slot + x < end_slot]
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

#### `get_active_shard_count`

```python
def get_active_shard_count(state: BeaconState) -> uint64:
    return len(state.shard_states)  # May adapt in the future, or change over time.
```

#### `get_online_validator_indices`

```python
def get_online_validator_indices(state: BeaconState) -> Set[ValidatorIndex]:
    active_validators = get_active_validator_indices(state, get_current_epoch(state))
    return set([i for i in active_validators if state.online_countdown[i] != 0])
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
    active_shard_count = get_active_shard_count(beacon_state)
    return compute_committee(
        indices=active_validator_indices,
        seed=seed,
        index=shard,
        count=active_shard_count,
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
    seed = hash(get_seed(beacon_state, epoch, DOMAIN_SHARD_COMMITTEE) + int_to_bytes(slot, length=8))
    r = bytes_to_int(seed[:8])
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
        max_committees_per_epoch = MAX_COMMITTEES_PER_SLOT * SLOTS_PER_EPOCH
        return Shard(
            # Ensure positive
            (state.current_epoch_start_shard + max_committees_per_epoch * active_shard_count - shard_delta)
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

#### `get_offset_slots`

```python
def get_offset_slots(state: BeaconState, shard: Shard) -> Sequence[Slot]:
    """
    Return the offset slots of the given ``shard``.
    The offset slot are after the latest slot and before current slot. 
    """
    return compute_offset_slots(get_latest_slot_for_shard(state, shard), state.slot)
```

### Predicates

#### `is_on_time_attestation`

```python
def is_on_time_attestation(state: BeaconState,
                           attestation_data: AttestationData) -> bool:
    """
    Check if the given ``attestation_data`` is on-time.
    """
    return attestation_data.slot == compute_previous_slot(state.slot)
```

#### `is_winning_attestation`

```python
def is_winning_attestation(state: BeaconState,
                           attestation: PendingAttestation,
                           committee_index: CommitteeIndex,
                           winning_root: Root) -> bool:
    """
    Check if on-time ``attestation`` helped contribute to the successful crosslink of
    ``winning_root`` formed by ``committee_index`` committee.
    """
    return (
        is_on_time_attestation(state, attestation.data)
        and attestation.data.index == committee_index
        and attestation.data.shard_transition_root == winning_root
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

    process_shard_transitions(state, body.shard_transitions, body.attestations)

    # TODO process_operations(body.shard_receipt_proofs, process_shard_receipt_proofs)
```

##### New Attestation processing

###### `validate_attestation`

```python
def validate_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.index < get_committee_count_per_slot(state, data.target.epoch)
    assert data.index < get_active_shard_count(state)
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot <= data.slot + SLOTS_PER_EPOCH

    committee = get_beacon_committee(state, data.slot, data.index)
    assert len(attestation.aggregation_bits) == len(committee)

    if attestation.data.target.epoch == get_current_epoch(state):
        assert attestation.data.source == state.current_justified_checkpoint
    else:
        assert attestation.data.source == state.previous_justified_checkpoint

    # Type 1: on-time attestations
    if is_on_time_attestation(state, attestation.data):
        # Correct parent block root
        assert data.beacon_block_root == get_block_root_at_slot(state, compute_previous_slot(state.slot))
        # Correct shard number
        shard = compute_shard_from_committee_index(state, attestation.data.index, attestation.data.slot)
        assert attestation.data.shard == shard
        # On-time attestations should have a non-empty shard transition root
        assert attestation.data.shard_transition_root != hash_tree_root(ShardTransition())
    # Type 2: no shard transition
    else:
        # Ensure delayed attestation
        assert data.slot < compute_previous_slot(state.slot)
        # Late attestations cannot have a shard transition root
        assert data.shard_transition_root == Root()

    # Signature check
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))
```

###### Updated `process_attestation`

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    validate_attestation(state, attestation)
    # Store pending attestation for epoch processing
    pending_attestation = PendingAttestation(
        aggregation_bits=attestation.aggregation_bits,
        data=attestation.data,
        inclusion_delay=state.slot - attestation.data.slot,
        proposer_index=get_beacon_proposer_index(state),
        crosslink_success=False,  # To be filled in during process_shard_transitions
    )
    if attestation.data.target.epoch == get_current_epoch(state):
        state.current_epoch_attestations.append(pending_attestation)
    else:
        state.previous_epoch_attestations.append(pending_attestation)
```

##### Shard transition processing

###### `apply_shard_transition`

```python
def apply_shard_transition(state: BeaconState, shard: Shard, transition: ShardTransition) -> None:
    # TODO: only need to check it once when phase 1 starts
    assert state.slot > PHASE_1_GENESIS_SLOT

    # Correct data root count
    offset_slots = get_offset_slots(state, shard)
    assert (
        len(transition.shard_data_roots)
        == len(transition.shard_states)
        == len(transition.shard_block_lengths)
        == len(offset_slots)
    )
    assert transition.start_slot == offset_slots[0]

    headers = []
    proposers = []
    prev_gasprice = state.shard_states[shard].gasprice
    shard_parent_root = state.shard_states[shard].latest_block_root
    for i, offset_slot in enumerate(offset_slots):
        shard_block_length = transition.shard_block_lengths[i]
        shard_state = transition.shard_states[i]
        # Verify correct calculation of gas prices and slots
        assert shard_state.gasprice == compute_updated_gasprice(prev_gasprice, shard_block_length)
        assert shard_state.slot == offset_slot
        # Collect the non-empty proposals result
        is_empty_proposal = shard_block_length == 0
        if not is_empty_proposal:
            proposal_index = get_shard_proposer_index(state, offset_slot, shard)
            # Reconstruct shard headers
            header = ShardBlockHeader(
                shard_parent_root=shard_parent_root,
                beacon_parent_root=get_block_root_at_slot(state, offset_slot),
                slot=offset_slot,
                shard=shard,
                proposer_index=proposal_index,
                body_root=transition.shard_data_roots[i]
            )
            shard_parent_root = hash_tree_root(header)
            headers.append(header)
            proposers.append(proposal_index)
        else:
            # Must have a stub for `shard_data_root` if empty slot
            assert transition.shard_data_roots[i] == Root()

        prev_gasprice = shard_state.gasprice

    pubkeys = [state.validators[proposer].pubkey for proposer in proposers]
    signing_roots = [
        compute_signing_root(header, get_domain(state, DOMAIN_SHARD_PROPOSAL, compute_epoch_at_slot(header.slot)))
        for header in headers
    ]
    # Verify combined proposer signature
    assert optional_aggregate_verify(pubkeys, signing_roots, transition.proposer_signature_aggregate)

    # Save updated state
    state.shard_states[shard] = transition.shard_states[len(transition.shard_states) - 1]
    state.shard_states[shard].slot = compute_previous_slot(state.slot)
```

###### `process_crosslink_for_shard`

```python
def process_crosslink_for_shard(state: BeaconState,
                                committee_index: CommitteeIndex,
                                shard_transition: ShardTransition,
                                attestations: Sequence[Attestation]) -> Root:
    on_time_attestation_slot = compute_previous_slot(state.slot)
    committee = get_beacon_committee(state, on_time_attestation_slot, committee_index)
    online_indices = get_online_validator_indices(state)
    shard = compute_shard_from_committee_index(state, committee_index, on_time_attestation_slot)

    # Loop over all shard transition roots
    shard_transition_roots = set([a.data.shard_transition_root for a in attestations])
    for shard_transition_root in sorted(shard_transition_roots):
        transition_attestations = [a for a in attestations if a.data.shard_transition_root == shard_transition_root]
        transition_participants: Set[ValidatorIndex] = set()
        for attestation in transition_attestations:
            participants = get_attesting_indices(state, attestation.data, attestation.aggregation_bits)
            transition_participants = transition_participants.union(participants)

        enough_online_stake = (
            get_total_balance(state, online_indices.intersection(transition_participants)) * 3 >=
            get_total_balance(state, online_indices.intersection(committee)) * 2
        )
        # If not enough stake, try next transition root
        if not enough_online_stake:
            continue

        # Attestation <-> shard transition consistency
        assert shard_transition_root == hash_tree_root(shard_transition)

        # Check `shard_head_root` of the winning root
        last_offset_index = len(shard_transition.shard_states) - 1
        shard_head_root = shard_transition.shard_states[last_offset_index].latest_block_root
        for attestation in transition_attestations:
            assert attestation.data.shard_head_root == shard_head_root

        # Apply transition
        apply_shard_transition(state, shard, shard_transition)
        # Apply proposer reward and cost
        beacon_proposer_index = get_beacon_proposer_index(state)
        estimated_attester_reward = sum([get_base_reward(state, attester) for attester in transition_participants])
        proposer_reward = Gwei(estimated_attester_reward // PROPOSER_REWARD_QUOTIENT)
        increase_balance(state, beacon_proposer_index, proposer_reward)
        states_slots_lengths = zip(
            shard_transition.shard_states,
            get_offset_slots(state, shard),
            shard_transition.shard_block_lengths
        )
        for shard_state, slot, length in states_slots_lengths:
            proposer_index = get_shard_proposer_index(state, slot, shard)
            decrease_balance(state, proposer_index, shard_state.gasprice * length)

        # Return winning transition root
        return shard_transition_root

    # No winning transition root, ensure empty and return empty root
    assert shard_transition == ShardTransition()
    return Root()
```

###### `process_crosslinks`

```python
def process_crosslinks(state: BeaconState,
                       shard_transitions: Sequence[ShardTransition],
                       attestations: Sequence[Attestation]) -> None:
    on_time_attestation_slot = compute_previous_slot(state.slot)
    committee_count = get_committee_count_per_slot(state, compute_epoch_at_slot(on_time_attestation_slot))
    for committee_index in map(CommitteeIndex, range(committee_count)):
        # All attestations in the block for this committee/shard and current slot
        shard = compute_shard_from_committee_index(state, committee_index, on_time_attestation_slot)
        # Since the attestations are validated, all `shard_attestations` satisfy `attestation.data.shard == shard`
        shard_attestations = [
            attestation for attestation in attestations
            if is_on_time_attestation(state, attestation.data) and attestation.data.index == committee_index
        ]
        winning_root = process_crosslink_for_shard(
            state, committee_index, shard_transitions[shard], shard_attestations
        )
        if winning_root != Root():
            # Mark relevant pending attestations as creating a successful crosslink
            for pending_attestation in state.current_epoch_attestations:
                if is_winning_attestation(state, pending_attestation, committee_index, winning_root):
                    pending_attestation.crosslink_success = True
```

###### `verify_empty_shard_transition`

```python
def verify_empty_shard_transition(state: BeaconState, shard_transitions: Sequence[ShardTransition]) -> bool:
    """
    Verify that a `shard_transition` in a block is empty if an attestation was not processed for it.
    """
    for shard in range(get_active_shard_count(state)):
        if state.shard_states[shard].slot != compute_previous_slot(state.slot):
            if shard_transitions[shard] != ShardTransition():
                return False
    return True
```

###### `process_shard_transitions`

```python
def process_shard_transitions(state: BeaconState,
                              shard_transitions: Sequence[ShardTransition],
                              attestations: Sequence[Attestation]) -> None:
    # Process crosslinks
    process_crosslinks(state, shard_transitions, attestations)
    # Verify the empty proposal shard states
    assert verify_empty_shard_transition(state, shard_transitions)
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

#### Phase 1 final updates

```python
def process_phase_1_final_updates(state: BeaconState) -> None:
    process_custody_final_updates(state)
    process_online_tracking(state)
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
    for pending_attestation in state.current_epoch_attestations + state.previous_epoch_attestations:
        for index in get_attesting_indices(state, pending_attestation.data, pending_attestation.aggregation_bits):
            state.online_countdown[index] = ONLINE_PERIOD
```

#### Light client committee updates

```python
def process_light_client_committee_updates(state: BeaconState) -> None:
    """
    Update light client committees.
    """
    if get_current_epoch(state) % LIGHT_CLIENT_COMMITTEE_PERIOD == 0:
        state.current_light_committee = state.next_light_committee
        new_committee = get_light_client_committee(state, get_current_epoch(state) + LIGHT_CLIENT_COMMITTEE_PERIOD)
        state.next_light_committee = committee_to_compact_committee(state, new_committee)
```
