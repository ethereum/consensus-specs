# PQ -- Fast Confirmation

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Fast Confirmation Rule](#fast-confirmation-rule)
  - [Helpers](#helpers)
    - [LMD-GHOST helpers](#lmd-ghost-helpers)
      - [Modified `compute_committee_weight_between_slots`](#modified-compute_committee_weight_between_slots)
      - [Modified `get_equivocation_score`](#modified-get_equivocation_score)
      - [Modified `get_node_support_between_slots`](#modified-get_node_support_between_slots)
    - [FFG helpers](#ffg-helpers)
      - [Modified `get_current_target_score`](#modified-get_current_target_score)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fast confirmation rule accompanying the PQ
upgrade, which reads validators from `state.pq_validators`.

## Fast Confirmation Rule

### Helpers

#### LMD-GHOST helpers

##### Modified `compute_committee_weight_between_slots`

```python
def compute_committee_weight_between_slots(
    store: Store, balance_source: BeaconState, start_slot: Slot, end_slot: Slot
) -> Gwei:
    """
    Compute total weight of committees
    between ``start_slot`` and ``end_slot`` (inclusive of both).
    """

    # Sanity check
    if start_slot > end_slot:
        return Gwei(0)

    # If an entire epoch is covered by the range, return the total active balance
    if is_full_validator_set_covered(start_slot, end_slot):
        return get_total_active_balance(balance_source)

    # Get indices of validators assigned to committees between the slots
    participants: set[ValidatorIndex] = set()
    for slot in range(start_slot, end_slot + 1):
        participants.update(get_slot_committee(store, Slot(slot)))

    # Sort out validators not active in the view of a balance source
    active_participants: set[ValidatorIndex] = set()
    current_epoch = get_current_epoch(balance_source)
    for index in participants:
        # [Modified in PQ]
        if is_active_validator(balance_source.pq_validators[index], current_epoch):
            active_participants.add(index)

    # Return total balance of the participants
    return get_total_balance(balance_source, active_participants)
```

##### Modified `get_equivocation_score`

```python
def get_equivocation_score(
    store: Store,
    balance_source: BeaconState,
    start_slot: Slot,
    end_slot: Slot,
) -> Gwei:
    """
    Return total weight of equivocating participants of all committees
    in the slots between ``start_slot`` and ``end_slot`` (inclusive of both).
    """
    committee_indices: set[ValidatorIndex] = set()
    for slot in range(start_slot, end_slot + 1):
        committee_indices.update(get_slot_committee(store, Slot(slot)))

    # Keep equivocating validators that were active at the balance_source epoch to be consistent
    # with get_total_active_balance() computation
    active_equivocating_indices = [
        index
        for index in committee_indices.intersection(store.equivocating_indices)
        # [Modified in PQ]
        if is_active_validator(
            balance_source.pq_validators[index], get_current_epoch(balance_source)
        )
    ]

    return Gwei(
        sum(
            # [Modified in PQ]
            balance_source.pq_validators[index].effective_balance
            for index in active_equivocating_indices
        )
    )
```

##### Modified `get_node_support_between_slots`

```python
def get_node_support_between_slots(
    store: Store,
    balance_source: BeaconState,
    node: ForkChoiceNode,
    start_slot: Slot,
    end_slot: Slot,
) -> Gwei:
    """
    Return support of the node by validators assigned to slots
    between ``start_slot`` and ``end_slot`` (inclusive of both).
    """
    participants: set[ValidatorIndex] = set()
    for slot in range(start_slot, end_slot + 1):
        participants.update(get_slot_committee(store, Slot(slot)))

    # Keep validators that were active at the balance_source epoch to be consistent
    # with get_total_active_balance() computation, also filter out slashed validators
    unslashed_and_active_indices = [
        index
        for index in participants
        if (
            # [Modified in PQ]
            not balance_source.pq_validators[index].slashed
            and is_active_validator(
                # [Modified in PQ]
                balance_source.pq_validators[index],
                get_current_epoch(balance_source),
            )
        )
    ]

    return Gwei(
        sum(
            # [Modified in PQ]
            balance_source.pq_validators[index].effective_balance
            for index in unslashed_and_active_indices
            # Check that validator has voted in the support of the node
            # and has not been slashed
            if (
                index in store.latest_messages
                and get_supported_node(store, store.latest_messages[index]) == node
                and index not in store.equivocating_indices
            )
        )
    )
```

#### FFG helpers

##### Modified `get_current_target_score`

```python
def get_current_target_score(store: Store) -> Gwei:
    """
    Return the estimate of FFG support of the current epoch target by using LMD-GHOST votes.
    """
    target = get_current_target(store)
    state = get_pulled_up_head_state(store)
    unslashed_and_active_indices = [
        index
        for index in get_active_validator_indices(state, get_current_epoch(state))
        # [Modified in PQ]
        if not state.pq_validators[index].slashed
    ]
    return Gwei(
        sum(
            # [Modified in PQ]
            state.pq_validators[index].effective_balance
            for index in unslashed_and_active_indices
            if (
                index in store.latest_messages
                and index not in store.equivocating_indices
                and target
                == get_checkpoint_for_block(
                    store,
                    store.latest_messages[index].root,
                    get_latest_message_epoch(store.latest_messages[index]),
                )
            )
        )
    )
```
