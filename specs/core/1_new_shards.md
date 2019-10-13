# Ethereum 2.0 Phase 1 -- Crosslinks and Shard Data

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Shard Data Chains](#ethereum-20-phase-1----shard-data-chains)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Configuration](#configuration)
        - [Misc](#misc)
    - [Containers](#containers)
    - [Helpers](#helpers)
    - [Beacon Chain Changes](#beacon-chain-changes)
        - [New state variables](#new-state-variables)
        - [New block data structures](#new-block-data-structures)
        - [Attestation processing](#attestation-processing)
        - [Light client signature processing)(#light-client-signature-processing)
        - [Epoch transition](#epoch-transition)
        - [Fraud proofs](#fraud-proofs)
    - [Honest persistent committee member behavior](#honest-persistent-committee-member-behavior)

<!-- /TOC -->

## Introduction

This document describes the shard transition function (data layer only) and the shard fork choice rule as part of Phase 1 of Ethereum 2.0.

## Configuration

### Misc

| Name | Value | Unit | Duration |
| - | - | - | - | 
| `MAX_SHARDS` | `2**10` (= 1024) |
| `ACTIVE_SHARDS` | `2**6` (= 64) |
| `SHARD_ROOT_HISTORY_LENGTH` | `2**15` (= 32,768) |
| `MAX_CATCHUP_RATIO` | `2**2` (= 4) |
| `ONLINE_PERIOD` | `2**3` (= 8) | epochs | ~51 min |
| `LIGHT_CLIENT_COMMITTEE_SIZE` | `2**7` (= 128) |
| `LIGHT_CLIENT_COMMITTEE_PERIOD` | `2**8` (= 256) | epochs | ~29 hours |

## Containers

### `AttestationData`

```python
class AttestationData(Container):
    # Slot
    slot: Slot
    # LMD GHOST vote
    beacon_block_root: Hash
    # FFG vote
    source: Checkpoint
    target: Checkpoint
    # Shard data roots
    shard_data_roots: List[Hash, MAX_CATCHUP_RATIO * MAX_SHARDS]
    # Intermediate state roots
    shard_state_roots: List[Hash, MAX_CATCHUP_RATIO * MAX_SHARDS]
    # Index
    index: uint64
```

### `Attestation`

```python
class Attestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    custody_bits: List[Bitlist[MAX_VALIDATORS_PER_COMMITTEE], MAX_CATCHUP_RATIO * MAX_SHARDS]
    signature: BLSSignature
```

### `CompactCommittee`

```python
class CompactCommittee(Container):
    pubkeys: List[BLSPubkey, MAX_VALIDATORS_PER_COMMITTEE]
    compact_validators: List[uint64, MAX_VALIDATORS_PER_COMMITTEE]
```

## Helpers

### `get_online_validators`

```python
def get_online_indices(state: BeaconState) -> Set[ValidatorIndex]:
    active_validators = get_active_validator_indices(state, get_current_epoch(state))
    return set([i for i in active_validators if state.online_countdown[i] != 0])
```

### `get_shard_state_root`

```python
def get_shard_state_root(state: BeaconState, shard: Shard) -> Hash:
    return state.shard_state_roots[shard][-1]
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

### `unpack_compact_validator`

```python
def unpack_compact_validator(compact_validator: int) -> Tuple[int, bool, int]:
    """
    Returns validator index, slashed, balance // EFFECTIVE_BALANCE_INCREMENT
    """
    return compact_validator >> 16, bool((compact_validator >> 15) % 2), compact_validator & (2**15 - 1)
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

## Beacon Chain Changes

### New state variables

```python
    shard_state_roots: Vector[List[Hash, MAX_CATCHUP_RATIO * MAX_SHARDS], MAX_SHARDS]
    shard_next_slot: Vector[Slot, MAX_SHARDS]
    online_countdown: Bytes[VALIDATOR_REGISTRY_LIMIT]
    current_light_committee: CompactCommittee
    next_light_committee: CompactCommittee
```

### New block data structures

```python
    light_client_signature_bitfield: Bitlist[LIGHT_CLIENT_COMMITTEE_SIZE]
    light_client_signature: BLSSignature
```

### Attestation processing

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.index < ACTIVE_SHARDS
    shard = (data.index + get_start_shard(state, data.slot)) % ACTIVE_SHARDS

    # Signature check
    committee = get_crosslink_committee(state, get_current_epoch(state), shard)
    for bits in attestation.custody_bits + [attestation.aggregation_bits]:
        assert bits == len(committee)
    # Check signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))
    # Get attesting indices
    attesting_indices = get_attesting_indices(state, attestation.data, attestation.aggregation_bits)
    
    # Type 1: on-time attestations
    if data.custody_bits != []:
        # Correct start slot
        assert data.slot == state.shard_next_slot[shard]
        # Correct data root count
        max_catchup = ACTIVE_SHARDS * MAX_CATCHUP_RATIO // get_committee_count(state, state.slot)
        assert len(data.shard_data_roots) == len(attestation.custody_bits) == len(data.shard_state_roots) == min(state.slot - data.slot, max_catchup)
        # Correct parent block root
        assert data.beacon_block_root == get_block_root_at_slot(state, state.slot - 1)
        # Apply
        online_indices = get_online_indices(state)
        if get_total_balance(state, online_indices.intersection(attesting_indices)) * 3 >= get_total_balance(state, online_indices) * 2:
            state.shard_state_roots[shard] = data.shard_state_roots
            state.shard_next_slot[shard] += len(data.shard_data_roots)
        
    # Type 2: delayed attestations
    else:
        assert slot_to_epoch(data.slot) in (get_current_epoch(state), get_previous_epoch(state))
        assert len(data.shard_data_roots) == len(data.intermediate_state_roots) == 0

    for index in attesting_indices:
        online_countdown[index] = ONLINE_PERIOD

    pending_attestation = PendingAttestation(
        slot=data.slot,
        shard=shard,
        aggregation_bits=attestation.aggregation_bits,
        inclusion_delay=state.slot - attestation_slot,
        proposer_index=get_beacon_proposer_index(state),
    )

    if data.target.epoch == get_current_epoch(state):
        assert data.source == state.current_justified_checkpoint
        state.current_epoch_attestations.append(pending_attestation)
    else:
        assert data.source == state.previous_justified_checkpoint
        state.previous_epoch_attestations.append(pending_attestation)
```

Check the length of attestations using `len(block.attestations) <= 4 * get_committee_count(state, state.slot)`.

### Light client processing

```python
signer_validators = []
signer_keys = []
for i, bit in enumerate(block.light_client_signature_bitfield):
    if bit:
        signer_keys.append(state.current_light_committee.pubkeys[i])
        index, _, _ = unpack_compact_validator(state.current_light_committee.compact_validators[i])
        signer_validators.append(index)

assert bls_verify(
    pubkey=bls_aggregate_pubkeys(signer_keys),
    message_hash=get_block_root_at_slot(state, state.slot - 1),
    signature=block.light_client_signature,
    domain=DOMAIN_LIGHT_CLIENT
)
```

### Epoch transition

```python
# Slowly remove validators from the "online" set if they do not show up
for index in range(len(state.validators)):
    if state.online_countdown[index] != 0:
        state.online_countdown[index] = state.online_countdown[index] - 1

# Update light client committees
if get_current_epoch(state) % LIGHT_CLIENT_COMMITTEE_PERIOD == 0:
    state.current_light_committee = state.next_light_committee
    seed = get_seed(state, get_current_epoch(state), DOMAIN_LIGHT_CLIENT)
    active_indices = get_active_validator_indices(state, get_current_epoch(state))
    committee = [active_indices[compute_shuffled_index(ValidatorIndex(i), len(active_indices), seed)] for i in range(LIGHT_CLIENT_COMMITTEE_SIZE)]
    state.next_light_committee = committee_to_compact_committee(state, committee)
```

### Fraud proofs

TODO. The intent is to have a single universal fraud proof type, which contains (i) an on-time attestation on shard `s` signing a set of `data_roots`, (ii) an index `i` of a particular data root to focus on, (iii) the full contents of the i'th data, (iii) a Merkle proof to the `shard_state_roots` in the parent block the attestation is referencing, and which then verifies that one of the two conditions is false:

* `custody_bits[i][j] != generate_custody_bit(subkey, block_contents)` for any `j`
* `execute_state_transition(slot, shard, attestation.shard_state_roots[i-1], parent.shard_state_roots, block_contents) != shard_state_roots[i]` (if `i=0` then instead use `parent.shard_state_roots[s][-1]`)

For phase 1, we will use a simple state transition function:

* Check that `data[:32] == prev_state_root`
* Check that `bls_verify(get_shard_proposer(state, slot, shard), hash_tree_root(data[-96:]), BLSSignature(data[-96:]), BLOCK_SIGNATURE_DOMAIN)`
* Output the new state root: `hash_tree_root(prev_state_root, other_prev_state_roots, data)`

## Honest persistent committee member behavior

Suppose you are a persistent committee member on shard `i` at slot `s`. Suppose `state.shard_next_slots[i] = s-1` ("the happy case"). In this case, you look for a valid proposal that satisfies the checks in the state transition function above, and if you see such a proposal `data` with post-state `post_state`, make an attestation with `shard_data_roots = [hash_tree_root(data)]` and `shard_state_roots = [post_state]`. If you do not find such a proposal, make an attestation using the "default empty proposal", `data = prev_state_root + b'\x00' * 96`.

Now suppose `state.shard_next_slots[i] = s-k` for `k>1`. Then, initialize `data = []`, `states = []`, `state = state.shard_state_roots[i]`. For `slot in (state.shard_next_slot, min(state.shard_next_slot + max_catchup, s))`, do:

* Look for all valid proposals for `slot` whose first 32 bytes equal to `state`. If there are none, add a default empty proposal to `data`. If there is one such proposal `p`, add `p` to `data`. If there is more than one, select the one with the largest number of total attestations supporting it or its descendants, and add it to `data`.
* Set `state` to the state after processing the proposal just added to `data`; append it to `states`

Make an attestation using `shard_data_roots = data` and `shard_state_roots = states`.
