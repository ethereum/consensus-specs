# Ethereum 2.0 Phase 1 -- Crosslinks and Shard Data

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Crosslinks and Shard Data](#ethereum-20-phase-1----crosslinks-and-shard-data)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Configuration](#configuration)
        - [Misc](#misc)
    - [Containers](#containers)
        - [`ShardBlockWrapper`](#shardblockwrapper)
        - [`ShardSignableHeader`](#shardsignedheader)
        - [`ShardState`](#shardstate)
        - [`AttestationData`](#attestationdata)
        - [`ShardTransition`](#shardtransition)
        - [`Attestation`](#attestation)
        - [`AttestationAndCommittee`](#attestationandcommittee)
        - [`CompactCommittee`](#compactcommittee)
        - [`AttestationCustodyBitWrapper`](#attestationcustodybitwrapper)
        - [`PendingAttestation`](#pendingattestation)
    - [Helpers](#helpers)
        - [`get_online_validators`](#get_online_validators)
        - [`pack_compact_validator`](#pack_compact_validator)
        - [`committee_to_compact_committee`](#committee_to_compact_committee)
        - [`get_light_client_committee`](#get_light_client_committee)
        - [`get_indexed_attestation`](#get_indexed_attestation)
        - [`get_updated_gasprice`](#get_updated_gasprice)
        - [`is_valid_indexed_attestation`](#is_valid_indexed_attestation)
        - [`get_attestation_shard`](#get_attestation_shard)
    - [Beacon Chain Changes](#beacon-chain-changes)
        - [New beacon state fields](#new-beacon-state-fields)
        - [New beacon block data fields](#new-beacon-block-data-fields)
        - [Attestation processing](#attestation-processing)
            - [`validate_attestation`](#validate_attestation)
            - [`apply_shard_transition`](#apply_shard_transition)
            - [`process_attestations`](#process_attestations)
        - [Misc block post-processing](#misc-block-post-processing)
        - [Light client processing](#light-client-processing)
        - [Epoch transition](#epoch-transition)
    - [Fraud proofs](#fraud-proofs)
    - [Shard state transition function](#shard-state-transition-function)
    - [Honest committee member behavior](#honest-committee-member-behavior)

<!-- /TOC -->

## Introduction

This document describes the shard transition function (data layer only) and the shard fork choice rule as part of Phase 1 of Ethereum 2.0.

## Configuration

### Misc

| Name | Value | Unit | Duration |
| - | - | - | - | 
| `MAX_SHARDS` | `2**10` (= 1024) |
| `ACTIVE_SHARDS` | `2**6` (= 64) |
| `ONLINE_PERIOD` | `2**3` (= 8) | epochs | ~51 min |
| `LIGHT_CLIENT_COMMITTEE_SIZE` | `2**7` (= 128) |
| `LIGHT_CLIENT_COMMITTEE_PERIOD` | `2**8` (= 256) | epochs | ~27 hours |
| `SHARD_BLOCK_CHUNK_SIZE` | `2**18` (= 262,144) | |
| `MAX_SHARD_BLOCK_CHUNKS` | `2**2` (= 4) | |
| `BLOCK_SIZE_TARGET` | `3 * 2**16` (= 196,608) | |
| `SHARD_BLOCK_OFFSETS` | `[1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]` | |
| `MAX_SHARD_BLOCKS_PER_ATTESTATION` | `len(SHARD_BLOCK_OFFSETS)` | |
| `EMPTY_CHUNK_ROOT` | `hash_tree_root(BytesN[SHARD_BLOCK_CHUNK_SIZE]())` | |
| `MAX_GASPRICE` | `2**14` (= 16,384) | Gwei | |
| `MIN_GASPRICE` | `2**5` (= 32) | Gwei | |
| `GASPRICE_ADJUSTMENT_COEFFICIENT` | `2**3` (= 8) | |
| `DOMAIN_SHARD_LIGHT_CLIENT` | `192` | |
| `DOMAIN_SHARD_PROPOSAL` | `193` | |

## Containers

### `ShardBlockWrapper`

_Wrapper for being broadcasted over the network._

```python
class ShardBlockWrapper(Container):
    shard_parent_root: Hash
    beacon_parent_root: Hash
    slot: Slot
    body: BytesN[SHARD_BLOCK_CHUNK_SIZE]
    signature: BLSSignature
```

### `ShardSignableHeader`

```python
class ShardSignableHeader(Container):
    shard_parent_root: Hash
    beacon_parent_root: Hash
    slot: Slot
    body_root: Hash
```

### `ShardState`

```python
class ShardState(Container):
    slot: Slot
    gasprice: Gwei
    data: Hash
    latest_block_root: Hash
```

### `AttestationData`

```python
class AttestationData(Container):
    slot: Slot
    index: CommitteeIndex
    # LMD GHOST vote
    beacon_block_root: Hash
    # FFG vote
    source: Checkpoint
    target: Checkpoint
    # Current-slot shard block root
    head_shard_root: Hash
    # Shard transition root
    shard_transition_root: Hash
```

### `ShardTransition`

```python
class ShardTransition(Container):
    # Starting from slot
    start_slot: Slot
    # Shard block lengths
    shard_block_lengths: List[uint64, MAX_SHARD_BLOCKS_PER_ATTESTATION]
    # Shard data roots
    shard_data_roots: List[List[Hash, MAX_SHARD_BLOCK_CHUNKS], MAX_SHARD_BLOCKS_PER_ATTESTATION]
    # Intermediate shard states
    shard_states: List[ShardState, MAX_SHARD_BLOCKS_PER_ATTESTATION]
    # Proposer signature aggregate
    proposer_signature_aggregate: BLSSignature
```

### `Attestation`

```python
class Attestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    custody_bits: List[Bitlist[MAX_VALIDATORS_PER_COMMITTEE], MAX_SHARD_BLOCKS_PER_ATTESTATION]
    signature: BLSSignature
```

### `AttestationAndCommittee`

```python
class AttestationAndCommittee(Container):
    committee: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE]
    attestation: Attestation
```

### `CompactCommittee`

```python
class CompactCommittee(Container):
    pubkeys: List[BLSPubkey, MAX_VALIDATORS_PER_COMMITTEE]
    compact_validators: List[uint64, MAX_VALIDATORS_PER_COMMITTEE]
```

### `AttestationCustodyBitWrapper`

```python
class AttestationCustodyBitWrapper(Container):
    attestation_root: Hash
    block_index: uint64
    bit: bool
```

### `PendingAttestation`

```python
class PendingAttestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    inclusion_delay: Slot
    proposer_index: ValidatorIndex
    crosslink_success: bool
```

## Helpers

### `get_online_validators`

```python
def get_online_indices(state: BeaconState) -> Set[ValidatorIndex]:
    active_validators = get_active_validator_indices(state, get_current_epoch(state))
    return set([i for i in active_validators if state.online_countdown[i] != 0])
```

### `pack_compact_validator`

```python
def pack_compact_validator(index: int, slashed: bool, balance_in_increments: int) -> int:
    """
    Creates a compact validator object representing index, slashed status, and compressed balance.
    Takes as input balance-in-increments (// EFFECTIVE_BALANCE_INCREMENT) to preserve symmetry with
    the unpacking function.
    """
    return (index << 16) + (slashed << 15) + balance_in_increments
```

### `committee_to_compact_committee`

```python
def committee_to_compact_committee(state: BeaconState, committee: Sequence[ValidatorIndex]) -> CompactCommittee:
    """
    Given a state and a list of validator indices, outputs the CompactCommittee representing them.
    """
    validators = [state.validators[i] for i in committee]
    compact_validators = [
        pack_compact_validator(i, v.slashed, v.effective_balance // EFFECTIVE_BALANCE_INCREMENT)
        for i, v in zip(committee, validators)
    ]
    pubkeys = [v.pubkey for v in validators]
    return CompactCommittee(pubkeys=pubkeys, compact_validators=compact_validators)
```

### `get_light_client_committee`

```python
def get_light_client_committee(beacon_state: BeaconState, epoch: Epoch) -> Sequence[ValidatorIndex]:
    source_epoch = epoch - epoch % LIGHT_CLIENT_COMMITTEE_PERIOD 
    if source_epoch > 0:
        source_epoch -= LIGHT_CLIENT_COMMITTEE_PERIOD
    active_validator_indices = get_active_validator_indices(beacon_state, source_epoch)
    seed = get_seed(beacon_state, source_epoch, DOMAIN_SHARD_LIGHT_CLIENT)
    return compute_committee(active_validator_indices, seed, 0, ACTIVE_SHARDS)[:TARGET_COMMITTEE_SIZE]
```

### `get_indexed_attestation`

```python
def get_indexed_attestation(beacon_state: BeaconState, attestation: Attestation) -> AttestationAndCommittee:
    committee = get_beacon_committee(beacon_state, attestation.data.slot, attestation.data.index)
    return AttestationAndCommittee(committee, attestation)
```

### `get_updated_gasprice`

```python
def get_updated_gasprice(prev_gasprice: Gwei, length: uint8) -> Gwei:
    if length > BLOCK_SIZE_TARGET:
        delta = prev_gasprice * (length - BLOCK_SIZE_TARGET) // BLOCK_SIZE_TARGET // GASPRICE_ADJUSTMENT_COEFFICIENT
        return min(prev_gasprice + delta, MAX_GASPRICE)
    else:
        delta = prev_gasprice * (BLOCK_SIZE_TARGET - length) // BLOCK_SIZE_TARGET // GASPRICE_ADJUSTMENT_COEFFICIENT
        return max(prev_gasprice, MIN_GASPRICE + delta) - delta
```

### `is_valid_indexed_attestation`

```python
def is_valid_indexed_attestation(state: BeaconState, indexed_attestation: AttestationAndCommittee) -> bool:
    """
    Check if ``indexed_attestation`` has valid indices and signature.
    """

    # Verify aggregate signature
    all_pubkeys = []
    all_message_hashes = []
    aggregation_bits = indexed_attestation.attestation.aggregation_bits
    assert len(aggregation_bits) == len(indexed_attestation.committee)
    for i, custody_bits in enumerate(indexed_attestation.attestation.custody_bits):
        assert len(custody_bits) == len(indexed_attestation.committee)
        for participant, abit, cbit in zip(indexed_attestation.committee, aggregation_bits, custody_bits):
            if abit:
                all_pubkeys.append(state.validators[participant].pubkey)
                # Note: only 2N distinct message hashes
                all_message_hashes.append(hash_tree_root(
                    AttestationCustodyBitWrapper(hash_tree_root(indexed_attestation.data), i, cbit)
                ))
            else:
                assert cbit == False
        
    return bls_verify_multiple(
        pubkeys=all_pubkeys,
        message_hashes=all_message_hashes,
        signature=indexed_attestation.signature,
        domain=get_domain(state, DOMAIN_BEACON_ATTESTER, indexed_attestation.data.target.epoch),
    )
```

### `get_shard`

```python
def get_shard(state: BeaconState, attestation: Attestation) -> Shard:
    return Shard((attestation.data.index + get_start_shard(state, data.slot)) % ACTIVE_SHARDS)
```

### `get_offset_slots`

```python
def get_offset_slots(state: BeaconState, start_slot: Slot) -> Sequence[Slot]:
    return [start_slot + x for x in SHARD_BLOCK_OFFSETS if start_slot + x < state.slot]
```

### `chunks_to_body_root`

```python
def chunks_to_body_root(chunks):
    return hash_tree_root(chunks + [EMPTY_CHUNK_ROOT] * (MAX_SHARD_BLOCK_CHUNKS - len(chunks)))
```

## Beacon Chain Changes

### New beacon state fields

```python
    shard_states: Vector[ShardState, MAX_SHARDS]
    online_countdown: Bytes[VALIDATOR_REGISTRY_LIMIT]
    current_light_committee: CompactCommittee
    next_light_committee: CompactCommittee
```

### New beacon block data fields

```python
    shard_transitions: Vector[ShardTransition, MAX_SHARDS]
    light_client_signature_bitfield: Bitlist[LIGHT_CLIENT_COMMITTEE_SIZE]
    light_client_signature: BLSSignature
```

### Attestation processing

#### `validate_attestation`

```python
def validate_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.index < ACTIVE_SHARDS
    shard = get_shard(state, attestation)
    proposer_index = get_beacon_proposer_index(state)

    # Signature check
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))
    # Type 1: on-time attestations
    if attestation.custody_bits != []:
        # Correct slot
        assert data.slot == state.slot
        # Correct data root count
        assert len(attestation.custody_bits) == len(get_offset_slots(state, state.shard_next_slots[shard]))
        # Correct parent block root
        assert data.beacon_block_root == get_block_root_at_slot(state, state.slot - 1)
    # Type 2: delayed attestations
    else:
        assert state.slot - compute_start_slot_at_epoch(slot_to_epoch(data.slot)) < EPOCH_LENGTH
        assert data.shard_transition_root == Hash()
```

#### `apply_shard_transition`

```python
def apply_shard_transition(state: BeaconState, shard: Shard, transition: ShardTransition) -> None:
    # Slot the attestation starts counting from
    start_slot = state.shard_next_slots[shard]

    # Correct data root count
    offset_slots = get_offset_slots(state, start_slot)
    assert len(transition.shard_data_roots) == len(transition.shard_states) == len(transition.shard_block_lengths) == len(offset_slots)
    assert transition.start_slot == start_slot

    # Reonstruct shard headers
    headers = []
    proposers = []
    shard_parent_root = state.shard_states[shard].latest_block_root
    for i in range(len(offset_slots)):
        if any(transition.shard_data_roots):
            headers.append(ShardSignableHeader(
                shard_parent_root=shard_parent_root,
                parent_hash=get_block_root_at_slot(state, state.slot-1),
                slot=offset_slots[i],
                body_root=chunks_to_body_root(transition.shard_data_roots[i])
            ))
            proposers.append(get_shard_proposer(state, shard, offset_slots[i]))
            shard_parent_root = hash_tree_root(headers[-1])

    # Verify correct calculation of gas prices and slots and chunk roots
    prev_gasprice = state.shard_states[shard].gasprice
    for i in range(len(offset_slots)):
        shard_state, block_length, chunks = transition.shard_states[i], transition.shard_block_lengths[i], transition.shard_data_roots[i]
        assert shard_state.gasprice == get_updated_gasprice(prev_gasprice, block_length)
        assert shard_state.slot == offset_slots[i]
        assert len(chunks) == block_length // SHARD_BLOCK_CHUNK_SIZE
        prev_gasprice = shard_state.gasprice

    # Verify combined proposer signature
    assert bls_verify_multiple(
        pubkeys=[state.validators[proposer].pubkey for proposer in proposers],
        message_hashes=[hash_tree_root(header) for header in headers],
        signature=transition.proposer_signature_aggregate,
        domain=DOMAIN_SHARD_PROPOSAL
    )

    # Save updated state
    state.shard_states[shard] = transition.shard_states[-1]
    state.shard_states[shard].slot = state.slot - 1
```

#### `process_attestations`

```python
def process_attestations(state: BeaconState, block: BeaconBlock, attestations: Sequence[Attestation]) -> None:
    pending_attestations = []
    # Basic validation
    for attestation in attestations:
       validate_attestation(state, attestation)
    # Process crosslinks
    online_indices = get_online_indices(state)
    winners = set()
    for shard in range(ACTIVE_SHARDS):
        success = False
        # All attestations in the block for this shard
        this_shard_attestations = [attestation for attestation in attestations if get_shard(state, attestation) == shard and attestation.data.slot == state.slot]
        # The committee for this shard
        this_shard_committee = get_beacon_committee(state, get_current_epoch(state), shard)
        # Loop over all shard transition roots
        for shard_transition_root in sorted(set([attestation.data.shard_transition_root for attestation in this_shard_attestations])):
            all_participants = set()
            participating_attestations = []
            for attestation in this_shard_attestations:
                participating_attestations.append(attestation)
                if attestation.data.shard_transition_root == shard_transition_root:
                    all_participants = all_participants.union(get_attesting_indices(state, attestation.data, attestation.aggregation_bits))
            if (
                get_total_balance(state, online_indices.intersection(all_participants)) * 3 >=
                get_total_balance(state, online_indices.intersection(this_shard_committee)) * 2
                and success is False
            ):
                # Attestation <-> shard transition consistency
                assert shard_transition_root == hash_tree_root(block.shard_transition)
                assert attestation.data.head_shard_root == chunks_to_body_root(block.shard_transition.shard_data_roots[-1])
                # Apply transition
                apply_shard_transition(state, shard, block.shard_transition)
                # Apply proposer reward and cost
                estimated_attester_reward = sum([get_base_reward(state, attester) for attester in all_participants])
                increase_balance(state, proposer, estimated_attester_reward // PROPOSER_REWARD_COEFFICIENT)
                for shard_state, slot, length in zip(block.shard_transition.shard_states, offset_slots, block.shard_transition.shard_block_lengths):
                    decrease_balance(state, get_shard_proposer(state, shard, slot), shard_state.gasprice * length)
                winners.add((shard, shard_transition_root))
                success = True
        if not success:
            assert block.shard_transitions[shard] == ShardTransition()
    for attestation in attestations:
        pending_attestation = PendingAttestation(
            aggregation_bits=attestation.aggregation_bits,
            data=attestation.data,
            inclusion_delay=state.slot - data.slot,
            crosslink_success=(get_shard(state, attestation), attestation.shard_transition_root) in winners and attestation.data.slot == state.slot,
            proposer_index=proposer_index
        )
        if attestation.data.target.epoch == get_current_epoch(state):
            assert attestation.data.source == state.current_justified_checkpoint
            state.current_epoch_attestations.append(pending_attestation)
        else:
            assert attestation.data.source == state.previous_justified_checkpoint
            state.previous_epoch_attestations.append(pending_attestation)
```

### Misc block post-processing

```python
def verify_shard_transition_false_positives(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that a `shard_transition` in a block is empty if an attestation was not processed for it
    for shard in range(MAX_SHARDS):
        if state.shard_states[shard].slot != state.slot - 1:
            assert block.shard_transition[shard] == ShardTransition()
```

### Light client processing

```python
def process_light_client_signatures(state: BeaconState, block: BeaconBlock) -> None:
    committee = get_light_client_committee(state, get_current_epoch(state))
    assert len(block.light_client_signature_bitfield) == len(committee)
    total_reward = Gwei(0)
    signer_keys = []
    for i, bit in enumerate(block.light_client_signature_bitfield):
        if bit:
            signer_keys.append(state.validators[committee[i]].pubkey)
            increase_balance(state, committee[i], get_base_reward(state, committee[i]))
            total_reward += get_base_reward(state, committee[i])

    increase_balance(state, get_beacon_proposer_index(state), total_reward // PROPOSER_REWARD_COEFFICIENT)
    
    assert bls_verify(
        pubkey=bls_aggregate_pubkeys(signer_keys),
        message_hash=get_block_root_at_slot(state, state.slot - 1),
        signature=block.light_client_signature,
        domain=DOMAIN_LIGHT_CLIENT
    )
```

### Epoch transition

```python
def phase_1_epoch_transition(state: BeaconState) -> None:
    # Slowly remove validators from the "online" set if they do not show up
    for index in range(len(state.validators)):
        if state.online_countdown[index] != 0:
            state.online_countdown[index] = state.online_countdown[index] - 1
    
    # Update light client committees
    if get_current_epoch(state) % LIGHT_CLIENT_COMMITTEE_PERIOD == 0:
        state.current_light_committee = state.next_light_committee
        new_committee = get_light_client_committee(state, get_current_epoch(state) + LIGHT_CLIENT_COMMITTEE_PERIOD)
        state.next_light_committee = committee_to_compact_committee(state, new_committee)

    # Process pending attestations
    for pending_attestation in state.current_epoch_attestations + state.previous_epoch_attestations:
        for index in get_attesting_indices(state, pending_attestation.data, pending_attestation.aggregation_bits):
            state.online_countdown[index] = ONLINE_PERIOD
```

## Fraud proofs

TODO. The intent is to have a single universal fraud proof type, which contains the following parts:

1. An on-time attestation on some `shard` signing a `ShardTransition`
2. An index `i` of a particular position to focus on
3. The `ShardTransition` itself
4. The full body of the block
5. A Merkle proof to the `shard_states` in the parent block the attestation is referencing

The proof verifies that one of the two conditions is false:

1. `custody_bits[i][j] != generate_custody_bit(subkey, block_contents)` for any `j`
2. `execute_state_transition(shard, slot, transition.shard_states[i-1].data, hash_tree_root(parent), get_shard_proposer(state, shard, slot), block_contents) != transition.shard_states[i].data` (if `i=0` then instead use `parent.shard_states[shard][-1].data`)

## Shard state transition function

```python
def shard_state_transition(shard: Shard, slot: Slot, pre_state: Hash, previous_beacon_root: Hash, proposer_pubkey: BLSPubkey, block_data: BytesN[MAX_SHARD_BLOCK_CHUNKS * SHARD_BLOCK_CHUNK_SIZE]) -> Hash:
    # We will add something more substantive in phase 2
    return hash(pre_state + hash_tree_root(previous_beacon_root) + hash_tree_root(block_data))
```

## Honest committee member behavior

Suppose you are a committee member on shard `shard` at slot `current_slot`. Let `state` be the head beacon state you are building on, and let `QUARTER_PERIOD = SECONDS_PER_SLOT // 4`. `2 * QUARTER_PERIOD` seconds into slot `slot`, run the following procedure:

* Initialize `proposals = []`, `shard_states = []`, `shard_state = state.shard_states[shard][-1]`, `start_slot = shard_state.slot`.
* For `slot in get_offset_slots(state, start_slot)`, do the following:
    * Look for all valid proposals for `slot`; that is, a Bytes `proposal` where `shard_state_transition(shard, slot, shard_state, get_block_root_at_slot(state, state.slot - 1), get_shard_proposer(state, shard, slot), proposal)` returns a result and does not throw an exception. Let `choices` be the set of non-empty valid proposals you discover.
    * If `len(choices) == 0`, do `proposals.append(make_empty_proposal(shard_state, slot))`
    * If `len(choices) == 1`, do `proposals.append(choices[0])`
    * If `len(choices) > 1`, let `winning_proposal` be the proposal with the largest number of total attestations from slots in `state.shard_next_slots[shard]....slot-1` supporting it or any of its descendants, breaking ties by choosing the first proposal locally seen. Do `proposals.append(winning_proposal)`.
    * If `proposals[-1]` is NOT an empty proposal, set `shard_state = shard_state_transition(shard, slot, shard_state, get_block_root_at_slot(state, state.slot - 1), get_shard_proposer(state, shard, slot), proposals[-1])` and do `shard_states.append(shard_state)`. If it is an empty proposal, leave `shard_state` unchanged.

Make an attestation using `shard_data_roots = [hash_tree_root(proposal) for proposal in proposals]` and `shard_state_roots = shard_states`.
