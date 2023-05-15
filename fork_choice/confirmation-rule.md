# Fork Choice -- Confirmation Rule

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Confirmation Rule](#confirmation-rule)
  - [Helper Functions](#helper-functions)
  - [Main Function](#main-function)
- [`get_safe_execution_payload_hash`](#get_safe_execution_payload_hash)
  - [Helper](#helper)
  - [Main Function](#main-function-1)
- [Confirmation Score](#confirmation-score)
  - [Helper Functions](#helper-functions-1)
  - [Main Function](#main-function-2)
- [Old functions kept for reference](#old-functions-kept-for-reference)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document specifies a fast block confirmation rule for the Ethereum protocol.
*Note:* Confirmation is not a substitute for finality! The safety of confirmations is weaker than that of finality.

### Usage

This rule makes the following network synchrony assumption: starting from the current slot, attestations created by honest validators in any slot are received by the end of that slot.
This rule provides confirmations to users who believe in the above assumption. If this assumption is broken, confirmed blocks can be reorged without any adversarial behavior, and without slashing.

## Confirmation Rule

This section specifies an algorithm to determine whether a block is confirmed. The confirmation rule can be configured to the desired tolerance of Byzantine validators, for which the algorithm takes the following input parameters:
| Input Parameter                    | Type  | Max. Value                         | Description                                                            |
| ---------------------------------- | ----- |:---------------------------------- | ---------------------------------------------------------------------- |
| `confirmation_byzantine_threshold` | `int` | `33`                               | the maximum percentage of Byzantine validators among the validator set |
| `confirmation_slashing_threshold`  | `int` | `confirmation_byzantine_threshold` | the maximum percentage of slashings among the validator set            |


### Helper Functions


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
def is_one_confirmed(store: Store, confirmation_byzantine_threshold: int, block_root: Root) -> bool:
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    justified_checkpoint_state = store.checkpoint_states[store.justified_checkpoint]
    parent_block = store.blocks[block.parent_root]
    support = int(get_weight(store, block_root))
    maximum_support = int(get_committee_weight_between_slots(justified_checkpoint_state, Slot(parent_block.slot + 1), current_slot))

    committee_weight = get_total_active_balance(justified_checkpoint_state) // SLOTS_PER_EPOCH
    proposer_score = int((committee_weight * PROPOSER_SCORE_BOOST) // 100)

    # support / maximum_support > 1/2 * (1 + proposer_score / maximum_support) + confirmation_byzantine_threshold/100 =>
    return 100 * support > 50 * maximum_support + 50 * proposer_score + confirmation_byzantine_threshold * maximum_support
```

```python
def is_LMD_confirmed(store: Store, confirmation_byzantine_threshold: int, block_root: Root) -> bool:
    current_slot = get_current_slot(store)
    if block_root == store.finalized_checkpoint.root:
        return True
    else:
        block = store.blocks[block_root]
        finalized_block = store.blocks[store.finalized_checkpoint.root]
        if block.slot <= finalized_block.slot:
            return False
        else:
            return (
                is_one_confirmed(store, confirmation_byzantine_threshold, block_root) and
                is_LMD_confirmed(store, confirmation_byzantine_threshold, block.parent_root)
            )
```

```python
def get_future_vote_weight_in_epoch(state: BeaconState, current_slot: Slot) -> Gwei:
    # Returns the total weight of votes for this epoch from future committees after the current slot
    first_slot_next_epoch = compute_start_slot_at_epoch(Epoch(compute_epoch_at_slot(current_slot) + 1))
    return get_committee_weight_between_slots(state, Slot(current_slot + 1), Slot(first_slot_next_epoch - 1))
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
    assert get_current_epoch(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_epoch(store)

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
    confirmation_byzantine_threshold: int,
    confirmation_slashing_threshold: int,
    block_root: Root,
) -> bool:
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    assert get_current_epoch(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_epoch(store)

    # The following could be replaced by get_checkpoint_block once merged in
    block_checkpoint_root = get_block_root(store.block_states[block_root], current_epoch)
    block_checkpoint_state = store.block_states[block_checkpoint_root]

    total_active_balance = int(get_total_active_balance(block_checkpoint_state))

    remaining_ffg_voting_weight = int(get_future_vote_weight_in_epoch(block_checkpoint_state, current_slot))

    current_vote_weight_in_epoch = total_active_balance - remaining_ffg_voting_weight
    assert current_vote_weight_in_epoch >= 0

    ffg_weight_supporting_checkpoint_for_block_to_be_confirmed = int(get_ffg_support(store, block_root))

    max_ffg_weight_the_adversary_can_subtract_from_ffg_support = int(
        min(
            (current_vote_weight_in_epoch * confirmation_byzantine_threshold - 1) // 100 + 1,
            confirmation_slashing_threshold,
            ffg_weight_supporting_checkpoint_for_block_to_be_confirmed
        )
    )

    # ffg_weight_supporting_checkpoint_for_block_to_be_confirmed - max_ffg_weight_the_adversary_can_subtract_from_ffg_support + (1 - confirmation_byzantine_threshold/100) * remaining_ffg_voting_weight >= 2/3 * total_active_balance =>
    return ffg_weight_supporting_checkpoint_for_block_to_be_confirmed * 300 + (300 - 3 * confirmation_byzantine_threshold) * remaining_ffg_voting_weight - max_ffg_weight_the_adversary_can_subtract_from_ffg_support * 300 >= 200 * total_active_balance
```

### Main Function

```python
def is_confirmed(
    store: Store,
    confirmation_byzantine_threshold: int,
    confirmation_slashing_threshold: int,
    block_root: Root
) -> bool:
    current_slot = get_current_slot(store)
    current_epoch = get_current_epoch(store)

    block = store.blocks[block_root]
    block_state = store.block_states[block_root]

    # We can only apply isConfirmed to blocks created in the current epoch
    assert compute_epoch_at_slot(block.slot) == current_epoch

    return (
        is_LMD_confirmed(store, confirmation_byzantine_threshold, block_root) and
        is_ffg_confirmed(store, confirmation_byzantine_threshold, confirmation_slashing_threshold, block_root) and
        block_state.current_justified_checkpoint.epoch + 1 == current_epoch
    )
```


## `get_safe_execution_payload_hash`

This function is used to compute the value of the `safeBlockHash` field which is passed from CL to EL in the `forkchoiceUpdated` engine api call.

### Helper

```python
def find_confirmed_block(
    store: Store,
    confirmation_byzantine_threshold: int,
    confirmation_slashing_threshold: int,
    block_root: Root
) -> Root:

    block = store.blocks[block_root]
    current_epoch = get_current_epoch(store)

    if compute_epoch_at_slot(block.slot) != current_epoch:
        return store.finalized_checkpoint.root

    if is_confirmed(store, confirmation_byzantine_threshold, confirmation_slashing_threshold, block_root):
        return block_root
    else:
        return find_confirmed_block(store, confirmation_byzantine_threshold, confirmation_slashing_threshold, block.parent_root)

```

### Main Function

```python
def get_safe_execution_payload_hash(
    store: Store,
    confirmation_byzantine_threshold: int,
    confirmation_slashing_threshold: int
) -> Hash32:
    head_root = get_head(store)

    confirmed_block_root = find_confirmed_block(store, confirmation_byzantine_threshold, confirmation_slashing_threshold, head_root)
    confirmed_block = store.blocks[confirmed_block_root]

    if compute_epoch_at_slot(confirmed_block.slot) >= BELLATRIX_FORK_EPOCH:
        return confirmed_block.body.execution_payload.block_hash
    else:
        return Hash32()
```

*Note*: This helper uses beacon block container extended in [Bellatrix](../specs/bellatrix/beacon-chain.md).

## Confirmation Score

The confirmation score for a block is the maximum adversarial percentage weight that a confirmed block can tolerate.
This section specifies the algorithm to calculate the confirmation score of a given block.
This under the assumption that the adversary is willing to get as much stake as possible slashed to
prevent a block from being confirmed.

### Helper Functions


##### `get_committee_weight`

```python
def get_committee_weight(store: Store, start_slot: Slot, end_slot: Slot) -> Gwei:
    """Returns the total weight of committees between ``start_slot`` and ``end_slot`` (inclusive of both).
    Uses the justified state to compute committee weights.
    """

    justified_state = store.checkpoint_states[store.justified_checkpoint]
    total_active_balance = get_total_active_balance(state)

    # If an entire epoch is covered by the range, return the total active balance
    start_epoch = compute_epoch_at_slot(start_slot)
    end_epoch = compute_epoch_at_slot(end_slot)
    if end_epoch > start_epoch + 1:
        return total_active_balance

    # A range that does not span any full epoch needs pro-rata calculation
    committee_weight = get_total_active_balance(state) // SLOTS_PER_EPOCH
    num_committees = 0
    # First, calculate the weight from the end epoch
    epoch_boundary_slot = compute_start_slot_at_epoch(end_epoch)
    num_committees += end_slot - epoch_boundary_slot + 1
    # Next, calculate the weight from the previous epoch
    # Each committee from the previous epoch only contributes a pro-rated weight
    # NOTE: using float arithmetic here. is that allowed here in spec? probably yes, since this is not consensus code.
    multiplier = (SLOTS_PER_EPOCH - end_slot - 1) / SLOTS_PER_EPOCH
    num_committees += (epoch_boundary_slot - start_slot) * multiplier
    return num_committees * committee_weight
```


```python
def get_score_for_one_confirmation(store: Store, block_root: Root) -> int:
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    parent_block = store.blocks[block.parent_root]
    support = int(get_weight(store, block_root))
    maximum_support = int(get_committee_weight(parent_block.slot + 1, current_slot))
    proposer_score = int((committee_weight * PROPOSER_SCORE_BOOST) // 100)

    # We need to return a value confirmation_byzantine_threshold such that the following inequality is true
    # 100 * support > 50 * maximum_support + 50 * proposer_score + confirmation_byzantine_threshold * maximum_support
    # the "-1" in the numerator is to return a "<=" rather than a "<" value
    return (100 * support - 50 * proposer_score - 1) // maximum_support - 50
```

```python
def get_score_for_LMD_confirmation(store: Store, block_root: Root) -> int:
    current_slot = get_current_slot(store)
    if block_root == store.finalized_checkpoint.root:
        return 100 // 3
    else:
        block = store.blocks[block_root]
        finalized_block = store.blocks[store.finalized_checkpoint.root]
        if block.slot <= finalized_block.slot:
            return -1
        else:
            return min(
                get_score_for_one_confirmation(store, block_root),
                get_score_for_LMD_confirmation(store, block.parent_root)
            )
```

```python
def get_score_for_FFG_confirmation(store: Store, block_root: Root) -> int:
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    assert get_current_epoch(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_epoch(store)

    # The following could be replaced by get_checkpoint_block once merged in
    block_checkpoint_root = get_block_root(store.block_states[block_root], current_epoch)
    block_checkpoint_state = store.block_states[block_checkpoint_root]

    total_active_balance = int(get_total_active_balance(block_checkpoint_state))

    remaining_ffg_voting_weight = int(get_future_vote_weight_in_epoch(block_checkpoint_state, current_slot))

    ffg_voting_weight_so_far = total_active_balance - remaining_ffg_voting_weight
    assert ffg_voting_weight_so_far >= 0

    ffg_weight_supporting_checkpoint_for_block_to_be_confirmed = int(get_ffg_support(store, block_root))

    # We assume confirmation_slashing_threshold = + infinity
    # So, we want to return a value confirmation_byzantine_threshold such that the following statement is true

    # ffg_weight_supporting_checkpoint_for_block_to_be_confirmed
    # - min(ffg_weight_supporting_checkpoint_for_block_to_be_confirmed, ffg_voting_weight_so_far  * confirmation_byzantine_threshold / 100)
    # + (1 - confirmation_byzantine_threshold/100) * remaining_ffg_voting_weight
    # >= 2/3 * total_active_balance

    # First, we check whether confirmation_byzantine_threshold >= ffg_weight_supporting_checkpoint_for_block_to_be_confirmed / ffg_voting_weight_so_far * 100
    # To do this we check whether in the case that confirmation_byzantine_threshold == ffg_weight_supporting_checkpoint_for_block_to_be_confirmed / ffg_voting_weight_so_far * 100
    # our target statement is true
    # This amount to checking that
    # (1 - ffg_weight_supporting_checkpoint_for_block_to_be_confirmed / ffg_voting_weight_so_far) * remaining_ffg_voting_weight >= 2/3 * total_active_balance
    # multiplying each side by 3 * ffg_voting_weight_so_far, we get (assuming ffg_voting_weight_so_far != 0):

    if ffg_voting_weight_so_far > 0 and 3 * (ffg_voting_weight_so_far - ffg_weight_supporting_checkpoint_for_block_to_be_confirmed) * remaining_ffg_voting_weight >= 2 * total_active_balance * ffg_voting_weight_so_far:
        # We know that confirmation_byzantine_threshold >= ffg_weight_supporting_checkpoint_for_block_to_be_confirmed / ffg_voting_weight_so_far

        # Then our target statement reduces to
        # (1 - confirmation_byzantine_threshold/100) * remaining_ffg_voting_weight >= 2/3 * total_active_balance

        # Therefore
        # confirmation_byzantine_threshold <=
        # (1 - (2/3 * total_active_balance / remaining_ffg_voting_weight)) * 100 =
        # by bringing all to the denominator (3 * remaining_ffg_voting_weight), we get
        return (300 * remaining_ffg_voting_weight - 200 * total_active_balance) // (3 * remaining_ffg_voting_weight)
    else:
        # We know that  confirmation_byzantine_threshold <= ffg_weight_supporting_checkpoint_for_block_to_be_confirmed / ffg_voting_weight_so_far
        # Then our target statement reduces to

        # ffg_weight_supporting_checkpoint_for_block_to_be_confirmed
        # - ffg_voting_weight_so_far  * confirmation_byzantine_threshold / 100
        # + (1 - confirmation_byzantine_threshold/100) * remaining_ffg_voting_weight
        # >= 2/3 * total_active_balance

        # Therfore:
        # confirmation_byzantine_threshold <= ((ffg_weight_supporting_checkpoint_for_block_to_be_confirmed + remaining_ffg_voting_weight)/total_active_balance - 2/3) * 100
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
    current_epoch = get_current_epoch(store)

    block = store.blocks[block_root]

    # We can only confirm blocks created in the current epoch
    assert compute_epoch_at_slot(block.slot) == current_epoch

    return min(
        get_score_for_LMD_confirmation(store, block_root),
        get_score_for_FFG_confirmation(store, block_root)
    )
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
def get_ffg_support_using_latest_messages(store: Store, block_root: Root) -> Gwei:
    block = store.blocks[block_root]
    assert get_current_epoch(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_epoch(store)

    block_checkpoint_root = get_block_root(store.block_states[block_root], current_epoch)

    block_checkpoint_state = store.block_states[block_checkpoint_root]

    active_indices = get_active_validator_indices(block_checkpoint_state, current_epoch)

    return Gwei(sum(
        block_checkpoint_state.validators[i].effective_balance for i in active_indices
        if get_checkpoint_block(store, store.latest_messages[i].root, current_epoch) == block_checkpoint_root
    ))
```

```python
def get_current_vote_weight_in_epoch(state: BeaconState, current_slot: Slot) -> Gwei:
    # Returns the total weight of votes for this epoch from committees up til the current slot
    first_slot_current_epoch = compute_start_slot_at_epoch(compute_epoch_at_slot(current_slot))
    return get_committee_weight_between_slots(state, first_slot_current_epoch, current_slot)
```
