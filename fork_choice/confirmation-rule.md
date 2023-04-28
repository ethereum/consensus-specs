# Fork Choice -- Confirmation Rule

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Boolean Confirmation Rule](#boolean-confirmation-rule)
  - [Helper Functions](#helper-functions)
  - [Main Function](#main-function)
- [Confirmation Score](#confirmation-score)
  - [Helper Functions](#helper-functions-1)
  - [Main Function](#main-function-1)
- [`get_safe_execution_payload_hash`](#get_safe_execution_payload_hash)
  - [Helper](#helper)
  - [Main Function](#main-function-2)
- [Old functions kept for reference](#old-functions-kept-for-reference)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document specifies a confirmation rule for the Ethereum protocol. This rule provides fast confirmations at the cost of reduced safety, as compared to finality.

## Confirmation Rule

This section specifies an algorithm to determine whether a block is confirmed. The algorithm requires an input value for the maximum fraction of adversarial validators, `max_adversary_percentage`.

### Helper Functions


```python
def get_current_epoch_store(store: Store) -> Epoch:
    current_slot = get_current_slot(store)
    return compute_epoch_at_slot(current_slot)
```

```python
def get_full_committee_at_slot(state: BeaconState, slot: Slot) -> Sequence[ValidatorIndex]:
    epoch = compute_epoch_at_slot(slot)
    validator_indexes = []  # type: List[ValidatorIndex]
    for i in get_committee_count_per_slot(state, epoch):
        validator_indexes.append(get_beacon_committee(state, slot, i))

    return validator_indexes
```

```python
def get_committee_weight_between_slots(state: BeaconState, from_slot: Slot, to_slot: Slot) -> Gwei:
    validator_index_set = set()
    for slot in range(from_slot, to_slot + 1):
        validator_index_set.add(set(get_full_committee_at_slot(state, Slot(slot))))

    total_weight = Gwei(0)

    for validator_index in validator_index_set:
        total_weight += state.validators[validator_index].effective_balance

    return total_weight
```

```python
def is_one_confirmed(store: Store, max_adversary_percentage: int, block_root: Root, current_slot: Slot) -> bool:
    block = store.blocks[block_root]
    justified_checkpoint_state = store.checkpoint_states[store.justified_checkpoint]
    parent_block = store.blocks[block.parent_root]
    support = int(get_weight(store, block_root))
    maximum_support = int(get_committee_weight_between_slots(justified_checkpoint_state, Slot(parent_block.slot + 1), current_slot))

    committee_weight = get_total_active_balance(justified_checkpoint_state) // SLOTS_PER_EPOCH
    proposer_score = int((committee_weight * PROPOSER_SCORE_BOOST) // 100)

    # support / maximum_support > 1/2 * (1 + proposer_score / maximum_support) + max_adversary_percentage/100 =>
    return 100 * support > 50 * maximum_support + 50 * proposer_score + max_adversary_percentage * maximum_support
```

```python
def is_LMD_confirmed(store: Store, max_adversary_percentage: int, block_root: Root, current_slot: Slot) -> bool:
    if block_root == store.finalized_checkpoint.root:
        return True
    else:
        block = store.blocks[block_root]
        finalized_block = store.blocks[store.finalized_checkpoint.root]
        if block.slot <= finalized_block.slot:
            return False
        else:
            return (
                is_one_confirmed(store, max_adversary_percentage, block_root, current_slot) and
                is_LMD_confirmed(store, max_adversary_percentage, block.parent_root, current_slot)
            )
```

```python
def get_current_vote_weight_in_epoch(state: BeaconState, current_slot: Slot) -> Gwei:
    # Returns the total weight of votes for this epoch from committees up til the current slot
    first_slot_current_epoch = compute_start_slot_at_epoch(compute_epoch_at_slot(current_slot))
    return get_committee_weight_between_slots(state, first_slot_current_epoch, current_slot)
```

```python
def get_future_vote_weight_in_epoch(state: BeaconState, current_slot: Slot) -> Gwei:
    # Returns the total weight of votes for this epoch from future committees after the current slot
    first_slot_next_epoch = compute_start_slot_at_epoch(Epoch(compute_epoch_at_slot(current_slot) + 1))
    return get_committee_weight_between_slots(state, Slot(current_slot + 1), Slot(first_slot_next_epoch - 1))
```

NOTE: The following should be removed once PR#3308 is merged

```python
def get_checkpoint_block(store: Store, root: Root, epoch: Epoch) -> Root:
    """
    Compute the checkpoint block for epoch ``epoch`` in the chain of block ``root``
    """
    epoch_first_slot = compute_start_slot_at_epoch(epoch)
    return get_ancestor(store, root, epoch_first_slot)
```

```python
def get_leaf_block_roots(store: Store, block_root: Root) -> Set[Root]:
    children = [
        root for root in store.blocks.keys()
        if store.blocks[root].parent_root == block_root
    ]

    if any(children):
        leaves = set().union(*[get_leaf_block_roots(store, child) for child in children])

        return leaves
    else:
        return set(block_root)

```

```python
def get_ffg_support(store: Store, block_root: Root) -> Gwei:
    # Returns the total weight supporting the highest checkpoint in the block's chain

    block = store.blocks[block_root]
    assert get_current_epoch_store(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_epoch_store(store)

    leave_roots = get_leaf_block_roots(store, block_root)

    # current_epoch_attestations contains only attestations with source matching block.current_justified_checkpoint
    attestations_in_leaves: Set[PendingAttestation] = set().union(*[store.block_states[root].current_epoch_attestations for root in leave_roots])

    block_checkpoint_root = get_checkpoint_block(store, block_root, current_epoch)

    attestations_in_leaves_for_block_checkpoint = {a for a in attestations_in_leaves if a.data.target.root == block_checkpoint_root}

    block_checkpoint_state = store.block_states[block_checkpoint_root]

    return get_attesting_balance(block_checkpoint_state, list(attestations_in_leaves_for_block_checkpoint))
```

```python
def is_ffg_confirmed(
    # Returns whether the branch will justify it's current epoch checkpoint at the end of this epoch
    store: Store,
    max_adversary_percentage: int,
    max_adversarial_slashing: int,
    block_root: Root,
    current_slot: Slot
) -> bool:
    block = store.blocks[block_root]
    assert get_current_epoch_store(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_epoch_store(store)

    # The following could be replaced by get_checkpoint_block once merged in
    block_checkpoint_root = get_block_root(store.block_states[block_root], current_epoch)
    block_checkpoint_state = store.block_states[block_checkpoint_root]

    total_active_balance = int(get_total_active_balance(block_checkpoint_state))

    remaining_ffg_voting_weight = int(get_future_vote_weight_in_epoch(block_checkpoint_state, current_slot))

    ffg_weight_supporting_checkpoint_for_block_to_be_confirmed = int(get_ffg_support(store, block_root))

    max_ffg_weight_the_adversary_can_subtract_from_ffg_support = int(
        min(
            get_current_vote_weight_in_epoch(block_checkpoint_state, current_slot) * max_adversary_percentage / 100 + 1,
            max_adversarial_slashing,
            ffg_weight_supporting_checkpoint_for_block_to_be_confirmed
        )
    )

    # ffg_weight_supporting_checkpoint_for_block_to_be_confirmed - max_ffg_weight_the_adversary_can_subtract_from_ffg_support + (1 - max_adversary_percentage/100) * remaining_ffg_voting_weight >= 2/3 * total_active_balance =>
    return ffg_weight_supporting_checkpoint_for_block_to_be_confirmed * 300 + (300 - 3 * max_adversary_percentage) * remaining_ffg_voting_weight - max_ffg_weight_the_adversary_can_subtract_from_ffg_support * 300 >= 200 * total_active_balance
```

### Main Function

```python
def is_confirmed(
    store: Store,
    max_adversary_percentage: int,
    max_adversarial_slashing: int,
    block_root: Root
) -> bool:
    current_slot = get_current_slot(store)
    current_epoch = get_current_epoch_store(store)

    block = store.blocks[block_root]
    block_state = store.block_states[block_root]

    # We can only apply isConfirmed to blocks created in the current epoch
    assert compute_epoch_at_slot(block.slot) == current_epoch

    return (
        is_LMD_confirmed(store, max_adversary_percentage, block_root, current_slot) and
        is_ffg_confirmed(store, max_adversary_percentage, max_adversarial_slashing, block_root, current_slot) and
        block_state.current_justified_checkpoint.epoch + 1 == current_epoch
    )
```

## Confirmation Score

The confirmation score for a block is the maximum adversarial percentage weight that a confirmed block can tolerate.
This section specifies the algorithm to calculate the confirmation score of a given block.
This under the assumption that the adversary is willing to get as much stake as possible slashed to
prevent a block from being confirmed.

### Helper Functions

```python
def get_score_for_one_confirmation(store: Store, block_root: Root, current_slot: Slot) -> int:
    block = store.blocks[block_root]
    justified_checkpoint_state = store.checkpoint_states[store.justified_checkpoint]
    parent_block = store.blocks[block.parent_root]
    support = int(get_weight(store, block_root))
    maximum_support = int(get_committee_weight_between_slots(justified_checkpoint_state, Slot(parent_block.slot + 1), current_slot))

    committee_weight = get_total_active_balance(justified_checkpoint_state) // SLOTS_PER_EPOCH
    proposer_score = int((committee_weight * PROPOSER_SCORE_BOOST) // 100)

    # We need to return a value max_adversary_percentage such that the following inequality is true
    # 100 * support > 50 * maximum_support + 50 * proposer_score + max_adversary_percentage * maximum_support
    # the "-1" in the numerator is to return a "<=" rather than a "<" value
    return (100 * support - 50 * proposer_score - 1) // maximum_support - 50
```

```python
def get_score_for_LMD_confirmation(store: Store, block_root: Root, current_slot: Slot) -> int:
    if block_root == store.finalized_checkpoint.root:
        return 100 // 3
    else:
        block = store.blocks[block_root]
        finalized_block = store.blocks[store.finalized_checkpoint.root]
        if block.slot <= finalized_block.slot:
            return -1
        else:
            return min(
                get_score_for_one_confirmation(store, block_root, current_slot),
                get_score_for_LMD_confirmation(store, block.parent_root, current_slot)
            )
```

```python
def get_score_for_FFG_confirmation(
    store: Store,
    block_root: Root,
    current_slot: Slot
) -> int:
    block = store.blocks[block_root]
    assert get_current_epoch_store(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_epoch_store(store)

    # The following could be replaced by get_checkpoint_block once merged in
    block_checkpoint_root = get_block_root(store.block_states[block_root], current_epoch)
    block_checkpoint_state = store.block_states[block_checkpoint_root]

    total_active_balance = int(get_total_active_balance(block_checkpoint_state))

    ffg_voting_weight_so_far = get_current_vote_weight_in_epoch(block_checkpoint_state, current_slot)

    remaining_ffg_voting_weight = int(get_future_vote_weight_in_epoch(block_checkpoint_state, current_slot))

    ffg_weight_supporting_checkpoint_for_block_to_be_confirmed = int(get_ffg_support(store, block_root))

    # We assume max_adversarial_slashing = + infinity
    # So, we want to return a value max_adversary_percentage such that the following statement is true

    # ffg_weight_supporting_checkpoint_for_block_to_be_confirmed
    # - min(ffg_weight_supporting_checkpoint_for_block_to_be_confirmed, ffg_voting_weight_so_far  * max_adversary_percentage / 100)
    # + (1 - max_adversary_percentage/100) * remaining_ffg_voting_weight
    # >= 2/3 * total_active_balance

    # First, we check whether max_adversary_percentage >= ffg_weight_supporting_checkpoint_for_block_to_be_confirmed / ffg_voting_weight_so_far * 100
    # To do this we check whether in the case that max_adversary_percentage == ffg_weight_supporting_checkpoint_for_block_to_be_confirmed / ffg_voting_weight_so_far * 100
    # our target statement is true
    # This amount to checking that
    # (1 - ffg_weight_supporting_checkpoint_for_block_to_be_confirmed / ffg_voting_weight_so_far) * remaining_ffg_voting_weight >= 2/3 * total_active_balance
    # multiplying each side by 3 * ffg_voting_weight_so_far, we get (assuming ffg_voting_weight_so_far != 0):

    if ffg_voting_weight_so_far > 0 and 3 * (ffg_voting_weight_so_far - ffg_weight_supporting_checkpoint_for_block_to_be_confirmed) * remaining_ffg_voting_weight >= 2 * total_active_balance * ffg_voting_weight_so_far:
        # We know that max_adversary_percentage >= ffg_weight_supporting_checkpoint_for_block_to_be_confirmed / ffg_voting_weight_so_far

        # Then our target statement reduces to
        # (1 - max_adversary_percentage/100) * remaining_ffg_voting_weight >= 2/3 * total_active_balance

        # Therefore
        # max_adversary_percentage <=
        # (1 - (2/3 * total_active_balance / remaining_ffg_voting_weight)) * 100 =
        # by bringing all to the denominator (3 * remaining_ffg_voting_weight), we get
        return (300 * remaining_ffg_voting_weight - 200 * total_active_balance) // (3 * remaining_ffg_voting_weight)
    else:
        # We know that  max_adversary_percentage <= ffg_weight_supporting_checkpoint_for_block_to_be_confirmed / ffg_voting_weight_so_far
        # Then our target statement reduces to

        # ffg_weight_supporting_checkpoint_for_block_to_be_confirmed
        # - ffg_voting_weight_so_far  * max_adversary_percentage / 100
        # + (1 - max_adversary_percentage/100) * remaining_ffg_voting_weight
        # >= 2/3 * total_active_balance

        # Therfore:
        # max_adversary_percentage <= ((ffg_weight_supporting_checkpoint_for_block_to_be_confirmed + remaining_ffg_voting_weight)/total_active_balance - 2/3) * 100
        # by bringing all to the denominator (3 * total_active_balance), we get
        return (300 * (ffg_weight_supporting_checkpoint_for_block_to_be_confirmed + remaining_ffg_voting_weight) - 200 * total_active_balance) // (3 * total_active_balance)
```

### Main Function

```python
def get_confirmation_score(
    store: Store,
    block_root: Root
) -> int:
    """
    Return -1 in the case that `block_root` cannot be confirmed even by assuming no adversary weight,
    otherwise it returns the maximum percentage of adversary weight that is admissible in order to
    consider `block_root` confirmed.
    """
    current_slot = get_current_slot(store)
    current_epoch = get_current_epoch_store(store)

    block = store.blocks[block_root]

    # We can only confirm blocks created in the current epoch
    assert compute_epoch_at_slot(block.slot) == current_epoch

    return min(
        get_score_for_LMD_confirmation(store, block_root, current_slot),
        get_score_for_FFG_confirmation(store, block_root, current_slot)
    )
```

## `get_safe_execution_payload_hash`

This function is used to compute the value of the `safeBlockHash` field which is passed from CL to EL in the `forkchoiceUpdated` engine api call.

### Helper

```python
def find_confirmed_block(
    store: Store,
    max_adversary_percentage: int,
    max_adversarial_slashing: int,
    block_root: Root
) -> Root:

    block = store.blocks[block_root]
    current_epoch = get_current_epoch_store(store)

    if compute_epoch_at_slot(block.slot) != current_epoch:
        return store.finalized_checkpoint.root

    if is_confirmed(store, max_adversary_percentage, max_adversarial_slashing, block_root):
        return block_root
    else:
        return find_confirmed_block(store, max_adversary_percentage, max_adversarial_slashing, block.parent_root)

```

### Main Function

```python
def get_safe_execution_payload_hash(
    store: Store,
    max_adversary_percentage: int,
    max_adversarial_slashing: int
) -> Hash32:
    head_root = get_head(store)

    confirmed_block_root = find_confirmed_block(store, max_adversary_percentage, max_adversarial_slashing, head_root)
    confirmed_block = store.blocks[confirmed_block_root]

    if compute_epoch_at_slot(confirmed_block.slot) >= BELLATRIX_FORK_EPOCH:
        return confirmed_block.body.execution_payload.block_hash
    else:
        return Hash32()
```

*Note*: This helper uses beacon block container extended in [Bellatrix](../specs/bellatrix/beacon-chain.md).

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
def get_ffg_support_using_latest_messages(store: Store, block_root: Root) -> Gwei:
    block = store.blocks[block_root]
    assert get_current_epoch_store(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_epoch_store(store)

    block_checkpoint_root = get_block_root(store.block_states[block_root], current_epoch)

    block_checkpoint_state = store.block_states[block_checkpoint_root]

    active_indices = get_active_validator_indices(block_checkpoint_state, current_epoch)

    return Gwei(sum(
        block_checkpoint_state.validators[i].effective_balance for i in active_indices
        if get_checkpoint_block(store, store.latest_messages[i].root, current_epoch) == block_checkpoint_root
    ))
```
