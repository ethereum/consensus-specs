# Fork Choice -- Confirmation Rule

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
  - [Usage](#usage)
- [Confirmation Rule](#confirmation-rule)
  - [Helper Functions](#helper-functions)
    - [`get_committee_weight_between_slots`](#get_committee_weight_between_slots)
    - [`is_one_confirmed`](#is_one_confirmed)
    - [`is_LMD_confirmed`](#is_lmd_confirmed)
    - [`get_remaining_weight_in_epoch`](#get_remaining_weight_in_epoch)
    - [`get_leaf_block_roots`](#get_leaf_block_roots)
    - [`get_FFG_support`](#get_FFG_support)
    - [`is_FFG_confirmed`](#is_FFG_confirmed)
  - [`is_confirmed`](#is_confirmed)
- [Safe Block Hash](#safe-block-hash)
  - [Helper Functions](#helper-functions-1)
    - [`find_confirmed_block`](#find_confirmed_block)
  - [`get_safe_execution_payload_hash`](#get_safe_execution_payload_hash)
- [Confirmation Score](#confirmation-score)
  - [Helper Functions](#helper-functions-2)
    - [`get_one_confirmation_score`](#get_one_confirmation_score)
    - [`get_LMD_confirmation_score`](#get_LMD_confirmation_score)
    - [`get_FFG_confirmation_score`](#get_FFG_confirmation_score)
  - [`get_confirmation_score`](#get_confirmation_score)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document specifies a fast block confirmation rule for the Ethereum protocol.
*Note:* Confirmation is not a substitute for finality! The safety of confirmations is weaker than that of finality.

The research paper for this rule is attached in this [ethresear.ch post](https://ethresear.ch/t/confirmation-rule-for-ethereum-pos/15454).

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

#### `get_committee_weight_between_slots`

```python
def get_committee_weight_between_slots(store: Store, start_slot: Slot, end_slot: Slot) -> Gwei:
    """Returns the total weight of committees between ``start_slot`` and ``end_slot`` (inclusive of both).
    Uses the justified state to compute committee weights.
    """
    justified_state = store.checkpoint_states[store.justified_checkpoint]
    total_active_balance = get_total_active_balance(justified_state)

    # If an entire epoch is covered by the range, return the total active balance
    start_epoch = compute_epoch_at_slot(start_slot)
    end_epoch = compute_epoch_at_slot(end_slot)
    if end_epoch > start_epoch + 1:
        return total_active_balance

    # A range that does not span any full epoch needs pro-rata calculation
    committee_weight = get_total_active_balance(justified_state) // SLOTS_PER_EPOCH
    num_committees = 0
    # First, calculate the weight from the end epoch
    epoch_boundary_slot = compute_start_slot_at_epoch(end_epoch)
    num_committees += end_slot - epoch_boundary_slot + 1
    # Next, calculate the weight from the previous epoch
    # Each committee from the previous epoch only contributes a pro-rated weight
    multiplier = (SLOTS_PER_EPOCH - end_slot % SLOTS_PER_EPOCH - 1) / SLOTS_PER_EPOCH
    num_committees += (epoch_boundary_slot - start_slot) * multiplier
    return num_committees * committee_weight
```

#### `is_one_confirmed`

```python
def is_one_confirmed(store: Store, confirmation_byzantine_threshold: int, block_root: Root) -> bool:
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    parent_block = store.blocks[block.parent_root]
    support = int(get_weight(store, block_root))
    maximum_support = int(get_committee_weight_between_slots(store, Slot(parent_block.slot + 1), current_slot))
    proposer_score = int(get_proposer_score(store))

    return support / maximum_support > \
        0.5 * (1 + proposer_score / maximum_support) + confirmation_byzantine_threshold / 100
```

#### `is_LMD_confirmed`

```python
def is_LMD_confirmed(store: Store, confirmation_byzantine_threshold: int, block_root: Root) -> bool:
    if block_root == store.finalized_checkpoint.root:
        return True
    else:
        block = store.blocks[block_root]
        finalized_block = store.blocks[store.finalized_checkpoint.root]
        if block.slot <= finalized_block.slot:
            # This block is not in the finalized chain.
            return False
        else:
            # Check is_one_confirmed for this block and is_LMD_confirmed for the preceding chain.
            return (
                is_one_confirmed(store, confirmation_byzantine_threshold, block_root) and
                is_LMD_confirmed(store, confirmation_byzantine_threshold, block.parent_root)
            )
```

#### `get_remaining_weight_in_epoch`

```python
def get_remaining_weight_in_epoch(store: Store, current_slot: Slot) -> Gwei:
    # Returns the total weight of votes for this epoch from future committees after the current slot
    first_slot_next_epoch = compute_start_slot_at_epoch(Epoch(compute_epoch_at_slot(current_slot) + 1))
    return get_committee_weight_between_slots(store, Slot(current_slot + 1), Slot(first_slot_next_epoch - 1))
```

#### `get_leaf_block_roots`

```python
def get_leaf_block_roots(store: Store, block_root: Root) -> Set[Root]:
    children = [
        root for root in store.blocks.keys()
        if store.blocks[root].parent_root == block_root
    ]

    if any(children):
        # Get leaves of all children and add to the set.
        leaves = set().union(*[get_leaf_block_roots(store, child) for child in children])
        return leaves
    else:
        # This block is a leaf.
        return set(block_root)

```

#### `get_FFG_support`

```python
def get_FFG_support(store: Store, block_root: Root) -> Gwei:
    # Returns the total weight supporting the highest checkpoint in the block's chain

    block = store.blocks[block_root]
    assert get_current_epoch(store) == compute_epoch_at_slot(block.slot)

    leave_roots = get_leaf_block_roots(store, block_root)
    # current_epoch_attestations contains only attestations with source matching block.current_justified_checkpoint
    attestations_in_leaves = set().union(
        *[store.block_states[root].current_epoch_attestations for root in leave_roots]
    )

    current_epoch = get_current_epoch(store)
    checkpoint_root = get_checkpoint_block(store, block_root, current_epoch)
    support_for_checkpoint = {a for a in attestations_in_leaves if a.data.target.root == checkpoint_root}
    checkpoint_state = store.block_states[checkpoint_root]
    return get_attesting_balance(checkpoint_state, list(support_for_checkpoint))
```

#### `is_FFG_confirmed`

```python
def is_FFG_confirmed(
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
    checkpoint_root = get_checkpoint_block(store, block_root, current_epoch)
    checkpoint_state = store.block_states[checkpoint_root]

    remaining_ffg_weight = int(get_remaining_weight_in_epoch(store, current_slot))
    total_active_balance = int(get_total_active_balance(checkpoint_state))
    current_weight_in_epoch = total_active_balance - remaining_ffg_weight
    assert current_weight_in_epoch >= 0

    ffg_support_for_checkpoint = int(get_FFG_support(store, block_root))
    max_adversarial_ffg_support_for_checkpoint = int(
        min(
            (current_weight_in_epoch * confirmation_byzantine_threshold - 1) // 100 + 1,
            confirmation_slashing_threshold,
            ffg_support_for_checkpoint
        )
    )

    return 2 / 3 * total_active_balance <= \
        ffg_support_for_checkpoint - max_adversarial_ffg_support_for_checkpoint + \
        (1 - confirmation_byzantine_threshold / 100) * remaining_ffg_weight
```

### `is_confirmed`

```python
def is_confirmed(
    store: Store,
    confirmation_byzantine_threshold: int,
    confirmation_slashing_threshold: int,
    block_root: Root
) -> bool:
    current_epoch = get_current_epoch(store)

    block = store.blocks[block_root]
    block_state = store.block_states[block_root]
    block_justified_checkpoint = block_state.current_justified_checkpoint.epoch

    # This function is only applicable to current epoch blocks
    assert compute_epoch_at_slot(block.slot) == current_epoch

    return (
        is_LMD_confirmed(store, confirmation_byzantine_threshold, block_root) and
        is_FFG_confirmed(store, confirmation_byzantine_threshold, confirmation_slashing_threshold, block_root) and
        block_justified_checkpoint + 1 == current_epoch
    )
```

## Safe Block Hash

This function is used to compute the value of the `safeBlockHash` field which is passed from CL to EL in the `forkchoiceUpdated` Engine API call.

### Helper Functions

#### `find_confirmed_block`

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
        return find_confirmed_block(store, confirmation_byzantine_threshold,
                                    confirmation_slashing_threshold, block.parent_root)

```

### `get_safe_execution_payload_hash`

```python
def get_safe_execution_payload_hash(
    store: Store,
    confirmation_byzantine_threshold: int,
    confirmation_slashing_threshold: int
) -> Hash32:
    head_root = get_head(store)

    confirmed_block_root = find_confirmed_block(store, confirmation_byzantine_threshold,
                                                confirmation_slashing_threshold, head_root)
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

#### `get_one_confirmation_score`

```python
def get_one_confirmation_score(store: Store, block_root: Root) -> int:
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    parent_block = store.blocks[block.parent_root]
    support = int(get_weight(store, block_root))
    maximum_support = int(get_committee_weight_between_slots(store, Slot(parent_block.slot + 1), current_slot))
    proposer_score = int(get_proposer_score(store))

    """
    Return the max possible one_confirmation_score such that:
    support / maximum_support > \
        0.5 * (1 + proposer_score / maximum_support) + one_confirmation_score / 100
    """
    return (100 * support - 50 * proposer_score - 1) // maximum_support - 50
```

#### `get_LMD_confirmation_score`

```python
def get_LMD_confirmation_score(store: Store, block_root: Root) -> int:
    if block_root == store.finalized_checkpoint.root:
        return 100 // 3
    else:
        block = store.blocks[block_root]
        finalized_block = store.blocks[store.finalized_checkpoint.root]
        if block.slot <= finalized_block.slot:
            # This block is not in the finalized chain.
            return -1
        else:
            # Check one_confirmed score for this block and LMD_confirmed score for the preceding chain.
            return min(
                get_one_confirmation_score(store, block_root),
                get_LMD_confirmation_score(store, block.parent_root)
            )
```

#### `get_FFG_confirmation_score`

```python
def get_FFG_confirmation_score(store: Store, block_root: Root) -> int:
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    assert get_current_epoch(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_epoch(store)
    checkpoint_root = get_checkpoint_block(store, block_root, current_epoch)
    checkpoint_state = store.block_states[checkpoint_root]

    total_active_balance = int(get_total_active_balance(checkpoint_state))

    remaining_ffg_weight = int(get_remaining_weight_in_epoch(store, current_slot))

    ffg_voting_weight_so_far = total_active_balance - remaining_ffg_weight
    assert ffg_voting_weight_so_far >= 0

    ffg_support_for_checkpoint = int(get_FFG_support(store, block_root))

    """
    Note: This function assumes confirmation_slashing_threshold = + infinity.

    Return the max possible ffg_confirmation_score such that:
    2 / 3 * total_active_balance <= \
        ffg_support_for_checkpoint - \
        min(ffg_support_for_checkpoint, ffg_voting_weight_so_far * ffg_confirmation_score / 100) + \
        (1 - ffg_confirmation_score / 100) * remaining_ffg_weight
    """

    """
    Case 1: ffg_support_for_checkpoint <= ffg_voting_weight_so_far * ffg_confirmation_score / 100

    2 / 3 * total_active_balance <= \
        (1 - ffg_confirmation_score / 100) * remaining_ffg_weight
    """
    if ffg_voting_weight_so_far > 0:
        ffg_confirmation_score = \
            100 * (3 * remaining_ffg_weight - 2 * total_active_balance) // (3 * remaining_ffg_weight)
        if ffg_confirmation_score / 100 >= ffg_support_for_checkpoint / ffg_voting_weight_so_far:
            return ffg_confirmation_score

    """
    Case 2: ffg_support_for_checkpoint > ffg_voting_weight_so_far * ffg_confirmation_score / 100

    2 / 3 * total_active_balance <= \
        ffg_support_for_checkpoint - \
        ffg_voting_weight_so_far * ffg_confirmation_score / 100 + \
        (1 - ffg_confirmation_score / 100) * remaining_ffg_weight
    """
    ffg_confirmation_score = \
        100 * (3 * (ffg_support_for_checkpoint + remaining_ffg_weight) - 2 * total_active_balance) // \
        (3 * total_active_balance)
    assert ffg_confirmation_score / 100 < ffg_support_for_checkpoint / ffg_voting_weight_so_far
    return ffg_confirmation_score
```

### `get_confirmation_score`

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
        get_LMD_confirmation_score(store, block_root),
        get_FFG_confirmation_score(store, block_root)
    )
```
