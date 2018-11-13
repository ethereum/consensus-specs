# Ethereum 2.0 Phase 1 -- Shard Data Chains

###### tags: `spec`, `eth2.0`, `casper`, `sharding`

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the [Python proof-of-concept implementation](https://github.com/ethereum/beacon_chain).

### Introduction

This document represents the specification for Phase 1 of Ethereum 2.0 -- Shard Data Chains. Phase 1 depends on the implementation of [Phase 0 -- The Beacon Chain](specs/core/0_beacon-chain.md).

Ethereum 2.0 consists of a central beacon chain along with `SHARD_COUNT` shard chains. Phase 1 is primarily concerned with the construction, validity, and consensus on the _data_ of these shard chains. Phase 1 does not specify shard chain state execution or account balances. This is left for future phases.

### Terminology

### Constants

Phase 1 depends upon all of the constants defined in [Phase 0](specs/core/0_beacon-chain.md#constants) in addition to the following:

| Constant | Value | Unit | Approximation |
| `CHUNK_SIZE` | 2**8 (= 256) | bytes |
| `MAX_SHARD_BLOCK_SIZE` | 2**15 (= 32768) | bytes |

## Data Structures

### Shard chain blocks

A `ShardBlock` object has the following fields:

```python
{
    # Slot number
    'slot': 'uint64',
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

A block on a shard can be processed only if its `parent` has been accepted. To validate a block header on shard `shard_id`, compute as follows:

* Verify that `beacon_chain_ref` is the hash of the `slot`'th block in the beacon chain.
* Let `state` be the state of the beacon chain block referred to by `beacon_chain_ref`. Let `validators` be `[validators[i] for i in state.current_persistent_committees[shard_id]]`.
* Assert `len(attester_bitfield) == ceil_div8(len(validators))`
* Let `curblock_proposer_index = hash(state.randao_mix + bytes8(shard_id)) % len(validators)`. Let `parent_proposer_index` be the same value calculated for the parent block.
* Make sure that the `parent_proposer_index`'th bit in the `attester_bitfield` is set to 1.
* Generate the group public key by adding the public keys of all the validators for whom the corresponding position in the bitfield is set to 1. Verify the `aggregate_sig` using this as the pubkey and the `parent_hash` as the message.

Note that at network layer we expect blocks to be broadcasted along with the signature from the `curblock_proposer_index`'th validator in the validator set for that block.

### Verifying shard block data

At network layer, we expect a shard block header to be broadcasted along with its `block_body`. First, we define a helper function that takes as input beacon chain state and outputs the max block size in bytes:

```python
def calc_block_maxbytes(state):
    max_grains = MAX_SHARD_BLOCK_SIZE // CHUNK_SIZE
    validators_at_max_committees = SHARD_COUNT * TARGET_COMMITTEE_SIZE
    grains = min(len(get_active_validator_indices(state.validators)) * max_grains // validators_at_max_committees,
                 max_grains)
    return CHUNK_SIZE * grains
```

* Verify that `len(block_body) == calc_block_maxbytes(state)`
* Define `filler_bytes = next_power_of_2(len(block_body)) - len(block_body)`. Compute a simple binary Merkle tree of `block_body + bytes([0] * filler_bytes)` and verify that the root equals the `data_root` in the header.

### Verifying a crosslink

A node should sign a crosslink only if the following conditions hold. **If a node has the capability to perform the required level of verification, it should NOT follow chains on which a crosslink for which these conditions do NOT hold has been included, or a sufficient number of signatures have been included that during the next state recalculation, a crosslink will be registered.**

First, the conditions must recursively apply to the crosslink referenced in `last_crosslink_hash` for the same shard (unless `last_crosslink_hash` equals zero, in which case we are at the genesis).

Second, we verify the `shard_block_combined_data_root`. Let `B[0]` be the first block _after_ the last crosslink and `B[n-1]` be the block directly referenced by the `shard_block_hash`. Let `bodies[0] .... bodies[n-1]` be their bodies and `roots[0] ... roots[n-1]` the data roots. Define `compute_merkle_root` be a simple Merkle root calculating function that takes as input a list of objects, where the list's length must be an exact power of two. Let `state[0] ... state[n-1]` be the beacon chain states at those times, and `depths[0] ... depths[n-1]` be equal to `log2(next_power_of_2(calc_block_maxbytes(state[i]) // CHUNK_SIZE))` (ie. the expected depth of the i'th data tree).

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

Essentially, this outputs the root of a tree of the data roots, with the data roots all adjusted to have the same height if needed. The tree can also be viewed as a tree of all of the underlying data concatenated together, appropriately padded. Here is an equivalent definition that uses bodies instead of roots [TODO: check equivalence]:

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

The fork choice rule for any shard is LMD GHOST using the validators currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (ie. `state.crosslinks[shard].shard_block_hash`).
