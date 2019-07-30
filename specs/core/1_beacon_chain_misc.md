# Phase 1 miscellaneous beacon chain changes

## Table of contents

<!-- TOC -->

- [Helpers](#helpers)
      - [pack_compact_validator](#pack_compact_validator)
      - [unpack_compact_validator](#unpack_compact_validator)
      - [committee_to_compact_committee](#committee_to_compact_committee)
- [Changes](#changes)
      - [Persistent committees](#persistent-committees)

<!-- /TOC -->

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

### `unpack_compact_validator`

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


#### `concat_generalized_indices`

```python
def concat_generalized_indices(*indices: Sequence[GeneralizedIndex]) -> GeneralizedIndex:
    o = GeneralizedIndex(1)
    for i in indices:
        o = o * get_previous_power_of_2(i) + i
    return o
```

#### `compute_historical_state_generalized_index`

```python
def compute_historical_state_generalized_index(frm: ShardSlot, to: ShardSlot) -> GeneralizedIndex:
    o = GeneralizedIndex(1)
    for i in range(63, -1, -1):
          if (to-1) & 2**i > (frm-1) & 2**i:
              to = to - ((to-1) % 2**i) - 1
              o = concat_generalized_indices(o, get_generalized_index(ShardState, 'history_acc', i))
    return o
```

#### `get_generalized_index_of_crosslink_header`

```python
def get_generalized_index_of_crosslink_header(index: int) -> GeneralizedIndex:
    MAX_CROSSLINK_SIZE = SHARD_BLOCK_SIZE_LIMIT * SHARD_SLOTS_PER_BEACON_SLOT * SLOTS_PER_EPOCH * MAX_EPOCHS_PER_CROSSLINK
    assert MAX_CROSSLINK_SIZE == get_previous_power_of_2(MAX_CROSSLINK_SIZE)
    return GeneralizedIndex(MAX_CROSSLINK_SIZE // SHARD_HEADER_SIZE + index)
```

#### `process_shard_receipt`

```python
def process_shard_receipt(state: BeaconState, shard: Shard, proof: List[Hash, PLACEHOLDER], receipt: List[ShardReceiptDelta, PLACEHOLDER]):
    receipt_slot = state.next_shard_receipt_period[shard] * SLOTS_PER_EPOCH * EPOCHS_PER_SHARD_PERIOD
    first_slot_in_last_crosslink = state.current_crosslinks[shard].start_epoch * SLOTS_PER_EPOCH
    gindex = concat_generalized_indices(
        get_generalized_index_of_crosslink_header(0),
        get_generalized_index(ShardBlockHeader, 'state_root')
        compute_historical_state_generalized_index(receipt_slot, first_slot_in_last_crosslink)
        get_generalized_index(ShardState, 'receipt_root')
    )
    assert verify_merkle_proof(
        leaf=hash_tree_root(receipt),
        proof=proof,
        index=gindex,
        root=state.current_crosslinks[shard].data_root
    )
```

## Changes

### Persistent committees

Add to the beacon state the following fields:

* `previous_persistent_committee_root: Hash`
* `current_persistent_committee_root: Hash`
* `next_persistent_committee_root: Hash`
* `next_shard_receipt_period: Vector[uint, SHARD_COUNT]`, values initialized to `PHASE_1_FORK_SLOT // SLOTS_PER_EPOCH // EPOCHS_PER_SHARD_PERIOD`

Process the following function before `process_final_updates`:

```python
def update_persistent_committee(state: BeaconState):
    if (get_current_epoch(state) + 1) % EPOCHS_PER_SHARD_PERIOD == 0:
        state.previous_persistent_committee_root = state.current_persistent_committee_root
        state.current_persistent_committee_root = state.next_persistent_committee_root
        committees = Vector[CompactCommittee, SHARD_COUNT]([
            committee_to_compact_committee(state, get_period_committee(state, get_current_epoch(state) + 1, i))
            for i in range(SHARD_COUNT)
        ])
        state.next_persistent_committee_root = hash_tree_root(committees)
```
