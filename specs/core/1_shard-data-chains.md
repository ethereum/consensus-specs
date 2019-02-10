# Ethereum 2.0 Phase 1 -- Shard Data Chains

###### tags: `spec`, `eth2.0`, `casper`, `sharding`

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the [Python proof-of-concept implementation](https://github.com/ethereum/beacon_chain).

### Introduction

This document represents the specification for Phase 1 of Ethereum 2.0 -- Shard Data Chains. Phase 1 depends on the implementation of [Phase 0 -- The Beacon Chain](0_beacon-chain.md).

Ethereum 2.0 consists of a central beacon chain along with `SHARD_COUNT` shard chains. Phase 1 is primarily concerned with the construction, validity, and consensus on the _data_ of these shard chains. Phase 1 does not specify shard chain state execution or account balances. This is left for future phases.

### Terminology

### Constants

Phase 1 depends upon all of the constants defined in [Phase 0](0_beacon-chain.md#constants) in addition to the following:

| Constant               | Value           | Unit  | Approximation |
|------------------------|-----------------|-------|---------------|
| `SHARD_CHUNK_SIZE`     | 2**5 (= 32)     | bytes |               |
| `SHARD_BLOCK_SIZE`     | 2**14 (= 16384) | bytes |               |
| `CROSSLINK_LOOKBACK`   | 2**5 (= 32)     | slots |               |

### Flags, domains, etc.

| Constant               | Value           |
|------------------------|-----------------|
| `SHARD_PROPOSER_DOMAIN`| 129             |
| `SHARD_ATTESTER_DOMAIN`| 130             |

## Data Structures

### Shard chain blocks

A `ShardBlock` object has the following fields:

```python
{
    # Slot number
    'slot': 'uint64',
    # What shard is it on
    'shard_id': 'uint64',
    # Parent block's hash of root
    'parent_root': 'hash32',
    # Beacon chain block
    'beacon_chain_ref': 'hash32',
    # Depth of the Merkle tree
    'data_tree_depth': 'uint8',
    # Merkle root of data
    'data_root': 'hash32'
    # State root (placeholder for now)
    'state_root': 'hash32',
    # Block signature
    'signature': ['uint384'],
    # Attestation
    'participation_bitfield': 'bytes',
    'aggregate_signature': ['uint384'],
}
```

## Shard block processing

For a block on a shard to be processed by a node, the following conditions must be met:

* The `ShardBlock` pointed to by `parent_root` has already been processed and accepted
* The signature for the block from the _proposer_ (see below for definition) of that block is included along with the block in the network message object

To validate a block header on shard `shard_id`, compute as follows:

* Verify that `beacon_chain_ref` is the hash of a block in the beacon chain with slot less than or equal to `slot`. Verify that `beacon_chain_ref` is equal to or a descendant of the `beacon_chain_ref` specified in the `ShardBlock` pointed to by `parent_root`.
* Let `state` be the state of the beacon chain block referred to by `beacon_chain_ref`. Let `validators` be `[validators[i] for i in state.current_persistent_committees[shard_id]]`.
* Assert `len(participation_bitfield) == ceil_div8(len(validators))`
* Let `proposer_index = hash(state.randao_mix + int_to_bytes8(shard_id) + int_to_bytes8(slot)) % len(validators)`. Let `msg` be the block but with the `block.signature` set to `[0, 0]`. Verify that `BLSVerify(pub=validators[proposer_index].pubkey, msg=hash(msg), sig=block.signature, domain=get_domain(state, slot, SHARD_PROPOSER_DOMAIN))` passes.
* Generate the `group_public_key` by adding the public keys of all the validators for whom the corresponding position in the bitfield is set to 1. Verify that `BLSVerify(pub=group_public_key, msg=parent_root, sig=block.aggregate_signature, domain=get_domain(state, slot, SHARD_ATTESTER_DOMAIN))` passes.

### Block Merklization helper

```python
def merkle_root(block_body):
    assert len(block_body) == SHARD_BLOCK_SIZE
    chunks = SHARD_BLOCK_SIZE // SHARD_CHUNK_SIZE
    o = [0] * chunks + [block_body[i * SHARD_CHUNK_SIZE: (i+1) * SHARD_CHUNK_SIZE] for i in range(chunks)]
    for i in range(chunks-1, 0, -1):
        o[i] = hash(o[i*2] + o[i*2+1])
    return o[1]
```

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
