# Ethereum 2.0 Phase 1 -- Shard Data Chains

###### tags: `spec`, `eth2.0`, `casper`, `sharding`

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the [Python proof-of-concept implementation](https://github.com/ethereum/beacon_chain).

### Introduction

This document represents the specification for Phase 1 of Ethereum 2.0 -- Shard Data Chains. Phase 1 depends on the implementation of [Phase 0 -- The Beacon Chain](0_beacon-chain.md).

Ethereum 2.0 consists of a central beacon chain along with `SHARD_COUNT` shard chains. Phase 1 is primarily concerned with the construction, validity, and consensus on the _data_ of these shard chains. Phase 1 does not specify shard chain state execution or account balances. This is left for future phases.

### Terminology

### Constants

Phase 1 depends upon all of the constants defined in [Phase 0](0_beacon-chain.md#constants) in addition to the following:

| Constant                     | Value           | Unit   | Approximation |
|------------------------------|-----------------|--------|---------------|
| `SHARD_CHUNK_SIZE`           | 2**5 (= 32)     | bytes  |               |
| `SHARD_BLOCK_SIZE`           | 2**14 (= 16384) | bytes  |               |
| `MAX_BRANCH_CHALLENGE_DELAY` | 2**11 (= 2048)  | epochs | 9 days        |
| `CHALLENGE_RESPONSE_DEADLINE`| 2**14 (= 16384) | epochs | 73 days       |
| `MAX_BRANCH_CHALLENGES`      | 2**2 (= 4)      |        |               |
| `MAX_BRANCH_RESPONSES`       | 2**4 (= 16)     |        |               |
| `MAX_EARLY_SUBKEY_REVEALS`   | 2**4 (= 16)     |        |               |
| `CUSTODY_PERIOD_LENGTH`      | 2**11 (= 2048)  | epochs | 9 days        |

### Flags, domains, etc.

| Constant               | Value           |
|------------------------|-----------------|
| `SHARD_PROPOSER_DOMAIN`| 129             |
| `SHARD_ATTESTER_DOMAIN`| 130             |
| `DOMAIN_CUSTODY_SUBKEY`| 131             |

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
    return compute_merkle_root([data[pos:pos+SHARD_CHUNK_SIZE] for pos in range(0, len(data), SHARD_CHUNK_SIZE)])
```

Verify that the `shard_block_combined_data_root` is the output of these functions.

### Shard block fork choice rule

The fork choice rule for any shard is LMD GHOST using the validators currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (ie. `state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_chain_ref` is the block in the main beacon chain at the specified `slot` should be considered (if the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than a slot).

# Updates to the beacon chain

## Data structures

Add a member value to the end of the `Validator` object (initialized to `[]`):

```python
    'open_branch_challenges': [BranchChallengeRecord],
```

Define a `BranchChallengeRecord` as follows:

```python
{
    'challenger_index': 'uint64',
    'root': 'bytes32',
    'depth': 'uint64',
    'inclusion_epoch': 'uint64',
    'data_index': 'uint64'
}
```

In `process_penalties_and_exits`, change the definition of `eligible` to the following (note that it is not a pure function because `state` is declared in the surrounding scope):

```python
def eligible(index):
    validator = state.validator_registry[index]
    if len(validator.open_branch_challenges) > 0:
        return False
    elif validator.penalized_epoch <= current_epoch:
        penalized_withdrawal_epochs = LATEST_PENALIZED_EXIT_LENGTH // 2
        return current_epoch >= validator.penalized_epoch + penalized_withdrawal_epochs
    else:
        return current_epoch >= validator.exit_epoch + MIN_VALIDATOR_WITHDRAWAL_EPOCHS
```

Add two member values to the `BeaconBlockBody` structure:

```python
    'branch_challenges': [BranchChallenge],
    'branch_responses': [BranchResponse],
    'early_subkey_reveals': [EarlySubkeyReveal],
```

Define a `BranchChallenge` as follows:

```python
{
    'responder_index': 'uint64',
    'data_index': 'uint64',
    'attestation': SlashableAttestation,
}
```

Define a `BranchResponse` as follows:

```python
{
    'responder_index': 'uint64',
    'data': 'bytes32',
    'branch': ['bytes32'],
    'data_index': 'uint64',
    'root': 'bytes32'
}
```

Define a `EarlySubkeyReveal` as follows:

```python
{
    'validator_index': 'uint64',
    'period': 'uint64',
    'subkey': 'bytes96'
}
```

## Helpers

```python
def get_current_custody_period(state: BeaconState) -> int:
    return get_current_epoch(state) // CUSTODY_PERIOD_LENGTH
```

```python
def verify_custody_subkey(pubkey: bytes48, subkey: bytes96, period: int) -> bool:
    return bls_verify(
        pubkey=pubkey,
        message_hash=hash(int_to_bytes8(period)),
        signature=subkey,
        domain=get_domain(
            state.fork,
            period * CUSTODY_PERIOD_LENGTH,
            DOMAIN_CUSTODY_SUBKEY
        )
    )
```

## Per-slot processing

Add two object processing categories to the per-slot processing, in order given below and lower than all other objects (specifically, right below exits) as follows.

### Branch challenges

Verify that `len(block.body.branch_challenges) <= MAX_BRANCH_CHALLENGES`.

For each `challenge` in `block.body.branch_challenges`:

* Verify that `slot_to_epoch(challenge.attestation.data.slot) >= get_current_epoch(state) - MAX_BRANCH_CHALLENGE_DELAY`.
* Verify that `state.validator_registry[responder_index].exit_epoch >= get_current_epoch(state) - MAX_BRANCH_CHALLENGE_DELAY`.
* Verify that `verify_slashable_attestation(state, challenge.attestation)` returns `True`.
* Verify that `challenge.responder_index` is in `challenge.attestation.validator_indices`.
* Let `depth = log2(next_power_of_two(SHARD_BLOCK_SIZE // 32 * EPOCH_LENGTH * (slot_to_epoch(challenge.attestation.data.slot) - challenge.attestation.latest_crosslink.epoch)`. Verify that `challenge.data_index < 2**depth`.
* Verify that there does not exist a `BranchChallengeRecord` in `state.validator_registry[challenge.responder_index].open_branch_challenges` with `root == challenge.attestation.data.shard_chain_commitment` and `data_index == data_index`.
* Append to `state.validator_registry[challenge.responder_index].open_branch_challenges` the object `BranchChallengeRecord(challenger_index=get_beacon_proposer_index(state, state.slot), root=challenge.attestation.data.shard_chain_commitment, depth=depth, inclusion_epoch=get_current_epoch(state), data_index=data_index)`.

**Invariant**: the `open_branch_challenges` array will always stay sorted in order of `inclusion_epoch`.

### Branch responses

Verify that `len(block.body.branch_responses) <= MAX_BRANCH_RESPONSES`.

For each `response` in `block.body.branch_responses`:

* Find the `BranchChallengeRecord` in `state.validator_registry[response.responder_index].open_branch_challenges` whose (`root`, `data_index`) match the (`root`, `data_index`) of the `response`. Verify that one such record exists (it is not possible for there to be more than one), call it `record`.
* Verify that `verify_merkle_branch(leaf=response.data, branch=response.branch, depth=record.depth, index=record.data_index, root=record.root) is True.
* Verify that `get_current_epoch(state) >= record.inclusion_epoch + ENTRY_EXIT_DELAY`.
* Remove the `record` from `state.validator_registry[response.responder_index].open_branch_challenges`
* Determine the proposer `proposer_index = get_beacon_proposer_index(state, state.slot)` and set `state.validator_balances[proposer_index] += base_reward(state, index) // INCLUDER_REWARD_QUOTIENT // MAX_BRANCH_CHALLENGES`.

### Early subkey reveals

Verify that `len(block.body.early_subkey_reveals) <= MAX_EARLY_SUBKEY_REVEALS`.

For each `reveal` in `block.body.early_subkey_reveals`:

* Verify that `state.validator_registry[reveal.validator_index].penalized_epoch > get_current_epoch(state) + ENTRY_EXIT_DELAY`.
* Verify that `verify_custody_subkey(state.validator_registry[reveal.validator_index].pubkey, reveal.subkey, reveal.period)` returns `True`.
* Verify that `reveal.period >= get_current_custody_period(state)`.
* Run `penalize_validator(state, reveal.validator_index)`.

## Per-epoch processing

Add the following loop immediately below the `process_ejections` loop:

```python
def process_challenge_absences(state: BeaconState) -> None:
    """
    Iterate through the validator registry
    and penalize validators with balance that did not answer challenges.
    """
    for index, validator in enumerate(state.validator_registry):
        if len(validator.open_branch_challenges) > 0 and get_current_epoch(state) > validator.open_branch_challenges[0].inclusion_epoch + CHALLENGE_RESPONSE_DEADLINE:
            penalize_validator(state, index)
```
