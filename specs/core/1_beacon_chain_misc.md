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

## Changes

### Persistent committees

Add to the beacon state the following fields:

* `previous_persistent_committee_root: Hash`
* `current_persistent_committee_root: Hash`
* `next_persistent_committee_root: Hash`

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
