# Fork Choice -- Confirmation Rule

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Confirmation Rule](#confirmation-rule)
  - [Constants](#constants)
  - [Configuration](#configuration)
  - [Helper Functions](#helper-functions)
    - [`is_full_validator_set_covered`](#is_full_validator_set_covered)
    - [`is_full_validator_set_for_block_covered`](#is_full_validator_set_for_block_covered)
    - [`ceil_div`](#ceil_div)
    - [`adjust_committee_weight_estimate_to_ensure_safety`](#adjust_committee_weight_estimate_to_ensure_safety)
    - [`get_committee_weight_between_slots`](#get_committee_weight_between_slots)
    - [`is_one_confirmed`](#is_one_confirmed)
    - [`is_lmd_confirmed`](#is_lmd_confirmed)
    - [`get_total_active_balance_for_block_root`](#get_total_active_balance_for_block_root)
    - [`get_remaining_weight_in_current_epoch`](#get_remaining_weight_in_current_epoch)
    - [`get_leaf_block_roots`](#get_leaf_block_roots)
    - [`get_current_epoch_participating_indices`](#get_current_epoch_participating_indices)
    - [`get_ffg_support`](#get_ffg_support)
    - [`is_ffg_confirmed`](#is_ffg_confirmed)
  - [`is_confirmed_no_caching`](#is_confirmed_no_caching)
  - [`is_confirmed`](#is_confirmed)
    - [`find_confirmed_block`](#find_confirmed_block)
    - [`immediately_after_on_tick_if_slot_changed`](#immediately_after_on_tick_if_slot_changed)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document specifies a fast block confirmation rule for the Ethereum protocol.

*Note*: Confirmation is not a substitute for finality! The safety of confirmations is weaker than that of finality.

The research paper for this rule can be found [here](https://arxiv.org/abs/2405.00549).

This rule makes the following network synchrony assumption: starting from the current slot, attestations created by honest validators in any slot are received by the end of that slot.
Consequently, this rule provides confirmations to users who believe in the above assumption. If this assumption is broken, confirmed blocks can be reorged without any adversarial behavior and without slashing.


*Note*: This algorithm uses unbounded integer arithmetic in some places. The rest of `consensus-specs` uses `uint64` arithmetic exclusively to ensure that results fit into length-limited fields - a property crucial for consensus objects (such as the `BeaconBlockBody`). This document describes a local confirmation rule that does not require storing anything in length-limited fields. Using unbounded integer arithmetic here prevents possible overflowing issues for the spec tests generated using this Python specification (or when executing these specifications directly).

## Confirmation Rule

This section specifies an algorithm to determine whether a block is confirmed.

### Constants

The following values are (non-configurable) constants used throughout this specification.

| Name                                            | Value     | Description                                                                                                                                                                                                                                                                                                          |
|-------------------------------------------------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `UNCONFIRMED_SCORE`                             | `int(-1)` | Value returned by the `get_*_score` methods to indicate that the block passed in input cannot be confirmed even if all validators are honest.                                                                                                                                                                        |
| `MAX_CONFIRMATION_SCORE`                        | `int(33)` | Maximum possible value of the confirmation score corresponding to the maximum percentage of Byzantine stake.                                                                                                                                                                                                         |
| `COMMITTEE_WEIGHT_ESTIMATION_ADJUSTMENT_FACTOR` | `int(5)`  | Per mille value to add to the estimation of the committee weight across a range of slots not covering a full epoch in order to ensure the safety of the confirmation rule with high probability. See [here](https://gist.github.com/saltiniroberto/9ee53d29c33878d79417abb2b4468c20) for an explanation about the value chosen. |

### Configuration

The confirmation rule can be configured to the desired tolerance of Byzantine validators, for which the algorithm takes the following input parameters:

| Input Parameter                    | Type     | Max. Value               | Description                                                                                             |
|------------------------------------|----------|:-------------------------|---------------------------------------------------------------------------------------------------------|
| `CONFIRMATION_BYZANTINE_THRESHOLD` | `uint64` | `MAX_CONFIRMATION_SCORE` | assumed maximum percentage of Byzantine validators among the validator set.                             |
| `CONFIRMATION_SLASHING_THRESHOLD`  | `Gwei`   | `2**64 - 1`              | assumed maximum amount of stake that the adversary is willing to get slashed in order to reorg a block. |


### Helper Functions

#### `is_full_validator_set_covered`

```python
def is_full_validator_set_covered(start_slot: Slot, end_slot: Slot) -> bool:
    """
    Returns whether the range from ``start_slot`` to ``end_slot`` (inclusive of both) includes an entire epoch
    """
    start_epoch = compute_epoch_at_slot(start_slot)
    end_epoch = compute_epoch_at_slot(end_slot)

    return (
        end_epoch > start_epoch + 1
        or (end_epoch == start_epoch + 1 and start_slot % SLOTS_PER_EPOCH == 0))
```

#### `is_full_validator_set_for_block_covered`

```python
def is_full_validator_set_for_block_covered(store: Store, block_root: Root) -> bool:
    """
    Returns whether the range from ``start_slot`` to ``end_slot`` (inclusive of both) includes and entire epoch
    """
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    parent_block = store.blocks[block.parent_root]

    return is_full_validator_set_covered(Slot(parent_block.slot + 1), current_slot)
```

#### `ceil_div`

```python
def ceil_div(numerator: int, denominator: int) -> int:
    """
    Returns ``ceil(numerator / denominator)`` using only integer arithmetic
    """
    if numerator % denominator == 0:
        return numerator // denominator
    else:
        return (numerator // denominator) + 1
```

#### `adjust_committee_weight_estimate_to_ensure_safety`

```python
def adjust_committee_weight_estimate_to_ensure_safety(estimate: Gwei) -> Gwei:
    """
    Adjusts the ``estimate`` of the weight of a committee for a sequence of slots not covering a full epoch to
    ensure the safety of the confirmation rule with high probability.

    See https://gist.github.com/saltiniroberto/9ee53d29c33878d79417abb2b4468c20 for an explanation of why this is
    required.
    """
    return Gwei(ceil_div(int(estimate * (1000 + COMMITTEE_WEIGHT_ESTIMATION_ADJUSTMENT_FACTOR)), 1000))
```

#### `get_committee_weight_between_slots`

```python
def get_committee_weight_between_slots(state: BeaconState, start_slot: Slot, end_slot: Slot) -> Gwei:
    """
    Returns the total weight of committees between ``start_slot`` and ``end_slot`` (inclusive of both).
    """
    total_active_balance = get_total_active_balance(state)

    start_epoch = compute_epoch_at_slot(start_slot)
    end_epoch = compute_epoch_at_slot(end_slot)

    if start_slot > end_slot:
        return Gwei(0)

    # If an entire epoch is covered by the range, return the total active balance
    if is_full_validator_set_covered(start_slot, end_slot):
        return total_active_balance

    if start_epoch == end_epoch:
        return Gwei(ceil_div((end_slot - start_slot + 1) * int(total_active_balance), SLOTS_PER_EPOCH))
    else:
        # A range that spans an epoch boundary, but does not span any full epoch
        # needs pro-rata calculation

        # See https://gist.github.com/saltiniroberto/9ee53d29c33878d79417abb2b4468c20
        # for an explanation of the formula used below.

        # First, calculate the number of committees in the end epoch
        num_slots_in_end_epoch = int(compute_slots_since_epoch_start(end_slot) + 1)
        # Next, calculate the number of slots remaining in the end epoch
        remaining_slots_in_end_epoch = int(SLOTS_PER_EPOCH - num_slots_in_end_epoch)
        # Then, calculate the number of slots in the start epoch
        num_slots_in_start_epoch = int(SLOTS_PER_EPOCH - compute_slots_since_epoch_start(start_slot))

        end_epoch_weight_mul_by_slots_per_epoch = num_slots_in_end_epoch * int(total_active_balance)
        start_epoch_weight_mul_by_slots_per_epoch = ceil_div(
            num_slots_in_start_epoch * remaining_slots_in_end_epoch * int(total_active_balance),
            SLOTS_PER_EPOCH
        )

        # Each committee from the end epoch only contributes a pro-rated weight
        return adjust_committee_weight_estimate_to_ensure_safety(
            Gwei(ceil_div(
                start_epoch_weight_mul_by_slots_per_epoch + end_epoch_weight_mul_by_slots_per_epoch,
                SLOTS_PER_EPOCH
            ))
        )
```

#### `is_one_confirmed`

```python
def is_one_confirmed(store: Store, block_root: Root) -> bool:
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    parent_block = store.blocks[block.parent_root]
    support = int(get_weight(store, block_root))
    justified_state = store.checkpoint_states[store.justified_checkpoint]
    maximum_support = int(
        get_committee_weight_between_slots(justified_state, Slot(parent_block.slot + 1), Slot(current_slot - 1))
    )
    proposer_score = int(get_proposer_score(store))

    # Returns whether the following condition is true using only integer arithmetic
    # support / maximum_support >
    # 0.5 * (1 + proposer_score / maximum_support) + CONFIRMATION_BYZANTINE_THRESHOLD / 100

    return (
        100 * support >
        50 * maximum_support + 50 * proposer_score + CONFIRMATION_BYZANTINE_THRESHOLD * maximum_support
    )
```

#### `is_lmd_confirmed`

```python
def is_lmd_confirmed(store: Store, block_root: Root) -> bool:
    if block_root == store.finalized_checkpoint.root:
        return True

    if is_full_validator_set_for_block_covered(store, block_root):
        return is_one_confirmed(store, block_root)
    else:
        block = store.blocks[block_root]
        return (
            is_one_confirmed(store, block_root)
            and is_lmd_confirmed(store, block.parent_root)
        )
```

#### `get_total_active_balance_for_block_root`

```python
def get_total_active_balance_for_block_root(store: Store, block_root: Root) -> Gwei:
    assert block_root in store.block_states

    state = store.block_states[block_root]

    return get_total_active_balance(state)
```

#### `get_remaining_weight_in_current_epoch`

```python
def get_remaining_weight_in_current_epoch(store: Store, checkpoint: Checkpoint) -> Gwei:
    """
    Returns the total weight of votes for this epoch from future committees after the current slot.
    """
    assert checkpoint in store.checkpoint_states

    state = store.checkpoint_states[checkpoint]

    current_slot = get_current_slot(store)
    first_slot_next_epoch = compute_start_slot_at_epoch(Epoch(compute_epoch_at_slot(current_slot) + 1))
    return get_committee_weight_between_slots(state, Slot(current_slot + 1), Slot(first_slot_next_epoch - 1))
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
        leaf_block_roots: Set[Root] = set()
        for child_leaf_block_roots in [get_leaf_block_roots(store, child) for child in children]:
            leaf_block_roots = leaf_block_roots.union(child_leaf_block_roots)
        return leaf_block_roots
    else:
        # This block is a leaf.
        return set([block_root])

```

#### `get_current_epoch_participating_indices`

```python
def get_epoch_participating_indices(state: BeaconState,
                                    active_validator_indices: Sequence[ValidatorIndex],
                                    is_current_epoch: bool) -> Set[ValidatorIndex]:
    if is_current_epoch:
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation

    return set([
        i for i in active_validator_indices
        if has_flag(epoch_participation[i], TIMELY_TARGET_FLAG_INDEX)
    ])
```

#### `get_ffg_support`

```python
def get_ffg_support(store: Store, checkpoint: Root) -> Gwei:
    """
    Returns the total weight supporting the checkpoint in the block's chain at block's epoch.
    """
    current_epoch = get_current_store_epoch(store)

    # This function is only applicable to current and previous epoch blocks
    assert current_epoch in [checkpoint.epoch, checkpoint.epoch + 1]

    if checkpoint not in store.checkpoint_states:
        return Gwei(0)

    checkpoint_state = store.checkpoint_states[checkpoint]

    leaf_roots = [
        leaf for leaf in get_leaf_block_roots(store, checkpoint.root)
        if get_checkpoint_block(store, leaf, checkpoint.epoch) == checkpoint.root]

    active_checkpoint_indices = get_active_validator_indices(checkpoint_state, checkpoint.epoch)
    participating_indices_from_blocks = set().union(*[
        get_epoch_participating_indices(
            store.block_states[root],
            active_checkpoint_indices,
            checkpoint.epoch == current_epoch
        )
        for root in leaf_roots
    ])

    participating_indices_from_lmds = set([
        i
        for i in store.latest_messages
        if get_checkpoint_block(store, store.latest_messages[i].root, store.latest_messages[i].epoch) == checkpoint.root
    ])

    return get_total_balance(checkpoint_state, participating_indices_from_blocks.union(participating_indices_from_lmds))
```


#### `is_ffg_confirmed`

```python
def is_ffg_confirmed(store: Store, block_root: Root, epoch: Epoch) -> bool:
    """
    Returns whether the `block_root`'s checkpoint will be justified by the end of this epoch.
    """
    current_epoch = get_current_store_epoch(store)

    block = store.blocks[block_root]
    block_epoch = compute_epoch_at_slot(block.slot)
    checkpoint = Checkpoint(
        epoch=epoch,
        root=get_checkpoint_block(store, block_root, epoch)
    )

    store_target_checkpoint_state(store, checkpoint)

    # This function is only applicable to current and previous epoch blocks
    assert current_epoch in [block_epoch, block_epoch + 1]

    total_active_balance = int(get_total_active_balance(store.checkpoint_states[checkpoint]))

    ffg_support_for_checkpoint = int(get_ffg_support(store, checkpoint))

    if epoch == current_epoch:
        remaining_ffg_weight = int(get_remaining_weight_in_current_epoch(store, checkpoint))
    else:
        remaining_ffg_weight = 0

    max_adversarial_ffg_support_for_checkpoint = int(
        min(
            ceil_div(total_active_balance * CONFIRMATION_BYZANTINE_THRESHOLD, 100),
            CONFIRMATION_SLASHING_THRESHOLD,
            ffg_support_for_checkpoint
        )
    )

    # Returns whether the following condition is true using only integer arithmetic
    # 2 / 3 * total_active_balance <= (
    #     ffg_support_for_checkpoint - max_adversarial_ffg_support_for_checkpoint +
    #     (1 - CONFIRMATION_BYZANTINE_THRESHOLD / 100) * remaining_ffg_weight
    # )

    return (
        200 * total_active_balance <=
        ffg_support_for_checkpoint * 300 + (300 - 3 * CONFIRMATION_BYZANTINE_THRESHOLD) *
        remaining_ffg_weight - max_adversarial_ffg_support_for_checkpoint * 300
    )
```

### `is_confirmed_no_caching`

```python
def is_confirmed_no_caching(store: Store, block_root: Root) -> bool:
    current_epoch = get_current_store_epoch(store)

    block = store.blocks[block_root]
    block_state = store.block_states[block_root]
    block_epoch = compute_epoch_at_slot(block.slot)

    if current_epoch == block_epoch:
        return (
            get_checkpoint_block(store, block_root, Epoch(current_epoch - 1)) == 
            block_state.current_justified_checkpoint.root
            and is_lmd_confirmed(store, block_root)
            and is_ffg_confirmed(store, block_root, current_epoch)
        )
    else:
        return (
            compute_slots_since_epoch_start(get_current_slot(store)) == 0
            and is_ffg_confirmed(store, block_root, Epoch(current_epoch - 1))
            and any(
                [
                    get_voting_source(store, leaf).epoch + 2 >= current_epoch
                    and is_lmd_confirmed(store, leaf)
                    for leaf in store.leaves_last_slot_previous_epoch
                ]
            )
        )
```

### `is_confirmed`

```python
def is_confirmed(store: Store, block_root: Root) -> bool:
    highest_confirmed_root_since_last_epoch = (
        store.highest_confirmed_block_current_epoch
        if store.blocks[store.highest_confirmed_block_current_epoch].slot >
        store.blocks[store.highest_confirmed_block_previous_epoch].slot
        else store.highest_confirmed_block_previous_epoch)

    return get_ancestor(store, highest_confirmed_root_since_last_epoch, store.blocks[block_root].slot) == block_root
```

#### `find_confirmed_block`

```python
def find_confirmed_block(store: Store, block_root: Root) -> Root:

    if block_root == store.finalized_checkpoint.root:
        return block_root

    block = store.blocks[block_root]
    current_epoch = get_current_store_epoch(store)

    block_epoch = compute_epoch_at_slot(block.slot)

    # If `block_epoch` is not either the current or previous epoch, then return `store.finalized_checkpoint.root`
    if current_epoch not in [block_epoch, block_epoch + 1]:
        return store.finalized_checkpoint.root

    if is_confirmed_no_caching(store, block_root):
        return block_root
    else:
        return find_confirmed_block(store, block.parent_root)

```

#### `immediately_after_on_tick_if_slot_changed`

```python
def immediately_after_on_tick_if_slot_changed(store: Store) -> None:
    """
    This method must be executed immediately after `on_tick` whenever the current slot changes.
    Importantly, any attestation that could not be fed into `on_attestation` at the previous slot
    because of ageing reasons, it must be processed through `on_attestation` before executing this method.
    The reason for not calling this method directly from `on_tick` is that, due to the spec architecture,
    it is impossible to specify the behaviour described above.
    Separating the code execution in this way is therefore necessary to be able to test this functionality properly.
    """
    current_slot = get_current_slot(store)

    if compute_slots_since_epoch_start(Slot(current_slot + 1)) == 0:
        store.leaves_last_slot_previous_epoch = get_leaf_block_roots(store, store.finalized_checkpoint.root)

    highest_confirmed_root = find_confirmed_block(store, get_head(store))
    if (store.blocks[highest_confirmed_root].slot > store.blocks[store.highest_confirmed_block_current_epoch].slot
       or compute_slots_since_epoch_start(current_slot) == 1):
        store.highest_confirmed_block_current_epoch = highest_confirmed_root

    if compute_slots_since_epoch_start(current_slot) == 0:
        store.highest_confirmed_block_previous_epoch = store.highest_confirmed_block_current_epoch
```