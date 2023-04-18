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
    validator_indexes = []  # type: List[ValidatorIndex]
    for i in get_committee_count_per_slot(state, epoch):
        validator_indexes.append(get_beacon_committee(state, slot, i))

    return validator_indexes
```

```python
def get_beacon_committee_weight_between_slots(state: BeaconState, from_slot: Slot, to_slot: Slot) -> Gwei:
    validator_index_set = set()
    for slot in range(from_slot, to_slot + 1):
        validator_index_set.add(set(get_complete_beacon_committee_at_slot(state, Slot(slot))))

    total_weight = Gwei(0)

    for validator_index in validator_index_set:
        total_weight += state.validators[validator_index].effective_balance

    return total_weight
```

```python
def isOneConfirmed(store: Store, max_adversary_percentage: int, block_root: Root, current_slot: Slot) -> bool:
    block = store.blocks[block_root]
    justified_checkpoint_state = store.checkpoint_states[store.justified_checkpoint]
    parent_block = store.blocks[block.parent_root]
    support = get_weight(store, block_root)
    maximum_support = get_beacon_committee_weight_between_slots(justified_checkpoint_state, Slot(parent_block.slot + 1), current_slot)

    committee_weight = get_total_active_balance(justified_checkpoint_state) // SLOTS_PER_EPOCH
    proposer_score = (committee_weight * PROPOSER_SCORE_BOOST) // 100

    # support / maximum_support > 1/2 * (1 + proposer_score / maximum_support) + max_adversary_percentage/100 =
    # support / maximum_support > 1/2 + proposer_score / (2 * maximum_support) + max_adversary_percentage/100
    # multiply both sides by (maximum_support * 100) =>
    return support * 100 > 50 * maximum_support + 50 * proposer_score + max_adversary_percentage * maximum_support
```

```python
def isLMDConfirmed(store: Store, max_adversary_percentage: int, block_root: Root, current_slot: Slot) -> bool:
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
                isLMDConfirmed(store, max_adversary_percentage, block.parent_root, current_slot)
            )
```


```python
def get_ffg_voting_weight_in_current_epoch_until_current_slot(state: BeaconState, current_slot: Slot) -> Gwei:
    first_slot_current_epoch = compute_start_slot_at_epoch(compute_epoch_at_slot(current_slot))
    return get_beacon_committee_weight_between_slots(state, first_slot_current_epoch, current_slot)

```

```python
def get_remaining_ffg_voting_weight_to_the_end_of_the_current_epoch(state: BeaconState, current_slot: Slot) -> Gwei:
    first_slot_next_epoch = compute_start_slot_at_epoch(Epoch(compute_epoch_at_slot(current_slot) + 1))
    return get_beacon_committee_weight_between_slots(state, Slot(current_slot + 1), Slot(first_slot_next_epoch - 1))

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

```python
def get_ffg_weight_supporting_checkpoint_for_block(store: Store, block_root: Root) -> Gwei:

    block = store.blocks[block_root]
    assert get_current_epoch_store(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_epoch_store(store)

    leave_roots = get_leaf_block_roots(store, block_root)

    attestations_in_leaves: Set[PendingAttestation] = set().union(*[store.block_states[root].current_epoch_attestations for root in leave_roots])

    # The following could be replaced by get_checkpoint_block once merged in
    block_checkpoint_root = get_block_root(store.block_states[block_root], current_epoch)

    attestations_in_leaves_for_block_checkpoint = {a for a in attestations_in_leaves if a.data.target.root == block_checkpoint_root}

    block_checkpoint_state = store.block_states[block_checkpoint_root]

    return get_attesting_balance(block_checkpoint_state, list(attestations_in_leaves_for_block_checkpoint))

```

```python
def will_block_checkpoint_be_justified_by_end_of_the_current_epoch(
    store: Store, 
    max_adversary_percentage: int, 
    max_weight_adversary_is_willing_to_get_slashed: int, 
    block_root: Root
) -> bool:
    block = store.blocks[block_root]
    assert get_current_epoch_store(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_epoch_store(store)

    # The following could be replaced by get_checkpoint_block once merged in
    block_checkpoint_root = get_block_root(store.block_states[block_root], current_epoch) 
    block_checkpoint_state = store.block_states[block_checkpoint_root]   

    current_slot = get_current_slot(store)

    total_active_balance = get_total_active_balance(block_checkpoint_state)

    remaining_ffg_voting_weight = get_remaining_ffg_voting_weight_to_the_end_of_the_current_epoch(block_checkpoint_state, current_slot)

    ffg_weight_supporting_checkpoint_for_block_to_be_confirmed = get_ffg_weight_supporting_checkpoint_for_block(store, block_root)

    max_ffg_weight_the_adversary_can_subtract_from_ffg_support = min(
        get_ffg_voting_weight_in_current_epoch_until_current_slot(block_checkpoint_state, current_slot) * max_adversary_percentage / 100 + 1, 
        max_weight_adversary_is_willing_to_get_slashed
    )
    
    # ffg_weight_supporting_checkpoint_for_block_to_be_confirmed - max_ffg_weight_the_adversary_can_subtract_from_ffg_support + (1 - max_adversary_percentage/100) * remaining_ffg_voting_weight >= 2/3 * total_active_balance
    return ffg_weight_supporting_checkpoint_for_block_to_be_confirmed * 300 + (300 - 3 * max_adversary_percentage) * remaining_ffg_voting_weight - max_ffg_weight_the_adversary_can_subtract_from_ffg_support * 300 >= 200 * total_active_balance    
```

```python
def isConfirmed(
    store: Store, 
    max_adversary_percentage: int, 
    max_weight_adversary_is_willing_to_get_slashed: int, 
    block_root: Root
) -> bool:
    current_slot = get_current_slot(store)
    current_epoch = get_current_epoch_store(store)

    block_state = store.block_states[block_root]

    return (
        isLMDConfirmed(store, max_adversary_percentage, block_root, current_slot) and
        will_block_checkpoint_be_justified_by_end_of_the_current_epoch(store, max_adversary_percentage, max_weight_adversary_is_willing_to_get_slashed, block_root) and
        block_state.current_justified_checkpoint.epoch + 1 == current_epoch
    )

```

## `get_safe_execution_payload_hash`

```python
def get_safe_execution_payload_hash(store: Store) -> Hash32:
    # TBD   
    store
    return None
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

*Note*: This helper uses beacon block container extended in [Bellatrix](../specs/bellatrix/beacon-chain.md).
