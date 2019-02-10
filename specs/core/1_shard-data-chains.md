# Ethereum 2.0 Phase 1 -- Shard Data Chains

###### tags: `spec`, `eth2.0`, `casper`, `sharding`

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the [Python proof-of-concept implementation](https://github.com/ethereum/beacon_chain).

### Introduction

This document represents the specification for Phase 1 of Ethereum 2.0 -- Shard Data Chains. Phase 1 depends on the implementation of [Phase 0 -- The Beacon Chain](0_beacon-chain.md).

Ethereum 2.0 consists of a central beacon chain along with `SHARD_COUNT` shard chains. Phase 1 is primarily concerned with the construction, validity, and consensus on the _data_ of these shard chains. Phase 1 does not specify shard chain state execution or account balances. This is left for future phases.

### Terminology

### Constants

Phase 1 depends upon all of the constants defined in [Phase 0](0_beacon-chain.md#constants) in addition to the following:

| Constant                      | Value            | Unit   | Approximation |
|-------------------------------|------------------|--------|---------------|
| `SHARD_CHUNK_SIZE`            | 2**5 (= 32)      | bytes  |               |
| `SHARD_BLOCK_SIZE`            | 2**14 (= 16,384) | bytes  |               |
| `CROSSLINK_LOOKBACK`          | 2**5 (= 32)      | slots  |               |
| `PERSISTENT_COMMITTEE_PERIOD` | 2**11 (= 2,048)  | epochs | 9 days        |

### Flags, domains, etc.

| Constant               | Value           |
|------------------------|-----------------|
| `SHARD_PROPOSER_DOMAIN`| 129             |
| `SHARD_ATTESTER_DOMAIN`| 130             |

## Helper functions

#### get_split_offset

````python
def get_split_offset(list_size: int, chunks: int, index: int) -> int:
  """
  Returns a value such that for a list L, chunk count k and index i,
  split(L, k)[i] == L[get_split_offset(len(L), k, i): get_split_offset(len(L), k+1, i)]
  """
  return (len(list_size) * index) // chunks
````

#### get_persistent_committee

```python
def get_persistent_commmitee(state: BeaconState,
                             shard: ShardNumber,
                             epoch: EpochNumber) -> List[ValidatorIndex]:
    """
    Returns the persistent committee for the given shard at the given epoch
    """
                  
    earlier_committee_start = epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD * 2
    earlier_validator_set = get_active_validator_indices(state.validators, earlier_committee_start)
    earlier_seed = generate_seed(state, earlier_committee_start)
    earlier_start_offset = get_split_offset(len(earlier_validator_set), SHARD_COUNT, shard)
    earlier_end_offset = get_split_offset(len(earlier_validator_set), SHARD_COUNT, shard+1)
    earlier_committee = [
        earlier_validator_set[get_permuted_index(i, len(earlier_validator_set), earlier_seed)]
        for i in range(earlier_start_offset, earlier_end_offset)
    ]
    
    later_committee_start = epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD
    later_validator_set = get_active_validator_indices(state.validators, later_committee_start)
    later_seed = generate_seed(state, later_committee_start)
    later_start_offset = get_split_offset(len(later_validator_set), SHARD_COUNT, shard)
    later_end_offset = get_split_offset(len(later_validator_set), SHARD_COUNT, shard+1)
    later_committee = [
        later_validator_set[get_permuted_index(i, len(later_validator_set), later_seed)]
        for i in range(later_start_offset, later_end_offset)
    ]
    
    def get_switchover_epoch(index):
        return (
            bytes_to_int(hash(earlier_seed + bytes3(index))[0:8]) %
            PERSISTENT_COMMITTEE_PERIOD
        )
       
    # Take not-yet-cycled-out validators from earlier committee and already-cycled-in validators from
    # later committee; return a sorted list of the union of the two, deduplicated
    return sorted(list(set(
        [i for i in earlier_committee if epoch % PERSISTENT_COMMITTEE_PERIOD < get_switchover_epoch(i)] +
        [i for i in later_committee if epoch % PERSISTENT_COMMITTEE_PERIOD >= get_switchover_epoch(i)]
    )))
```
#### get_shard_proposer_index

```python
def get_shard_proposer_index(state: BeaconState,
                             shard: ShardNumber,
                             slot: SlotNumber) -> ValidatorIndex:
    seed = hash(
        state.current_epoch_seed +
        int_to_bytes8(shard) +
        int_to_bytes8(slot)
    )
    persistent_committee = get_persistent_committee(state, shard, slot_to_epoch(slot))
    # Default proposer
    index = bytes_to_int(seed[0:8]) % len(persistent_committee)
    # If default proposer exits, try the other proposers in order; if all are exited
    # return None (ie. no block can be proposed)
    validators_to_try = persistent_committee[index:] + persistent_committee[:index]
    for index in validators_to_try:
        if is_active_validator(state.validators[index], get_current_epoch(state)):
            return index
    return None
## Data Structures

### Shard chain blocks

A `ShardBlock` object has the following fields:

```python
{
    # Slot number
    'slot': 'uint64',
    # What shard is it on
    'shard_id': 'uint64',
    # Parent block's root
    'parent_root': 'bytes32',
    # Beacon chain block
    'beacon_chain_ref': 'bytes32',
    # Merkle root of data
    'data_root': 'bytes32'
    # State root (placeholder for now)
    'state_root': 'bytes32',
    # Block signature
    'signature': 'bytes96',
    # Attestation
    'participation_bitfield': 'bytes',
    'aggregate_signature': 'bytes96',
}
```

## Shard block processing

For a `shard_block` on a shard to be processed by a node, the following conditions must be met:

* The `ShardBlock` pointed to by `shard_block.parent_root` has already been processed and accepted
* The signature for the block from the _proposer_ (see below for definition) of that block is included along with the block in the network message object

To validate a block header on shard `shard_block.shard_id`, compute as follows:

* Verify that `shard_block.beacon_chain_ref` is the hash of a block in the (canonical) beacon chain with slot less than or equal to `slot`.
* Verify that `shard_block.beacon_chain_ref` is equal to or a descendant of the `shard_block.beacon_chain_ref` specified in the `ShardBlock` pointed to by `shard_block.parent_root`.
* Let `state` be the state of the beacon chain block referred to by `shard_block.beacon_chain_ref`.
* Let `persistent_committee = get_persistent_committee(state, shard_block.shard_id, slot_to_epoch(shard_block.slot))`.
* Assert `verify_bitfield(shard_block.participation_bitfield, len(persistent_committee))`
* Let `proposer_index = bytes_to_int(hash(state.current_epoch_seed + int_to_bytes8(shard_block.shard_id) + int_to_bytes8(shard_block.slot))[0:8]) % len(validators)`. Let `msg` be the `shard_block` but with `shard_block.signature` set to `[0, 0]`. Verify that `bls_verify(pubkey=validators[proposer_index].pubkey, message_hash=hash(msg), signature=shard_block.signature, domain=get_domain(state, slot_to_epoch(shard_block.slot), SHARD_PROPOSER_DOMAIN))` passes.
* Let `group_public_key = bls_aggregate_pubkeys([state.validators[index].pubkey for i, index in enumerate(persistent_committee) if get_bitfield_bit(shard_block.participation_bitfield, i) is True])`. Verify that `bls_verify(pubkey=group_public_key, message_hash=shard_block.parent_root, sig=shard_block.aggregate_signature, domain=get_domain(state, slot_to_epoch(shard_block.slot), SHARD_ATTESTER_DOMAIN))` passes.

### Verifying shard block data

At network layer, we expect a shard block header to be broadcast along with its `block_body`.

* Verify that `len(block_body) == SHARD_BLOCK_SIZE`
* Verify that `merkle_root(block_body)` equals the `data_root` in the header.

### Verifying a crosslink

A node should sign a crosslink only if the following conditions hold. **If a node has the capability to perform the required level of verification, it should NOT follow chains on which a crosslink for which these conditions do NOT hold has been included, or a sufficient number of signatures have been included that during the next state recalculation, a crosslink will be registered.**

First, the conditions must recursively apply to the crosslink referenced in `last_crosslink_root` for the same shard (unless `last_crosslink_root` equals zero, in which case we are at the genesis).

Second, we verify the `shard_chain_commitment`.
* Let `start_slot = state.latest_crosslinks[shard].epoch * EPOCH_LENGTH + EPOCH_LENGTH - CROSSLINK_LOOKBACK`.
* Let `end_slot = attestation.data.slot - attestation.data.slot % EPOCH_LENGTH - CROSSLINK_LOOKBACK`.
* Let `length = end_slot - start_slot`, `headers[0] .... headers[length-1]` be the serialized block headers in the canonical shard chain from the verifer's point of view (note that this implies that `headers` and `bodies` have been checked for validity).
* Let `bodies[0] ... bodies[length-1]` be the bodies of the blocks.
* Note: If there is a missing slot, then the header and body are the same as that of the block at the most recent slot that has a block.

We define two helpers:

```python
def pad_to_power_of_2(values: List[bytes]) -> List[bytes]:
    while not is_power_of_two(len(values)):
        values = values + [SHARD_BLOCK_SIZE]
    return values
```

```python
def merkle_root_of_bytes(data: bytes) -> bytes:
    return merkle_root([data[i:i+32] for i in range(0, len(data), 32)])
```

We define the function for computing the commitment as follows:

```python
def compute_commitment(headers: List[ShardBlock], bodies: List[bytes]) -> Bytes32:
    return hash(
        merkle_root(pad_to_power_of_2([merkle_root_of_bytes(zpad(serialize(h), SHARD_BLOCK_SIZE)) for h in headers])),
        merkle_root(pad_to_power_of_2([merkle_root_of_bytes(h) for h in bodies]))
    )
```

The `shard_chain_commitment` is only valid if it equals `compute_commitment(headers, bodies)`.


### Shard block fork choice rule

The fork choice rule for any shard is LMD GHOST using the shard chain attestations of the persistent committee and the beacon chain attestations of the crosslink committee currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (ie. `state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_chain_ref` is the block in the main beacon chain at the specified `slot` should be considered (if the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than a slot).
