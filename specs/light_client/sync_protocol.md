# Beacon Chain Light Client Syncing

**Notice**: This document is a work-in-progress for researchers and implementers. One of the design goals of the Eth 2.0 beacon chain is light-client friendliness, not only to allow low-resource clients (mobile phones, IoT, etc.) to maintain access to the blockchain in a reasonably safe way, but also to facilitate the development of "bridges" between the Eth 2.0 beacon chain and other chains.

## Table of contents

<!-- TOC -->

- [Beacon Chain Light Client Syncing](#beacon-chain-light-client-syncing)
    - [Table of contents](#table-of-contents)
    - [Preliminaries](#preliminaries)
        - [Beacon chain changes](#beacon-chain-changes)
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

### Beacon chain changes

Add three roots to the state: `next_persistent_committee_root`, `current_persistent_committee_root`, `previous_persistent_committee_root`, which are updated at period boundary slots and are set to `hash_tree_root([committee_to_compact_committee(state, get_period_committee(state, get_current_epoch(state) - EPOCHS_PER_SHARD_PERIOD * k, i) for i in range(1024))])` where `k` equals 0 for the next committee, 1 for the current committee and 2 for the previous committee.

### Expansions

We define an "expansion" of an object as an object where a field in an object that is meant to represent the `hash_tree_root` of another object is replaced by the object. Note that defining expansions is not a consensus-layer-change; it is merely a "re-interpretation" of the object. Particularly, the `hash_tree_root` of an expansion of an object is identical to that of the original object, and we can define expansions where, given a complete history, it is always possible to compute the expansion of any object in the history. The opposite of an expansion is a "summary" (e.g. `BeaconBlockHeader` is a summary of `BeaconBlock`).

We define two expansions:

* `ExtendedBeaconState`, which is identical to a `BeaconState` except each of `(next, current, previous)_persistent_committee_root` are replaced by the corresponding `CompactCommittee`.
* `ExtendedBeaconBlock`, which is identical to a `BeaconBlock` except `state_root` is replaced with the corresponding `state: ExtendedBeaconState`.

### `MerklePartial`

A `MerklePartial(f, *args)` is an object that contains a minimal Merkle proof needed to compute `f(*args)`. A `MerklePartial` can be used in place of a regular SSZ object, though a computation would return an error if it attempts to access part of the object that is not contained in the proof.

### Light client state

A light client will keep track of:

* A random `shard_id` in `[0...SHARD_COUNT-1]` (selected once and retained forever)
* A block header that they consider to be finalized (`finalized_header`) and do not expect to revert.
* `previous_committee = finalized_header.previous_persistent_committees[shard_id]`
* `current_committee = finalized_header.current_persistent_committees[shard_id]`
* `next_committee = finalized_header.next_persistent_committees[shard_id]`

We use the struct `ValidatorMemory` to keep track of these variables.

### Updating the shuffled committee

If a client's `validator_memory.finalized_header` changes so that `header.slot // EPOCHS_PER_SHARD_PERIOD` increases, then `(previous, current)_committee` will be set to `(current, next)_committee`, but `next_committee` will need to be updated, by downloading `validator_memory.finalized_header.state.next_persistent_committees[shard_id]`.

The maximum size of a proof for this new data is `32 * 10` (Merkle branch) + `56 * 128` (committee) `= 14336` bytes for a compact committee. This needs to be done once per `EPOCHS_PER_SHARD_PERIOD` epochs (256 epochs, or 27 hours), or ~0.146 bytes per second (compare Bitcoin SPV at 80 / 560 ~= 0.143 bytes per second).

### Computing the persistent committee at an epoch

```
def compute_persistent_committee_at_epoch(memory: ValidatorMemory,
                                         epoch: Epoch) -> Sequence[Tuple[BLSPubkey, Gwei]]:
    current_period = memory.finalized_header.slot // SLOTS_PER_EPOCH // EPOCHS_PER_SHARD_PERIOD
    target_period = epoch // EPOCHS_PER_SHARD_PERIOD
    if target_period == current_period + 1:
        earlier_committee, later_committee = memory.current_committee, memory.next_committee
    elif target_period == current_period:
        earlier_committee, later_committee = memory.previous_committee, memory.current_committee
    else:
        raise Exception("Cannot compute for this slot")
    o = []
    for pub, aux in zip(earlier_committee.pubkeys, earlier_committee.compact_validators):
        if epoch % EPOCHS_PER_SHARD_PERIOD < (aux >> 16) % EPOCHS_PER_SHARD_PERIOD:
            o.append((pub, aux & (2**15-1))
    for pub, aux in zip(later_committee.pubkeys, later_committee.compact_validators):
        if epoch % EPOCHS_PER_SHARD_PERIOD >= (aux >> 16) % EPOCHS_PER_SHARD_PERIOD:
            o.append((pub, aux & (2**15-1))
    return o
```

## Verifying blocks

If a client wants to update its `finalized_header` it asks the network for a `BlockValidityProof`, which is simply:

```python
{
    'beacon_block_header': BeaconBlockHeader,
    'shard_aggregate_signature': BLSSignature,
    'shard_aggregation_bits': Bitlist[PLACEHOLDER],
    'shard_parent_block': ShardBlock,
}
```

The verification procedure is as follows:

```python
def verify_block_validity_proof(proof: BlockValidityProof, validator_memory: ValidatorMemory) -> bool:
    assert proof.shard_parent_block.core.beacon_chain_root == hash_tree_root(proof.beacon_block_header)
    committee = compute_persistent_committee_at_slot(validator_memory, compute_epoch_of_shard_slot(shard_parent_block.slot))
    # Verify that we have >=50% support
    support_balance = sum([balance for i, (pubkey, balance) in enumerate(committee) if proof.shard_aggregation_bits[i]])
    total_balance = sum([balance for i, (pubkey, balance) in enumerate(committee)])
    assert support_balance * 2 > total_balance
    # Verify shard attestations
    group_public_key = bls_aggregate_pubkeys([
        pubkey for i, (pubkey, balance) in enumerate(committee) if proof.shard_aggregation_bits[i]
    ])
    assert bls_verify(
        pubkey=group_public_key,
        message_hash=hash_tree_root(shard_parent_block),
        signature=proof.shard_aggregate_signature,
        domain=get_domain(state, compute_epoch_of_slot(shard_block.slot), DOMAIN_SHARD_ATTESTER),
    )
```

The size of this proof is only 200 (header) + 96 (signature) + 16 (bits) + 352 (shard block) = 664 bytes. It can be reduced further by replacing `ShardBlock` with `MerklePartial(lambda x: x.beacon_chain_root, ShardBlock)`, which would cut off ~220 bytes.
