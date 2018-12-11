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
| `CHUNK_SIZE`           | 2**8 (= 256)    | bytes |               |
| `SHARD_BLOCK_SIZE`     | 2**14 (= 16384) | bytes |               |

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
    'attester_bitfield': 'bytes',
    'aggregate_sig': ['uint384'],
}
```

## Shard block processing

For a block on a shard to be processed by a node, the following conditions must be met:

* The `ShardBlock` pointed to by `parent_root` has already been processed and accepted
* The signature for the block from the _proposer_ (see below for definition) of that block is included along with the block in the network message object

To validate a block header on shard `shard_id`, compute as follows:

* Verify that `beacon_chain_ref` is the hash of a block in the beacon chain with slot less than or equal to `slot`. Verify that `beacon_chain_ref` is equal to or a descendant of the `beacon_chain_ref` specified in the `ShardBlock` pointed to by `parent_root`.
* Let `state` be the state of the beacon chain block referred to by `beacon_chain_ref`. Let `validators` be `[validators[i] for i in state.current_persistent_committees[shard_id]]`.
* Assert `len(attester_bitfield) == ceil_div8(len(validators))`
* Let `proposer_index = hash(state.randao_mix + bytes8(shard_id) + bytes8(slot)) % len(validators)`. Let `msg` be the block but with the `block.signature` set to `[0, 0]`. Verify that `BLSVerify(pub=validators[proposer_index].pubkey, msg=hash(msg), sig=block.signature, domain=get_domain(state, slot, SHARD_PROPOSER_DOMAIN))` passes.
* Generate the `group_public_key` by adding the public keys of all the validators for whom the corresponding position in the bitfield is set to 1. Verify that `BLSVerify(pub=group_public_key, msg=parent_root, sig=block.aggregate_sig, domain=get_domain(state, slot, SHARD_ATTESTER_DOMAIN))` passes.

### Block Merklization helper

```python
def merkle_root(block_body):
    assert len(block_body) == SHARD_BLOCK_SIZE
    chunks = SHARD_BLOCK_SIZE // CHUNK_SIZE
    o = [0] * chunks + [block_body[i * CHUNK_SIZE: (i+1) * CHUNK_SIZE] for i in range(chunks)]
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

Second, we verify the `shard_block_combined_data_root`. Let `h` be the slot _immediately after_ the slot of the shard block included by the last crosslink, and `h+n-1` be the slot number of the block directly referenced by the current `shard_block_root`. Let `B[i]` be the block at slot `h+i` in the shard chain. Let `bodies[0] .... bodies[n-1]` be the bodies of these blocks and `roots[0] ... roots[n-1]` the data roots. If there is a missing slot in the shard chain at position `h+i`, then `bodies[i] == b'\x00' * shard_block_maxbytes(state[i])` and `roots[i]` be the Merkle root of the empty data. Define `compute_merkle_root` be a simple Merkle root calculating function that takes as input a list of objects, where the list's length must be an exact power of two. We define the function for computing the combined data root as follows:

```python
ZERO_ROOT = merkle_root(bytes([0] * SHARD_BLOCK_SIZE))

def mk_combined_data_root(roots):
    data = roots + [ZERO_ROOT for _ in range(len(roots), next_power_of_2(len(roots)))]
    return compute_merkle_root(data)
```

This outputs the root of a tree of the data roots, with the data roots all adjusted to have the same height if needed. The tree can also be viewed as a tree of all of the underlying data concatenated together, appropriately padded. Here is an equivalent definition that uses bodies instead of roots [TODO: check equivalence]:

```python
def mk_combined_data_root(depths, bodies):
    data = b''.join(bodies)
    data += bytes([0] * (next_power_of_2(len(data)) - len(data))
    return compute_merkle_root([data[pos:pos+CHUNK_SIZE] for pos in range(0, len(data), CHUNK_SIZE)])
```

Verify that the `shard_block_combined_data_root` is the output of these functions.

### Shard block fork choice rule

The fork choice rule for any shard is LMD GHOST using the validators currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (ie. `state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_chain_ref` is the block in the main beacon chain at the specified `slot` should be considered (if the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than a slot).
