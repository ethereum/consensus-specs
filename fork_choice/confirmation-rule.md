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
    - [`is_lmd_confirmed`](#is_lmd_confirmed)
    - [`get_remaining_weight_in_epoch`](#get_remaining_weight_in_epoch)
    - [`get_leaf_block_roots`](#get_leaf_block_roots)
    - [`get_current_epoch_participating_indices`](#get_current_epoch_participating_indices)
    - [`get_ffg_support`](#get_ffg_support)
    - [`is_ffg_confirmed`](#is_ffg_confirmed)
  - [`is_confirmed`](#is_confirmed)
- [Safe Block Hash](#safe-block-hash)
  - [Helper Functions](#helper-functions-1)
    - [`find_confirmed_block`](#find_confirmed_block)
  - [`get_safe_execution_payload_hash`](#get_safe_execution_payload_hash)
- [Confirmation Score](#confirmation-score)
  - [Helper Functions](#helper-functions-2)
    - [`get_one_confirmation_score`](#get_one_confirmation_score)
    - [`get_lmd_confirmation_score`](#get_lmd_confirmation_score)
    - [`get_ffg_confirmation_score`](#get_ffg_confirmation_score)
  - [`get_confirmation_score`](#get_confirmation_score)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document specifies a fast block confirmation rule for the Ethereum protocol.
*Note:* Confirmation is not a substitute for finality! The safety of confirmations is weaker than that of finality.

The research paper for this rule is attached in this [ethresear.ch post](https://ethresear.ch/t/confirmation-rule-for-ethereum-pos/15454).

This rule makes the following network synchrony assumption: starting from the current slot, attestations created by honest validators in any slot are received by the end of that slot.
Consequently, this rule provides confirmations to users who believe in the above assumption. If this assumption is broken, confirmed blocks can be reorged without any adversarial behavior, and without slashing.

There are two algorithms in the document:
- [**Confirmation Rule**](#confirmation-rule): Given a block and confirmation safety parameters, outputs whether the block is confirmed.
- [**Confirmation Score**](#confirmation-score): Given a block, outputs the confirmation score for the block, i.e., the maximum possible confirmation safety parameters to deem the block confirmed.

*Note:* These algorithms use floating point arithmetic in some places. The rest of `consensus-specs` uses `uint64` arithmetic exclusively to ensure that Ethereum clients arrive at the exact same results - a property crucial for consensus objects (such as the `BeaconState`). This document describes a local confirmation rule that is not used to derive any consensus objects. Using floating point arithmetic here allows for a more readable specification, and client-native floating point arithmetic provides sufficient precision for its objective.

## Confirmation Rule

This section specifies an algorithm to determine whether a block is confirmed. The confirmation rule can be configured to the desired tolerance of Byzantine validators, for which the algorithm takes the following input parameters:
| Input Parameter                    | Type     | Max. Value                         | Description                                                            |
| ---------------------------------- | -------- |:---------------------------------- | ---------------------------------------------------------------------- |
| `confirmation_byzantine_threshold` | `uint64` | `33`                               | the maximum percentage of Byzantine validators among the validator set |
| `confirmation_slashing_threshold`  | `uint64` | `confirmation_byzantine_threshold` | the maximum percentage of slashings among the validator set            |


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

    if start_slot > end_slot:
        return 0

    if end_epoch > start_epoch + 1:
        return total_active_balance

    committee_weight = total_active_balance // SLOTS_PER_EPOCH
    
    if start_epoch == end_epoch:
        num_committees = end_slot - start_slot + 1
    else:
        # A range that spans an epoch boundary, but does not span any full epoch
        # needs pro-rata calculation
        # First, calculate the number of committees in the current epoch
        num_slots_in_current_epoch = (end_slot % SLOTS_PER_EPOCH) + 1
        # Next, calculate the number of slots remaining in the current epoch
        remaining_slots_in_current_epoch = SLOTS_PER_EPOCH - num_slots_in_current_epoch
        # Then, calculate the number of slots in the previous epoch
        num_slots_in_previous_epoch = SLOTS_PER_EPOCH - (start_slot % SLOTS_PER_EPOCH)

        # Each committee from the previous epoch only contributes a pro-rated weight
        multiplier = remaining_slots_in_current_epoch / SLOTS_PER_EPOCH
        num_committees = num_slots_in_current_epoch + num_slots_in_previous_epoch * multiplier
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

    return (
        support / maximum_support >
        0.5 * (1 + proposer_score / maximum_support) + confirmation_byzantine_threshold / 100
    )
```

#### `is_lmd_confirmed`

```python
def is_lmd_confirmed(store: Store, confirmation_byzantine_threshold: int, block_root: Root) -> bool:
    if block_root == store.finalized_checkpoint.root:
        return True
    else:
        block = store.blocks[block_root]
        finalized_block = store.blocks[store.finalized_checkpoint.root]
        if block.slot <= finalized_block.slot:
            # This block is not in the finalized chain.
            return False
        else:
            # Check is_one_confirmed for this block and is_lmd_confirmed for the preceding chain.
            return (
                is_one_confirmed(store, confirmation_byzantine_threshold, block_root) and
                is_lmd_confirmed(store, confirmation_byzantine_threshold, block.parent_root)
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
        return set([block_root])

```

#### `get_current_epoch_participating_indices`

```python
def get_current_epoch_participating_indices(state: BeaconState, active_validator_indices: Sequence[ValidatorIndex]) -> Set[ValidatorIndex]:    
    return set([i for i in active_validator_indices if has_flag(state.current_epoch_participation[i], TIMELY_TARGET_FLAG_INDEX)])
```

#### `get_ffg_support`

```python
def get_ffg_support(store: Store, block_root: Root) -> Gwei:
    """
    Returns the total weight supporting the highest checkpoint in the block's chain
    """

    block = store.blocks[block_root]
    assert get_current_store_epoch(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_store_epoch(store)
    checkpoint_root = get_checkpoint_block(store, block_root, current_epoch)
    checkpoint_state = store.block_states[checkpoint_root]

    leave_roots = get_leaf_block_roots(store, block_root)

    # keep only leaves with checkpoint consistent with checkpoint_root   
    leave_roots = {root for root in leave_roots if get_checkpoint_block(store, root, current_epoch) == checkpoint_root}

    active_validator_indices = get_active_validator_indices(checkpoint_state, current_epoch)

    participating_indices = set().union(
        *[get_current_epoch_participating_indices(store.block_states[root], active_validator_indices) for root in leave_roots]
    )

    return get_total_balance(checkpoint_state, participating_indices)
```

#### `is_ffg_confirmed`

```python
def is_ffg_confirmed(
    store: Store,
    confirmation_byzantine_threshold: int,
    confirmation_slashing_threshold: int,
    block_root: Root,
) -> bool:
    """
    Returns whether the branch will justify it's current epoch checkpoint at the end of this epoch
    """
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    assert get_current_store_epoch(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_store_epoch(store)
    checkpoint_root = get_checkpoint_block(store, block_root, current_epoch)
    checkpoint_state = store.block_states[checkpoint_root]

    remaining_ffg_weight = int(get_remaining_weight_in_epoch(store, current_slot))
    total_active_balance = int(get_total_active_balance(checkpoint_state))
    current_weight_in_epoch = total_active_balance - remaining_ffg_weight
    assert current_weight_in_epoch >= 0

    ffg_support_for_checkpoint = int(get_ffg_support(store, block_root))
    max_adversarial_ffg_support_for_checkpoint = int(
        min(
            (current_weight_in_epoch * confirmation_byzantine_threshold - 1) // 100 + 1,
            confirmation_slashing_threshold,
            ffg_support_for_checkpoint
        )
    )

    return (
        2 / 3 * total_active_balance <= (
            ffg_support_for_checkpoint - max_adversarial_ffg_support_for_checkpoint +
            (1 - confirmation_byzantine_threshold / 100) * remaining_ffg_weight
        )
    )
```

### `is_confirmed`

```python
def is_confirmed(
    store: Store,
    confirmation_byzantine_threshold: int,
    confirmation_slashing_threshold: int,
    block_root: Root
) -> bool:
    current_epoch = get_current_store_epoch(store)

    block = store.blocks[block_root]
    block_state = store.block_states[block_root]
    block_justified_checkpoint = block_state.current_justified_checkpoint.epoch

    # This function is only applicable to current epoch blocks
    assert compute_epoch_at_slot(block.slot) == current_epoch

    return (
        block_justified_checkpoint + 1 == current_epoch
        and is_lmd_confirmed(store, confirmation_byzantine_threshold, block_root)
        and is_ffg_confirmed(store, confirmation_byzantine_threshold, confirmation_slashing_threshold, block_root)
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
    current_epoch = get_current_store_epoch(store)

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
def get_one_confirmation_score(store: Store, block_root: Root) -> float:
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
    return max(100 * (support - 0.5 * proposer_score - 1) / maximum_support - 50, -1)
```

#### `get_lmd_confirmation_score`

```python
def get_lmd_confirmation_score(store: Store, block_root: Root) -> float:
    if block_root == store.finalized_checkpoint.root:
        return 100 / 3
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
                get_lmd_confirmation_score(store, block.parent_root)
            )
```

#### `get_ffg_confirmation_score`

```python
def get_ffg_confirmation_score(store: Store, block_root: Root) -> float:
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    assert get_current_store_epoch(store) == compute_epoch_at_slot(block.slot)

    current_epoch = get_current_store_epoch(store)
    checkpoint_root = get_checkpoint_block(store, block_root, current_epoch)
    checkpoint_state = store.block_states[checkpoint_root]

    total_active_balance = int(get_total_active_balance(checkpoint_state))

    remaining_ffg_weight = int(get_remaining_weight_in_epoch(store, current_slot))

    ffg_voting_weight_so_far = total_active_balance - remaining_ffg_weight
    assert ffg_voting_weight_so_far >= 0

    ffg_support_for_checkpoint = int(get_ffg_support(store, block_root))

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
        ffg_confirmation_score = (
            100 * (3 * remaining_ffg_weight - 2 * total_active_balance) / (3 * remaining_ffg_weight)
        )
        if ffg_confirmation_score / 100 >= ffg_support_for_checkpoint / ffg_voting_weight_so_far:
            return ffg_confirmation_score

    """
    Case 2: ffg_support_for_checkpoint > ffg_voting_weight_so_far * ffg_confirmation_score / 100

    2 / 3 * total_active_balance <= \
        ffg_support_for_checkpoint - \
        ffg_voting_weight_so_far * ffg_confirmation_score / 100 + \
        (1 - ffg_confirmation_score / 100) * remaining_ffg_weight
    """
    ffg_confirmation_score = (
        100 * (3 * (ffg_support_for_checkpoint + remaining_ffg_weight) - 2 * total_active_balance) /
        (3 * total_active_balance)
    )
    assert ffg_confirmation_score / 100 < ffg_support_for_checkpoint / ffg_voting_weight_so_far
    return max(ffg_confirmation_score, -1)
```

### `get_confirmation_score`

```python
def get_confirmation_score(
    store: Store,
    block_root: Root
) -> float:
    """
    Return -1 in the case that `block_root` cannot be confirmed even by assuming no adversary weight,
    otherwise it returns the maximum percentage of adversary weight that is admissible in order to
    consider `block_root` confirmed.
    """
    current_epoch = get_current_store_epoch(store)

    block = store.blocks[block_root]

    # We can only confirm blocks created in the current epoch
    assert compute_epoch_at_slot(block.slot) == current_epoch

    return min(
        get_lmd_confirmation_score(store, block_root),
        get_ffg_confirmation_score(store, block_root)
    )
```
