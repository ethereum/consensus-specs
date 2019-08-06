# Phase 1 miscellaneous beacon chain changes

## Table of contents

<!-- TOC -->

- [Phase 1 miscellaneous beacon chain changes](#phase-1-miscellaneous-beacon-chain-changes)
    - [Table of contents](#table-of-contents)
    - [Classes](#classes)
        - [CompactCommittee](#compactcommittee)
        - [ShardReceiptProof](#shardreceiptproof)
    - [Helpers](#helpers)
        - [pack_compact_validator](#pack_compact_validator)
        - [unpack_compact_validator](#unpack_compact_validator)
        - [committee_to_compact_committee](#committee_to_compact_committee)
        - [get_previous_power_of_2](#get_previous_power_of_2)
        - [verify_merkle_proof](#verify_merkle_proof)
        - [concat_generalized_indices](#concat_generalized_indices)
        - [compute_historical_state_generalized_index](#compute_historical_state_generalized_index)
        - [get_generalized_index_of_crosslink_header](#get_generalized_index_of_crosslink_header)
        - [process_shard_receipt](#process_shard_receipt)
    - [Changes](#changes)
        - [Persistent committees](#persistent-committees)
        - [Shard receipt processing](#shard-receipt-processing)

<!-- /TOC -->

## Classes

#### `CompactCommittee`

```python
class CompactCommittee(Container):
    pubkeys: List[BLSPubkey, MAX_VALIDATORS_PER_COMMITTEE]
    compact_validators: List[uint64, MAX_VALIDATORS_PER_COMMITTEE]
```

#### `ShardReceiptProof`

```python
class ShardReceiptProof(Container):
    shard: Shard
    proof: List[Hash, PLACEHOLDER]
    receipt: List[ShardReceiptDelta, PLACEHOLDER]
```

## Helpers

#### `pack_compact_validator`

```python
def pack_compact_validator(index: uint64, slashed: bool, balance_in_increments: uint64) -> uint64:
    """
    Creates a compact validator object representing index, slashed status, and compressed balance.
    Takes as input balance-in-increments (// EFFECTIVE_BALANCE_INCREMENT) to preserve symmetry with
    the unpacking function.
    """
    return (index << 16) + (slashed << 15) + balance_in_increments
```

#### `unpack_compact_validator`

```python
def unpack_compact_validator(compact_validator: uint64) -> Tuple[uint64, bool, uint64]:
    """
    Returns validator index, slashed, balance // EFFECTIVE_BALANCE_INCREMENT
    """
    return compact_validator >> 16, (compact_validator >> 15) % 2, compact_validator & (2**15 - 1)
```

#### `committee_to_compact_committee`

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

#### `get_previous_power_of_2`

```python
def get_previous_power_of_2(x: int) -> int:
    return x if x <= 2 else 2 * get_previous_power_of_2(x // 2)
```

#### `verify_merkle_proof`

```python
def verify_merkle_proof(leaf: Hash, proof: Sequence[Hash], index: GeneralizedIndex, root: Hash) -> bool:
    assert len(proof) == get_generalized_index_length(index)
    for i, h in enumerate(proof):
        if get_generalized_index_bit(index, i):
            leaf = hash(h + leaf)
        else:
            leaf = hash(leaf + h)
    return leaf == root
```

#### `compute_historical_state_generalized_index`

```python
def compute_historical_state_generalized_index(earlier: ShardSlot, later: ShardSlot) -> GeneralizedIndex:
    """
    Computes the generalized index of the state root of slot `frm` based on the state root of slot `to`.
    Relies on the `history_acc` in the `ShardState`, where `history_acc[i]` maintains the most recent 2**i'th
    slot state. Works by tracing a `log(later-earlier)` step path from `later` to `earlier` through intermediate
    blocks at the next available multiples of descending powers of two.
    """
    o = GeneralizedIndex(1)
    for i in range(63, -1, -1):
        if (later - 1) & 2**i > (earlier - 1) & 2**i:
            later = later - ((later - 1) % 2**i) - 1
            o = concat_generalized_indices(o, get_generalized_index(ShardState, 'history_acc', i))
    return o
```

#### `get_generalized_index_of_crosslink_header`

```python
def get_generalized_index_of_crosslink_header(index: int) -> GeneralizedIndex:
    """
    Gets the generalized index for the root of the index'th header in a crosslink.
    """
    MAX_CROSSLINK_SIZE = SHARD_BLOCK_SIZE_LIMIT * SHARD_SLOTS_PER_BEACON_SLOT * SLOTS_PER_EPOCH * MAX_EPOCHS_PER_CROSSLINK
    assert MAX_CROSSLINK_SIZE == get_previous_power_of_2(MAX_CROSSLINK_SIZE)
    return GeneralizedIndex(MAX_CROSSLINK_SIZE // SHARD_HEADER_SIZE + index)
```

#### `process_shard_receipt`

```python
def process_shard_receipt(state: BeaconState, receipt_proof: ShardReceiptProof):
    """
    Processes a ShardReceipt object.
    """
    receipt_slot = state.next_shard_receipt_period[receipt_proof.shard] * SLOTS_PER_EPOCH * EPOCHS_PER_SHARD_PERIOD
    first_slot_in_last_crosslink = state.current_crosslinks[receipt_proof.shard].start_epoch * SLOTS_PER_EPOCH
    gindex = concat_generalized_indices(
        get_generalized_index_of_crosslink_header(0),
        get_generalized_index(ShardBlockHeader, 'state_root'),
        compute_historical_state_generalized_index(receipt_slot, first_slot_in_last_crosslink),
        get_generalized_index(ShardState, 'receipt_root')
    )
    assert verify_merkle_proof(
        leaf=hash_tree_root(receipt_proof.receipt),
        proof=receipt_proof.proof,
        index=gindex,
        root=state.current_crosslinks[shard].data_root
    )
    for delta in receipt_proof.receipt:
        increase_balance(state, delta.index, state.validators[delta.index].effective_balance * delta.reward_coefficient // REWARD_COEFFICIENT_BASE)
        decrease_balance(state, delta.index, delta.block_fee)
    state.next_shard_receipt_period[receipt_proof.shard] += 1
    increase_balance(state, get_beacon_proposer_index(state), MICRO_REWARD)
```

## Changes

### Persistent committees

Add to the beacon state the following fields:

```python
# begin insert @persistent_committee_fields
    previous_persistent_committee_root: Hash
    current_persistent_committee_root: Hash
    next_persistent_committee_root: Hash
    next_shard_receipt_period: Vector[uint, SHARD_COUNT]
# end insert @persistent_committee_fields
```
`next_shard_receipt_period` values initialized to `PHASE_1_FORK_SLOT // SLOTS_PER_EPOCH // EPOCHS_PER_SHARD_PERIOD`

Run `update_persistent_committee` immediately before `process_final_updates`:

```python
# begin insert @update_persistent_committee
    update_persistent_committee(state)
# end insert @update_persistent_committee
def update_persistent_committee(state: BeaconState) -> None:
    """
    Updates persistent committee roots at boundary blocks.
    """
    if (get_current_epoch(state) + 1) % EPOCHS_PER_SHARD_PERIOD == 0:
        state.previous_persistent_committee_root = state.current_persistent_committee_root
        state.current_persistent_committee_root = state.next_persistent_committee_root
        committees = Vector[CompactCommittee, SHARD_COUNT]([
            committee_to_compact_committee(state, get_period_committee(state, get_current_epoch(state) + 1, i))
            for i in range(SHARD_COUNT)
        ])
        state.next_persistent_committee_root = hash_tree_root(committees)
```

### Shard receipt processing

Add the `shard_receipts` operation to `BeaconBlockBody`:

```python
# begin insert @shard_receipts
    shard_receipts: List[ShardReceipt, MAX_SHARD_RECEIPTS]
# end insert @shard_receipts
```

Use `process_shard_receipt` to process each receipt.

```python
# begin insert @process_shard_receipts
        (body.shard_receipts, process_shard_receipts),
# end insert @process_shard_receipts
```
