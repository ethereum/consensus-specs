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
| `PROOF_OF_CUSTODY_MIN_CHANGE_PERIOD` | 2**17 | (= 65,536) | slots | ~9 days |
| `PROOF_OF_CUSTODY_RESPONSE_DEADLINE` | 2**20 (= 524,288) | slots | ~73 days |

### Flags, domains, etc.

| Constant               | Value           |
|------------------------|-----------------|
| `SHARD_PROPOSER_DOMAIN`| 129             |
| `SHARD_ATTESTER_DOMAIN`| 130             |

**Special record types**

| Name | Value | Maximum count |
| `PROOF_OF_CUSTODY_SEED_CHANGE` | `4` | `16` |
| `PROOF_OF_CUSTODY_CHALLENGE` | `5` | `16` |
| `PROOF_OF_CUSTODY_RESPONSE` | `6` | `16` |

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
    # Block signature
    'signature': ['uint384'],
    # Attestation
    'attester_bitfield': 'bytes',
    'aggregate_sig': ['uint384'],
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
* Let `proposer_index = hash(state.randao_mix + bytes8(shard_id) + bytes8(slot)) % len(validators)`. Let `msg` be the block but with the `block.signature` set to `[0, 0]`. Verify that `BLSVerify(pub=validators[proposer_index].pubkey, msg=hash(msg), sig=block.signature, domain=get_domain(state, slot, SHARD_PROPOSER_DOMAIN))` passes.
* Generate the `group_public_key` by adding the public keys of all the validators for whom the corresponding position in the bitfield is set to 1. Verify that `BLSVerify(pub=group_public_key, msg=parent_hash, sig=block.aggregate_sig, domain=get_domain(state, slot, SHARD_ATTESTER_DOMAIN))` passes.

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

First, the conditions must recursively apply to the crosslink referenced in `last_crosslink_hash` for the same shard (unless `last_crosslink_hash` equals zero, in which case we are at the genesis).

Second, we verify the `shard_block_combined_data_root`. Let `h` be the slot _immediately after_ the slot of the shard block included by the last crosslink, and `h+n-1` be the slot number of the block directly referenced by the current `shard_block_hash`. Let `B[i]` be the block at slot `h+i` in the shard chain. Let `bodies[0] .... bodies[n-1]` be the bodies of these blocks and `roots[0] ... roots[n-1]` the data roots. If there is a missing slot in the shard chain at position `h+i`, then `bodies[i] == b'\x00' * shard_block_maxbytes(state[i])` and `roots[i]` be the Merkle root of the empty data. Define `compute_merkle_root` be a simple Merkle root calculating function that takes as input a list of objects, where the list's length must be an exact power of two. We define the function for computing the combined data root as follows:

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

The fork choice rule for any shard is LMD GHOST using the validators currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (ie. `state.crosslinks[shard].shard_block_hash`). Only blocks whose `beacon_chain_ref` is the block in the main beacon chain at the specified `slot` should be considered (if the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than a slot).

## Changes to beacon chain

Change to attestation verification:

* Let `expected_depth = log2(SHARD_BLOCK_SIZE // SHARD_CHUNK_SIZE * next_power_of_2(slot - last_crosslink_slot))`. For each integer `i = 0, 1`, let `messages[i]` be `AttestationSignedData(slot, shard, parent_hashes, shard_block_hash, i == 1, expected_depth, attestation_indices.total_validator_count, justified_slot)`.

A `ProofOfCustodyChallenge` has the following fields:

```python
{
    # Which validator is responding
    'responder_index': 'uint64',
    # Seed hash
    'seed_hash': 'hash32',
    # Depth
    'depth': 'uint64',
    # Index in tree
    'data_index': 'uint64',
    # Expiry date
    'expiry_slot': 'uint64',
    # Who is challenging
    'challenger_index': 'uint64',
    # Data root
    'data_root': 'hash32',
    # Proof of custody bit
    'bit': 'bool'
}
```



Three new types of `SpecialObject` records:

#### PROOF_OF_CUSTODY_SEED_CHANGE

```python
{
    'index': 'uint64',
    'new_commitment': 'hash32',
    'signature': ['uint256']
}
```

Let `signed_data = bytes8(fork_version) + new_commitment`. Verify that `BLSVerify(pub=state.validators[index].pubkey, msg=hash(signed_data), sig=signature)` passes. Verify that `hash(new_commitment) = state.validators[index].proof_of_custody_commitment`, and the `block.slot >= state.validators[index].proof_of_custody_last_change + PROOF_OF_CUSTODY_MIN_CHANGE_PERIOD`. Set `state.validators[index].proof_of_custody_second_last_change = state.validators[index].proof_of_custody_last_change` and `state.validators[index].proof_of_custody_last_change = block.slot`.

#### PROOF_OF_CUSTODY_CHALLENGE

```
{
    'attestation': SpecialAttestationData,
    'validator_index': 'uint64',
    'data_index': 'uint64',
}
```

Perform the following checks:

* Verify that the attestation is valid.
* Verify that `attestation.slot > state.validators[index].proof_of_custody_second_last_change`.
* Verify that `validator_index in attestation.aggregate_sig_poc_0_indices` or `validator_index in attestation.aggregate_sig_poc_1_indices`; if the former, let `bit = False`, else `bit = True`.
* Verify that `state.validators[index].status == ACTIVE` or `state.validators[index].status == PENDING_EXIT` and `block.slot < state.validators[index].exit_slot + PROOF_OF_CUSTODY_MIN_CHANGE_PERIOD`
* Let `check_value = as_uint256(hash(as_bytes8(validator_index) + as_bytes8(attestation.slot) + as_bytes8(attestation.shard_id)))`.
* Let `FULL_PROOF_OF_CUSTODY_VALCOUNT = TARGET_COMMITEE_SIZE * SHARD_COUNT`, and `target = 2**256 * attestation.total_validator_count // FULL_PROOF_OF_CUSTODY_VALCOUNT`.
* Verify that `check_value <= target`.

Let `seed_hash = state.validators[index].proof_of_custody_commitment if attestation.slot > state.validators[index].proof_of_custody_last_change else hash(state.validators[index].proof_of_custody_commitment)`. Append to `state.proof_of_custody_challenges` the object `ProofOfCustodyChallenge(responder_index=validator_index, seed_hash=seed_hash, depth=attestation.proof_of_custody_depth, data_root=attestation.data.shard_block_hash, data_index=data_index, expiry_slot=block.slot+PROOF_OF_CUSTODY_RESPONSE_DEADLINE, challenger_index=get_proposer(state, block), bit=bit)`.

A block can have maximum one proof of custody challenge, and it must appear before all `PROOF_OF_CUSTODY_SEED_CHANGE` objects.

#### PROOF_OF_CUSTODY_RESPONSE
```
{
    'challenge_index': 'uint64',
    'leaf': 'hash32',
    'root': 'hash32',
    'seed': 'hash32',
    'data_merkle_branch': '[hash32]',
    'poc_merkle_branch': '[hash32]',
}
```
Perform the following checks:

* Verify `challenge_index < len(state.proof_of_custody_challenges)`.
* Let`challenge = state.proof_of_custody_challenges[challenge_index]`.
* Verify that `hash(seed) = challenge.seed_hash`
* Verify that `verify_merkle_branch(leaf, data_merkle_branch, challenge.depth, challenge.data_index, root)` passes.
* Verify that `verify_merkle_branch(leaf, poc_merkle_branch, challenge.depth, challenge.data_index, xor(root, seed))` passes.
* Verify that `uint256(root) % 2 == challenge.bit`.

Remove `challenge` from `state.proof_of_custody_challenges` (note: if a block has multiple `PROOF_OF_CUSTODY_RESPONSE` objects , later objects' `challenge_index` values will need to take removals from earlier objects into account).
