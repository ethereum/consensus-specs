# Fork Choice -- Confirmation Rule

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [`get_safe_execution_payload_hash`](#get_safe_execution_payload_hash)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

TBD

## Block confirmation rule

```python
def get_current_epoch_store(store: Store) -> Epoch:
    current_slot = get_current_slot(store)
    return compute_epoch_at_slot(current_slot)    
```

```python
def get_complete_beacon_committee_at_slot(state: BeaconState, slot: Slot) -> Sequence[ValidatorIndex]:
    epoch = compute_epoch_at_slot(slot)
    validator_indexes = []
    for i in get_committee_count_per_slot(state, epoch):
        validator_indexes.append(get_beacon_committee(state, slot, i))

    return validator_indexes
```

```python
def get_beacon_committee_weight_between_slots(state: BeaconState, from_slot: Slot, to_slot: Slot) -> Gwei:
    validator_index_set = set()
    for slot in range(from_slot, to_slot + 1):
        validator_index_set.add(set(get_complete_beacon_committee_at_slot(state, slot)))

    total_weight = 0

    for validator_index in validator_index_set:
        total_weight += state.validators[validator_index].effective_balance

    return total_weight
```

```python
def get_ffg_weight_supporting_checkpoint_for_block(store: Store, block_root: Root):
    state = store.block_states[block_root]
    assert get_current_epoch_store(store) == get_current_epoch(state)
    current_attestations = get_matching_target_attestations(state, get_current_epoch(state))
    return get_attesting_balance(state, current_attestations)

```

```python
def isOneConfirmed(store: Store, max_adversary_percentage: int, block_root: Root, current_slot: Slot) -> bool:
    block = store.blocks[block_root]
    justified_checkpoint_state = store.checkpoint_states[store.justified_checkpoint]
    parent_block = store.blocks[block.parent]
    support = get_weight(store, block_root)
    maximum_weight = get_beacon_committee_weight_between_slots(justified_checkpoint_state, parent_block.slot + 1, current_slot)
    return support * 200 >= (1 + 2 * max_adversary_percentage) * maximum_weight
```

```python
def isLMDConfirmed(store: Store, max_adversary_percentage: int, block_root: Root, current_slot: Slot):
    if block_root == store.finalized_checkpoint.root:
        return True 
    else:
        block = store.blocks[block_root]
        finalized_block = store.blocks[store.finalized_checkpoint.root]
        if block.slot <= finalized_block.slot:
            return False
        else:
            return (
                isOneConfirmed(store, max_adversary_percentage, block_root, current_slot) and
                isLMDConfirmed(store, max_adversary_percentage, block.parent, current_slot)
            )
```

```python
def get_remaining_ffg_voting_weight_to_the_end_of_the_current_epoch(store: Store, block_root: Root, current_slot: Slot):
    state = store.block_states[block_root]
    first_slot_next_epoch = compute_start_slot_at_epoch(get_current_epoch(state) + 1) 
    return get_beacon_committee_weight_between_slots(current_slot + 1, first_slot_next_epoch - 1)

```

```python
def isConfirmed(store: Store, max_adversary_percentage: int, block_root: Root):
    block = store.blocks[block_root]
    current_epoch = get_current_epoch_store(store)

    assert compute_epoch_at_slot(block.slot) == current_epoch

    block_state = store.block_states[block_root]
    current_slot = get_current_slot(store)

    block_checkpoint_state = store.block_states[block_state.current_justified_checkpoint]

    total_active_balance = get_total_active_balance(block_checkpoint_state)
    remaining_ffg_voting_weight = get_remaining_ffg_voting_weight_to_the_end_of_the_current_epoch(store, block_root, current_slot)
    ffg_weight_supporting_checkpoint_for_block_to_be_confirmed = get_ffg_weight_supporting_checkpoint_for_block(store, block_root)

    block_to_be_confirmed_will_be_justified_by_the_end_of_the_epoch = ffg_weight_supporting_checkpoint_for_block_to_be_confirmed * 300 + 100 - 3 * max_adversary_percentage * remaining_ffg_voting_weight >= 200 * total_active_balance

    return (
        isLMDConfirmed(store, max_adversary_percentage, block_root, current_slot) and
        block_to_be_confirmed_will_be_justified_by_the_end_of_the_epoch and
        block_state.current_justified_checkpoint.epoch + 1 == current_epoch
    )

```

## `get_safe_execution_payload_hash`

```python
def get_safe_execution_payload_hash(store: Store) -> Hash32:
    # TBD   
    pass
```

## Old functions kept for reference

```python
def get_descendants_in_current_epoch(store: Store, block_root: Root) -> Set[Root]:
    block = store.blocks[block_root]
    children = [
        root for root in store.blocks.keys()
        if store.blocks[root].parent_root == block_root
    ] 

    descendants = set()
    current_epoch = compute_epoch_at_slot(get_current_slot(store))

    if compute_epoch_at_slot(block.slot) == current_epoch:
        descendants.add(block_root)

    if any(children):
        for child in children:
            descendants.update(get_descendants_in_current_epoch(store, child))

    return descendants
```

```python
def get_leaf_block_roots(store: Store, block_root: Root) -> Set[Root]:
    children = [
        root for root in store.blocks.keys()
        if store.blocks[root].parent_root == block_root
    ] 

    if any(children):
        leaves = set()
        for child in children:
            leaves.update(get_leaf_block_roots(store, child))

        return leaves        
    else:
        return set([block_root])

```

*Note*: This helper uses beacon block container extended in [Bellatrix](../specs/bellatrix/beacon-chain.md).
