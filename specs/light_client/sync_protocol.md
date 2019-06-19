# Beacon Chain Light Client Syncing

**Notice**: This document is a work-in-progress for researchers and implementers. One of the design goals of the Eth 2.0 beacon chain is light-client friendliness, not only to allow low-resource clients (mobile phones, IoT, etc.) to maintain access to the blockchain in a reasonably safe way, but also to facilitate the development of "bridges" between the Eth 2.0 beacon chain and other chains.

## Table of contents

<!-- TOC -->

- [Beacon Chain Light Client Syncing](#beacon-chain-light-client-syncing)
    - [Table of contents](#table-of-contents)
    - [Preliminaries](#preliminaries)
        - [Expansions](#expansions)
        - [`get_active_validator_indices`](#get_active_validator_indices)
        - [`MerklePartial`](#merklepartial)
        - [`PeriodData`](#perioddata)
        - [`get_earlier_start_epoch`](#get_earlier_start_epoch)
        - [`get_later_start_epoch`](#get_later_start_epoch)
        - [`get_period_data`](#get_period_data)
        - [Light client state](#light-client-state)
        - [Updating the shuffled committee](#updating-the-shuffled-committee)
    - [Computing the current committee](#computing-the-current-committee)
    - [Verifying blocks](#verifying-blocks)

<!-- /TOC -->

## Preliminaries

### Expansions

We define an "expansion" of an object as an object where a field in an object that is meant to represent the `hash_tree_root` of another object is replaced by the object. Note that defining expansions is not a consensus-layer-change; it is merely a "re-interpretation" of the object. Particularly, the `hash_tree_root` of an expansion of an object is identical to that of the original object, and we can define expansions where, given a complete history, it is always possible to compute the expansion of any object in the history. The opposite of an expansion is a "summary" (e.g. `BeaconBlockHeader` is a summary of `BeaconBlock`).

We define two expansions:

* `ExtendedBeaconState`, which is identical to a `BeaconState` except `active_index_roots: List[Bytes32]` is replaced by `active_indices: List[List[ValidatorIndex]]`, where `BeaconState.active_index_roots[i] = hash_tree_root(ExtendedBeaconState.active_indices[i])`.
* `ExtendedBeaconBlock`, which is identical to a `BeaconBlock` except `state_root` is replaced with the corresponding `state: ExtendedBeaconState`.

### `get_active_validator_indices`

Note that there is now a new way to compute `get_active_validator_indices`:

```python
def get_active_validator_indices(state: ExtendedBeaconState, epoch: Epoch) -> List[ValidatorIndex]:
    return state.active_indices[epoch % ACTIVE_INDEX_ROOTS_LENGTH]
```

Note that it takes `state` instead of `state.validators` as an argument. This does not affect its use in `get_shuffled_committee`, because `get_shuffled_committee` has access to the full `state` as one of its arguments.


### `MerklePartial`

A `MerklePartial(f, *args)` is an object that contains a minimal Merkle proof needed to compute `f(*args)`. A `MerklePartial` can be used in place of a regular SSZ object, though a computation would return an error if it attempts to access part of the object that is not contained in the proof.

### `PeriodData`

```python
{
    'validator_count': 'uint64',
    'seed': 'bytes32',
    'committee': [Validator],
}
```

### `get_earlier_start_epoch`

```python
def get_earlier_start_epoch(slot: Slot) -> int:
    return slot - slot % PERSISTENT_COMMITTEE_PERIOD - PERSISTENT_COMMITTEE_PERIOD * 2
```

### `get_later_start_epoch`

```python
def get_later_start_epoch(slot: Slot) -> int:
    return slot - slot % PERSISTENT_COMMITTEE_PERIOD - PERSISTENT_COMMITTEE_PERIOD
```

### `get_period_data`

```python
def get_period_data(block: ExtendedBeaconBlock, shard_id: Shard, later: bool) -> PeriodData:
    period_start = get_later_start_epoch(header.slot) if later else get_earlier_start_epoch(header.slot)
    validator_count = len(get_active_validator_indices(state, period_start))
    committee_count = validator_count // (SHARD_COUNT * TARGET_COMMITTEE_SIZE) + 1
    indices = get_period_committee(block.state, shard_id, period_start, 0, committee_count)
    return PeriodData(
        validator_count,
        generate_seed(block.state, period_start),
        [block.state.validators[i] for i in indices],
    )
```

### Light client state

A light client will keep track of:

* A random `shard_id` in `[0...SHARD_COUNT-1]` (selected once and retained forever)
* A block header that they consider to be finalized (`finalized_header`) and do not expect to revert.
* `later_period_data = get_period_data(finalized_header, shard_id, later=True)`
* `earlier_period_data = get_period_data(finalized_header, shard_id, later=False)`

We use the struct `ValidatorMemory` to keep track of these variables.

### Updating the shuffled committee

If a client's `validator_memory.finalized_header` changes so that `header.slot // PERSISTENT_COMMITTEE_PERIOD` increases, then the client can ask the network for a `new_committee_proof = MerklePartial(get_period_data, validator_memory.finalized_header, shard_id, later=True)`. It can then compute:

```python
earlier_period_data = later_period_data
later_period_data = get_period_data(new_committee_proof, finalized_header, shard_id, later=True)
```

The maximum size of a proof is `128 * ((22-7) * 32 + 110) = 75520` bytes for validator records and `(22-7) * 32 + 128 * 8 = 1504` for the active index proof (much smaller because the relevant active indices are all beside each other in the Merkle tree). This needs to be done once per `PERSISTENT_COMMITTEE_PERIOD` epochs (2048 epochs / 9 days), or ~38 bytes per epoch.

## Computing the current committee

Here is a helper to compute the committee at a slot given the maximal earlier and later committees:

```python
def compute_committee(header: BeaconBlockHeader,
                      validator_memory: ValidatorMemory) -> List[ValidatorIndex]:
    earlier_validator_count = validator_memory.earlier_period_data.validator_count
    later_validator_count = validator_memory.later_period_data.validator_count
    maximal_earlier_committee = validator_memory.earlier_period_data.committee
    maximal_later_committee = validator_memory.later_period_data.committee
    earlier_start_epoch = get_earlier_start_epoch(header.slot)
    later_start_epoch = get_later_start_epoch(header.slot)
    epoch = slot_to_epoch(header.slot)

    committee_count = max(
        earlier_validator_count // (SHARD_COUNT * TARGET_COMMITTEE_SIZE),
        later_validator_count // (SHARD_COUNT * TARGET_COMMITTEE_SIZE),
    ) + 1

    def get_offset(count: int, end: bool) -> int:
        return get_split_offset(
            count,
            SHARD_COUNT * committee_count,
            validator_memory.shard_id * committee_count + (1 if end else 0),
        )

    actual_earlier_committee = maximal_earlier_committee[
        0:get_offset(earlier_validator_count, True) - get_offset(earlier_validator_count, False)
    ]
    actual_later_committee = maximal_later_committee[
        0:get_offset(later_validator_count, True) - get_offset(later_validator_count, False)
    ]
    def get_switchover_epoch(index):
        return (
            bytes_to_int(hash(validator_memory.earlier_period_data.seed + int_to_bytes(index, length=3))[0:8]) %
            PERSISTENT_COMMITTEE_PERIOD
        )

    # Take not-yet-cycled-out validators from earlier committee and already-cycled-in validators from
    # later committee; return a sorted list of the union of the two, deduplicated
    return sorted(list(set(
        [i for i in actual_earlier_committee if epoch % PERSISTENT_COMMITTEE_PERIOD < get_switchover_epoch(i)] +
        [i for i in actual_later_committee if epoch % PERSISTENT_COMMITTEE_PERIOD >= get_switchover_epoch(i)]
    )))
```

Note that this method makes use of the fact that the committee for any given shard always starts and ends at the same validator index independently of the committee count (this is because the validator set is split into `SHARD_COUNT * committee_count` slices but the first slice of a shard is a multiple `committee_count * i`, so the start of the slice is `n * committee_count * i // (SHARD_COUNT * committee_count) = n * i // SHARD_COUNT`, using the slightly nontrivial algebraic identity `(x * a) // ab == x // b`).

## Verifying blocks

If a client wants to update its `finalized_header` it asks the network for a `BlockValidityProof`, which is simply:

```python
{
    'header': BeaconBlockHeader,
    'shard_aggregate_signature': BLSSignature,
    'shard_bitfield': 'bytes',
    'shard_parent_block': ShardBlock,
}
```

The verification procedure is as follows:

```python
def verify_block_validity_proof(proof: BlockValidityProof, validator_memory: ValidatorMemory) -> bool:
    assert proof.shard_parent_block.beacon_chain_root == hash_tree_root(proof.header)
    committee = compute_committee(proof.header, validator_memory)
    # Verify that we have >=50% support
    support_balance = sum([v.effective_balance for i, v in enumerate(committee) if get_bitfield_bit(proof.shard_bitfield, i) is True])
    total_balance = sum([v.effective_balance for i, v in enumerate(committee)])
    assert support_balance * 2 > total_balance
    # Verify shard attestations
    group_public_key = bls_aggregate_pubkeys([
        v.pubkey for v, index in enumerate(committee)
        if get_bitfield_bit(proof.shard_bitfield, index) is True
    ])
    assert bls_verify(
        pubkey=group_public_key,
        message_hash=hash_tree_root(shard_parent_block),
        signature=proof.shard_aggregate_signature,
        domain=get_domain(state, slot_to_epoch(shard_block.slot), DOMAIN_SHARD_ATTESTER),
    )
```

The size of this proof is only 200 (header) + 96 (signature) + 16 (bitfield) + 352 (shard block) = 664 bytes. It can be reduced further by replacing `ShardBlock` with `MerklePartial(lambda x: x.beacon_chain_root, ShardBlock)`, which would cut off ~220 bytes.
