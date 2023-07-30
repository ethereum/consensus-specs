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
    - [`committee_spans_full_epoch`](#committee_spans_full_epoch)
    - [`committee_for_block_spans_full_epoch`](#committee_for_block_spans_full_epoch)
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
  - [`is_confirmed`](#is_confirmed)
- [Safe Block Hash](#safe-block-hash)
  - [Helper Functions](#helper-functions-1)
    - [`find_confirmed_block`](#find_confirmed_block)
  - [`get_safe_beacon_block_root``](#get_safe_beacon_block_root)
  - [`get_safe_execution_payload_hash`](#get_safe_execution_payload_hash)
- [Confirmation Score](#confirmation-score)
  - [Helper Functions](#helper-functions-2)
    - [`get_one_confirmation_score`](#get_one_confirmation_score)
    - [`get_lmd_confirmation_score`](#get_lmd_confirmation_score)
    - [`get_ffg_confirmation_score_current_epoch`](#get_ffg_confirmation_score_current_epoch)
    - [`get_ffg_confirmation_score`](#get_ffg_confirmation_score)
  - [`get_confirmation_score`](#get_confirmation_score)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document specifies a fast block confirmation rule for the Ethereum protocol.

*Note*: Confirmation is not a substitute for finality! The safety of confirmations is weaker than that of finality.

The research paper for this rule is attached in this [ethresear.ch post](https://ethresear.ch/t/confirmation-rule-for-ethereum-pos/15454).

This rule makes the following network synchrony assumption: starting from the current slot, attestations created by honest validators in any slot are received by the end of that slot.
Consequently, this rule provides confirmations to users who believe in the above assumption. If this assumption is broken, confirmed blocks can be reorged without any adversarial behavior and without slashing.

There are two algorithms in the document:
- [**Confirmation Rule**](#confirmation-rule): Given a block and confirmation safety parameters, outputs whether the block is confirmed.
- [**Confirmation Score**](#confirmation-score): Given a block, outputs the confirmation score for the block, i.e., the maximum possible confirmation safety parameters to deem the block confirmed.

*Note*: These algorithms use unbounded integer arithmetic in some places. The rest of `consensus-specs` uses `uint64` arithmetic exclusively to ensure that results fit into length-limited fields - a property crucial for consensus objects (such as the `BeaconBlockBody`). This document describes a local confirmation rule that does not require storing anything in length-limited fields. Using unbounded integer arithmetic here prevents possible overflowing issues for the spec tests generated using this Python specification (or when executing these specifications directly).

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

#### `committee_spans_full_epoch`

```python
def committee_spans_full_epoch(start_slot: Slot, end_slot: Slot) -> bool:
    """
    Returns whether the range from ``start_slot`` to ``end_slot`` (inclusive of both) includes and entire epoch
    """
    start_epoch = compute_epoch_at_slot(start_slot)
    end_epoch = compute_epoch_at_slot(end_slot)

    return (
        end_epoch > start_epoch + 1 or
        (end_epoch == start_epoch + 1 and start_slot % SLOTS_PER_EPOCH == 0))
```

#### `committee_for_block_spans_full_epoch`

```python
def committee_for_block_spans_full_epoch(store: Store, block_root: Root) -> bool:
    """
    Returns whether the range from ``start_slot`` to ``end_slot`` (inclusive of both) includes and entire epoch
    """
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    parent_block = store.blocks[block.parent_root]
    
    return committee_spans_full_epoch(Slot(parent_block.slot + 1), current_slot)
```

#### `ceil_div`

```python
def ceil_div(numerator: int, denominator: int) -> int:
    """
    Returns ``ceil(numerator / denominator)`` using only integer arithmetic
    """
    result = numerator // denominator
    if numerator % denominator != 0:
        result = result + 1
    return result
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
    if committee_spans_full_epoch(start_slot, end_slot):
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
        get_committee_weight_between_slots(justified_state, Slot(parent_block.slot + 1), current_slot)
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

    if committee_for_block_spans_full_epoch(store, block_root):
        return is_one_confirmed(store, block_root)
    else:
        block = store.blocks[block_root]
        return (
            is_one_confirmed(store, block_root) and
            is_lmd_confirmed(store, block.parent_root)
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
def get_remaining_weight_in_current_epoch(store: Store, block_root: Root) -> Gwei:
    """ 
    Returns the total weight of votes for this epoch from future committees after the current slot.
    """
    assert block_root in store.block_states

    state = store.block_states[block_root]

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
                                    current_epoch: bool) -> Set[ValidatorIndex]: 
    if current_epoch:
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
def get_ffg_support(store: Store, block_root: Root) -> Gwei:
    """
    Returns the total weight supporting the checkpoint in the block's chain at block's epoch.
    """
    block = store.blocks[block_root]
    block_epoch = compute_epoch_at_slot(block.slot)
    current_epoch = get_current_store_epoch(store)

    # This function is only applicable to current and previous epoch blocks
    assert current_epoch in [block_epoch, block_epoch + 1]

    checkpoint_root = get_checkpoint_block(store, block_root, block_epoch)
    checkpoint = Checkpoint(root=checkpoint_root, epoch=block_epoch)

    if checkpoint not in store.checkpoint_states:
        return Gwei(0)

    checkpoint_state = store.checkpoint_states[checkpoint]

    leaf_roots = get_leaf_block_roots(store, block_root)

    active_checkpoint_indices = get_active_validator_indices(checkpoint_state, block_epoch)
    participating_indices = set().union(*[
        get_epoch_participating_indices(
            store.block_states[root], 
            active_checkpoint_indices, 
            block_epoch == current_epoch
        )
        for root in leaf_roots
    ])

    return get_total_balance(checkpoint_state, participating_indices)
```


#### `is_ffg_confirmed`

```python
def is_ffg_confirmed(store: Store, block_root: Root) -> bool:
    """
    Returns whether the `block_root`'s checkpoint will be justified by the end of this epoch.
    """
    current_epoch = get_current_store_epoch(store)

    block = store.blocks[block_root]
    block_epoch = compute_epoch_at_slot(block.slot)

    # This function is only applicable to current and previous epoch blocks
    assert current_epoch in [block_epoch, block_epoch + 1]

    total_active_balance = int(get_total_active_balance_for_block_root(store, block_root))

    ffg_support_for_checkpoint = int(get_ffg_support(store, block_root))

    if block_epoch == current_epoch:
        remaining_ffg_weight = int(get_remaining_weight_in_current_epoch(store, block_root))
    else:
        remaining_ffg_weight = 0

    max_adversarial_ffg_support_for_checkpoint = int(
        min(
            (total_active_balance * CONFIRMATION_BYZANTINE_THRESHOLD - 1) // 100 + 1,
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

### `is_confirmed`

```python
def is_confirmed(store: Store, block_root: Root) -> bool:
    current_epoch = get_current_store_epoch(store)

    block = store.blocks[block_root]
    block_state = store.block_states[block_root]
    block_justified_checkpoint_epoch = block_state.current_justified_checkpoint.epoch
    block_epoch = compute_epoch_at_slot(block.slot)

    # This function is only applicable to current and previous epoch blocks
    assert current_epoch in [block_epoch, block_epoch + 1]

    if block_epoch == current_epoch and block_justified_checkpoint_epoch + 1 != current_epoch:
        return False

    if block_epoch != current_epoch and block_justified_checkpoint_epoch + 2 < current_epoch:
        return False

    return (
        is_lmd_confirmed(store, block_root)
        and is_ffg_confirmed(store, block_root)
    )
```

## Safe Block Hash

This function is used to compute the value of the `safeBlockHash` field which is passed from CL to EL in the `forkchoiceUpdated` Engine API call.

### Helper Functions

#### `find_confirmed_block`

```python
def find_confirmed_block(store: Store, block_root: Root) -> Root:

    block = store.blocks[block_root]
    current_epoch = get_current_store_epoch(store)

    block_epoch = compute_epoch_at_slot(block.slot)

    # If `block_epoch` is not either the current or previous epoch, then return `store.finalized_checkpoint.root`
    if current_epoch not in [block_epoch, block_epoch + 1]:
        return store.finalized_checkpoint.root

    if is_confirmed(store, block_root):
        return block_root
    else:
        return find_confirmed_block(store, block.parent_root)

```

### `get_safe_beacon_block_root``

```python
def get_safe_beacon_block_root(store: Store) -> Root:
    head_root = get_head(store)

    return find_confirmed_block(store, head_root)
```

### `get_safe_execution_payload_hash`

```python
def get_safe_execution_payload_hash(store: Store) -> Hash32:
    safe_block_root = get_safe_beacon_block_root(store)
    safe_block = store.blocks[safe_block_root]

    # Return Hash32() if no payload is yet justified
    if compute_epoch_at_slot(safe_block.slot) >= BELLATRIX_FORK_EPOCH:
        return safe_block.body.execution_payload.block_hash
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
    justified_state = store.checkpoint_states[store.justified_checkpoint]
    maximum_support = int(
        get_committee_weight_between_slots(justified_state, Slot(parent_block.slot + 1), current_slot)
    )
    proposer_score = int(get_proposer_score(store))

    # Return the max possible one_confirmation_score such that:
    # support / maximum_support > \
    #     0.5 * (1 + proposer_score / maximum_support) + one_confirmation_score / 100

    return max((100 * support - 50 * proposer_score - 1) // maximum_support - 50, UNCONFIRMED_SCORE)
```

#### `get_lmd_confirmation_score`

```python
def get_lmd_confirmation_score(store: Store, block_root: Root) -> int:
    if block_root == store.finalized_checkpoint.root:
        return MAX_CONFIRMATION_SCORE
    else:
        block = store.blocks[block_root]
        finalized_block = store.blocks[store.finalized_checkpoint.root]
        if block.slot <= finalized_block.slot:
            # This block is not in the finalized chain.
            return UNCONFIRMED_SCORE
        else:
            # Check one_confirmed score for this block and LMD_confirmed score for the preceding chain.
            return min(
                get_one_confirmation_score(store, block_root),
                get_lmd_confirmation_score(store, block.parent_root)
            )
```

#### `get_ffg_confirmation_score_current_epoch`

```python
def get_ffg_confirmation_score_helper(total_active_balance: int,
                                      ffg_support_for_checkpoint: int,
                                      min_ffg_support_slash_th: int,
                                      remaining_ffg_weight: int) -> int:
    assert min_ffg_support_slash_th <= ffg_support_for_checkpoint
    
    """
    Return the max possible ffg_confirmation_score such that:
    2 / 3 * total_active_balance <= \
        ffg_support_for_checkpoint - \
        min(min_ffg_support_slash_th, total_active_balance * ffg_confirmation_score / 100) + \
        (1 - ffg_confirmation_score / 100) * remaining_ffg_weight
    """

    # Case 1: min_ffg_support_slash_th <= total_active_balance * ffg_confirmation_score / 100
    #
    # In this case the problem reduces to returning the max possible ffg_confirmation_score such that:
    #
    # 2 / 3 * total_active_balance <= \
    #     ffg_support_for_checkpoint - min_ffg_support_slash_th + (1 - ffg_confirmation_score / 100) * 
    #     remaining_ffg_weight
    #
    # If remaining_ffg_weight > 0, then first we compute ffg_confirmation_score and then check that the condition for
    # this case is satisfied. If it is, then we return the calculated ffg_confirmation_score. If not, we proceed to the
    # next case.
    #
    # If remaining_ffg_weight == 0, then the problem further reduces to whether the following condition, which is
    # independent of ffg_confirmation_score, is satisfied:
    #
    # 2 / 3 * total_active_balance <= ffg_support_for_checkpoint - min_ffg_support_slash_th
    #
    # If it is satisfied, then it means that ffg_support_for_checkpoint can be as high as the maximum fraction of
    # adversarial stake that the consensus protocol can deal with, i.e., < 1/3.
    # If it not satisfied, then we proceed to the next case.

    if remaining_ffg_weight > 0:
        ffg_confirmation_score = (
            100 * (
                3 * (ffg_support_for_checkpoint - min_ffg_support_slash_th + remaining_ffg_weight) 
                - 2 * total_active_balance
            ) // (3 * remaining_ffg_weight)
        )
        if min_ffg_support_slash_th * 100 <= total_active_balance * ffg_confirmation_score:
            return ffg_confirmation_score
    else:
        if 2 * total_active_balance <= (ffg_support_for_checkpoint - min_ffg_support_slash_th) * 3:
            return 100 // 3

    # Case 2: min_ffg_support_slash_th > total_active_balance * ffg_confirmation_score / 100
    #
    # In this case the problem reduces to returning the max possible ffg_confirmation_score such that:
    #
    # 2 / 3 * total_active_balance <= \
    #     ffg_support_for_checkpoint - \
    #     total_active_balance * ffg_confirmation_score / 100 + \
    #     (1 - ffg_confirmation_score / 100) * remaining_ffg_weight

    ffg_confirmation_score = (
        100 * (3 * (ffg_support_for_checkpoint + remaining_ffg_weight) - 2 * total_active_balance) //
        (3 * (remaining_ffg_weight + total_active_balance))
    )
    assert ffg_support_for_checkpoint * 100 > total_active_balance * ffg_confirmation_score
    return max(ffg_confirmation_score, UNCONFIRMED_SCORE)
```

#### `get_ffg_confirmation_score`

```python
def get_ffg_confirmation_score(store: Store, block_root: Root) -> int:

    current_epoch = get_current_store_epoch(store)

    block = store.blocks[block_root]
    block_epoch = compute_epoch_at_slot(block.slot)

    # This function is only applicable to current and previous epoch blocks
    assert current_epoch in [block_epoch, block_epoch + 1]

    total_active_balance = int(get_total_active_balance_for_block_root(store, block_root))

    ffg_support_for_checkpoint = int(get_ffg_support(store, block_root))

    min_ffg_support_slash_th = min(ffg_support_for_checkpoint, CONFIRMATION_SLASHING_THRESHOLD)

    if block_epoch == current_epoch:
        remaining_ffg_weight = int(get_remaining_weight_in_current_epoch(store, block_root))
    else:
        remaining_ffg_weight = 0  

    return get_ffg_confirmation_score_helper(
        total_active_balance,
        ffg_support_for_checkpoint,
        min_ffg_support_slash_th,
        remaining_ffg_weight
    )          
```

### `get_confirmation_score`

```python
def get_confirmation_score(store: Store, block_root: Root) -> int:
    """
    Return `UNCONFIRMED_SCORE` in the case that `block_root` cannot be confirmed even by assuming no adversary weight,
    otherwise it returns the maximum percentage of adversary weight that is admissible in order to
    consider `block_root` confirmed.
    """
    current_epoch = get_current_store_epoch(store)

    block = store.blocks[block_root]
    block_epoch = compute_epoch_at_slot(block.slot)

    # This function is only applicable to current and previous epoch blocks
    assert current_epoch in [block_epoch, block_epoch + 1]

    block_state = store.block_states[block_root]
    block_justified_checkpoint_epoch = block_state.current_justified_checkpoint.epoch

    if block_epoch == current_epoch and block_justified_checkpoint_epoch + 1 != current_epoch:
        return UNCONFIRMED_SCORE

    if block_epoch != current_epoch and block_justified_checkpoint_epoch + 2 < current_epoch:
        return UNCONFIRMED_SCORE

    return min(
        get_lmd_confirmation_score(store, block_root),
        get_ffg_confirmation_score(store, block_root)
    )            
```
