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
| `MAX_SHARD_BLOCK_SIZE` | 2**15 (= 32768) | bytes |               |

## Data Structures

### Shard chain blocks

A `ShardBlock` object has the following fields:

```python
{
    # Slot number
    'slot': 'uint64',
    # What shard is it on
    'shard_id': 'uint64',
    # Parent block hash
    'parent_hash': 'hash32',
    # Beacon chain block
    'beacon_chain_ref': 'hash32',
    # Depth of the Merkle tree
    'data_tree_depth': 'uint8',
    # Merkle root of data
    'data_root': 'hash32'
    # State root (placeholder for now)
    'state_root': 'hash32',
    # Attestation (including block signature)
    'attester_bitfield': 'bytes',
    'aggregate_sig': ['uint256'],
}
```

## Shard block processing

For a block on a shard to be processed by a node, the following conditions must be met:

* The `ShardBlock` pointed to by `parent_hash` has already been processed and accepted
* The signature for the block from the _proposer_ (see below for definition) of that block is included along with the block in the network message object

To validate a block header on shard `shard_id`, compute as follows:

* Verify that `beacon_chain_ref` is the hash of a block in the beacon chain with slot less than or equal to `slot`. Verify that `beacon_chain_ref` is equal to or a descendant of the `beacon_chain_ref` specified in the `ShardBlock` pointed to by `parent_hash`.
* Let `state` be the state of the beacon chain block referred to by `beacon_chain_ref`. Let `validators` be `[validators[i] for i in state.current_persistent_committees[shard_id]]`.
* Assert `len(attester_bitfield) == ceil_div8(len(validators))`
* Let `curblock_proposer_index = hash(state.randao_mix + bytes8(shard_id) + bytes8(slot)) % len(validators)`. Let `parent_proposer_index` be the same value calculated for the parent block.
* Make sure that the `parent_proposer_index`'th bit in the `attester_bitfield` is set to 1.
* Generate the group public key by adding the public keys of all the validators for whom the corresponding position in the bitfield is set to 1. Verify the `aggregate_sig` using this as the pubkey and the `parent_hash` as the message.

### Verifying shard block data

At network layer, we expect a shard block header to be broadcast along with its `block_body`. First, we define a helper function that takes as input beacon chain state and outputs the max block size in bytes:

```python
def shard_block_maxbytes(state):
    max_grains = MAX_SHARD_BLOCK_SIZE // CHUNK_SIZE
    validators_at_target_committee_size = SHARD_COUNT * TARGET_COMMITTEE_SIZE

    # number of grains per block is proportional to the number of validators
    # up until `validators_at_target_committee_size`
    grains = min(
        len(get_active_validator_indices(state.validators)) * max_grains // validators_at_target_committee_size,
        max_grains
    )

    return CHUNK_SIZE * grains
```

* Verify that `len(block_body) == shard_block_maxbytes(state)`
* Define `filler_bytes = next_power_of_2(len(block_body)) - len(block_body)`. Compute a simple binary Merkle tree of `block_body + bytes([0] * filler_bytes)` and verify that the root equals the `data_root` in the header.

### Verifying a crosslink

A node should sign a crosslink only if the following conditions hold. **If a node has the capability to perform the required level of verification, it should NOT follow chains on which a crosslink for which these conditions do NOT hold has been included, or a sufficient number of signatures have been included that during the next state recalculation, a crosslink will be registered.**

First, the conditions must recursively apply to the crosslink referenced in `last_crosslink_hash` for the same shard (unless `last_crosslink_hash` equals zero, in which case we are at the genesis).

Second, we verify the `shard_block_combined_data_root`. Let `h` be the slot _immediately after_ the slot of the shard block included by the last crosslink, and `h+n-1` be the slot number of the block directly referenced by the current `shard_block_hash`. Let `B[i]` be the block at slot `h+i` in the shard chain. Let `bodies[0] .... bodies[n-1]` be the bodies of these blocks and `roots[0] ... roots[n-1]` the data roots. If there is a missing slot in the shard chain at position `h+i`, then `bodies[i] == b'\x00' * shard_block_maxbytes(state[i])` and `roots[i]` be the Merkle root of the empty data. Define `compute_merkle_root` be a simple Merkle root calculating function that takes as input a list of objects, where the list's length must be an exact power of two. Let `state[i]` be the beacon chain state at height `h+i` (if the beacon chain is missing a block at some slot, the state is unchanged), and `depths[i]` be equal to `log2(next_power_of_2(shard_block_maxbytes(state[i]) // CHUNK_SIZE))` (ie. the expected depth of the i'th data tree). We define the function for computing the combined data root as follows:

```python
def get_zeroroot_at_depth(n):
    o = b'\x00' * CHUNK_SIZE
    for i in range(n):
        o = hash(o + o)
    return o

def mk_combined_data_root(depths, roots):
    default_value = get_zeroroot_at_depth(max(depths))
    data = [default_value for _ in range(next_power_of_2(len(roots)))]
    for i, (depth, root) in enumerate(zip(depths, roots)):
        value = root
        for j in range(depth, max(depths)):
            value = hash(value, get_zeroroot_at_depth(depth + j))
        data[i] = value
    return compute_merkle_root(data)
```

This outputs the root of a tree of the data roots, with the data roots all adjusted to have the same height if needed. The tree can also be viewed as a tree of all of the underlying data concatenated together, appropriately padded. Here is an equivalent definition that uses bodies instead of roots [TODO: check equivalence]:

```python
def mk_combined_data_root(depths, bodies):
    default_value = get_zeroroot_at_depth(max(depths))
    padded_body_length = max([CHUNK_SIZE * 2**d for d in depths])
    data = b''
    for body in bodies:
        padded_body = body + bytes([0] * (padded_body_length - len(body)))
        data += padded_body
    data += bytes([0] * (next_power_of_2(len(data)) - len(data))
    return compute_merkle_root([data[pos:pos+CHUNK_SIZE] for pos in range(0, len(data), CHUNK_SIZE)])
```

Verify that the `shard_block_combined_data_root` is the output of these functions.

### Shard block fork choice rule

The fork choice rule for any shard is LMD GHOST using the validators currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (ie. `state.crosslinks[shard].shard_block_hash`). Only blocks whose `beacon_chain_ref` is the block in the main beacon chain at the specified `slot` should be considered (if the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than a slot).
