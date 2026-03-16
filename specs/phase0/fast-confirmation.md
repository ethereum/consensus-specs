# Phase 0 -- Fast Confirmation

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Fast Confirmation Rule](#fast-confirmation-rule)
  - [Constants](#constants)
  - [Configuration](#configuration)
  - [Helpers](#helpers)
    - [Misc helper functions](#misc-helper-functions)
      - [`get_block_slot`](#get_block_slot)
      - [`get_block_epoch`](#get_block_epoch)
      - [`get_checkpoint_for_block`](#get_checkpoint_for_block)
      - [`get_current_target`](#get_current_target)
      - [`is_start_slot_at_epoch`](#is_start_slot_at_epoch)
      - [`is_ancestor`](#is_ancestor)
      - [`get_ancestor_roots`](#get_ancestor_roots)
    - [State helpers](#state-helpers)
      - [`get_slot_committee`](#get_slot_committee)
      - [`get_pulled_up_head_state`](#get_pulled_up_head_state)
      - [`get_previous_balance_source`](#get_previous_balance_source)
      - [`get_current_balance_source`](#get_current_balance_source)
    - [LMD-GHOST helpers](#lmd-ghost-helpers)
      - [`get_block_support_between_slots`](#get_block_support_between_slots)
      - [`is_full_validator_set_covered`](#is_full_validator_set_covered)
      - [`adjust_committee_weight_estimate_to_ensure_safety`](#adjust_committee_weight_estimate_to_ensure_safety)
      - [`estimate_committee_weight_between_slots`](#estimate_committee_weight_between_slots)
      - [`get_equivocation_score`](#get_equivocation_score)
      - [`compute_adversarial_weight`](#compute_adversarial_weight)
      - [`get_adversarial_weight`](#get_adversarial_weight)
      - [`compute_empty_slot_support_discount`](#compute_empty_slot_support_discount)
      - [`get_support_discount`](#get_support_discount)
      - [`compute_safety_threshold`](#compute_safety_threshold)
      - [`is_one_confirmed`](#is_one_confirmed)
      - [`is_confirmed_chain_safe`](#is_confirmed_chain_safe)
    - [FFG helpers](#ffg-helpers)
      - [`get_current_target_score`](#get_current_target_score)
      - [`compute_honest_ffg_support_for_current_target`](#compute_honest_ffg_support_for_current_target)
      - [`will_no_conflicting_checkpoint_be_justified`](#will_no_conflicting_checkpoint_be_justified)
      - [`will_current_target_be_justified`](#will_current_target_be_justified)
    - [`update_fast_confirmation_variables`](#update_fast_confirmation_variables)
    - [`find_latest_confirmed_descendant`](#find_latest_confirmed_descendant)
    - [`get_latest_confirmed`](#get_latest_confirmed)
  - [Handlers](#handlers)
    - [`on_fast_confirmation`](#on_fast_confirmation)

<!-- mdformat-toc end -->

## Introduction

This document specifies a fast block confirmation rule (a.k.a. FCR) for the
Ethereum protocol.

The research paper for this rule can be found
[here](https://arxiv.org/abs/2405.00549).

A shorter explainer is available
[here](https://www.overleaf.com/project/691b4629fb781aeb8efdb20f).

This rule makes the following network synchrony assumption: starting from the
current slot, attestations created by honest validators in any slot are received
by the end of that slot. Consequently, this rule provides confirmations to users
who believe in the above assumption. If this assumption is broken, confirmed
blocks can be reorged without any adversarial behavior and without slashing.

## Fast Confirmation Rule

### Constants

| Name                                            | Value       | Description                                                                                                                                                                                                                                                                                                                     |
| ----------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `COMMITTEE_WEIGHT_ESTIMATION_ADJUSTMENT_FACTOR` | `uint64(5)` | Per mille value to add to the estimation of the committee weight across a range of slots not covering a full epoch in order to ensure the safety of the confirmation rule with high probability. See [here](https://gist.github.com/saltiniroberto/9ee53d29c33878d79417abb2b4468c20) for an explanation about the value chosen. |

### Configuration

| Name                               | Value        | Max. Value   | Description                                                                 |
| ---------------------------------- | ------------ | ------------ | --------------------------------------------------------------------------- |
| `CONFIRMATION_BYZANTINE_THRESHOLD` | `uint64(25)` | `uint64(25)` | Assumed maximum percentage of Byzantine validators among the validator set. |

### Helpers

#### Misc helper functions

##### `get_block_slot`

```python
def get_block_slot(store: Store, block_root: Root) -> Slot:
    """
    Return a slot of the block.
    """
    return store.blocks[block_root].slot
```

##### `get_block_epoch`

```python
def get_block_epoch(store: Store, block_root: Root) -> Epoch:
    """
    Return an epoch of the block.
    """
    return compute_epoch_at_slot(store.blocks[block_root].slot)
```

##### `get_checkpoint_for_block`

```python
def get_checkpoint_for_block(store: Store, block_root: Root, epoch: Epoch) -> Checkpoint:
    """
    Return a checkpoint in the chain of the block at the ``epoch``.
    """
    return Checkpoint(epoch=epoch, root=get_checkpoint_block(store, block_root, epoch))
```

##### `get_current_target`

```python
def get_current_target(store: Store) -> Checkpoint:
    """
    Return current epoch target.
    """
    head = get_head(store)
    current_epoch = get_current_store_epoch(store)
    return get_checkpoint_for_block(store, head, current_epoch)
```

##### `is_start_slot_at_epoch`

```python
def is_start_slot_at_epoch(slot: Slot) -> bool:
    """
    Return ``True`` if ``slot`` is the start slot of an epoch.
    """
    return compute_slots_since_epoch_start(slot) == 0
```

##### `is_ancestor`

```python
def is_ancestor(store: Store, block_root: Root, ancestor_root: Root) -> bool:
    """
    Return ``True`` if ``ancestor_root`` is an ancestor of ``block_root``.
    """
    return get_ancestor(store, block_root, store.blocks[ancestor_root].slot) == ancestor_root
```

##### `get_ancestor_roots`

```python
def get_ancestor_roots(store: Store, block_root: Root, terminal_root: Root) -> list[Root]:
    """
    Return a list of ancestors of ``block_root`` inclusive until ``terminal_root`` exclusive.
    """
    root = block_root
    ancestor_roots: list[Root] = []
    while store.blocks[root].slot > store.blocks[terminal_root].slot:
        ancestor_roots.insert(0, root)
        root = store.blocks[root].parent_root

        # Return when terminal_root is reached
        if root == terminal_root:
            return ancestor_roots

    # Return empty list if terminal_root is not in the chain of block_root
    return []
```

#### State helpers

This section encapsulates reads from different beacon states used by the Fast
Confirmation Rule.

Implementations MAY override the logic of each of these functions but the
semantics MUST be preserved.

##### `get_slot_committee`

*Note:* This function returns the committee for a specific slot. It MUST support
committees of epochs starting from `current_epoch - 2`.

```python
def get_slot_committee(store: Store, slot: Slot) -> set[ValidatorIndex]:
    """
    Return participants of all committees in ``slot``.
    """
    head = get_head(store)
    # Use head state as the source of shuffling.
    shuffling_source = store.block_states[head]
    committees_count = get_committee_count_per_slot(shuffling_source, compute_epoch_at_slot(slot))
    participants: set[ValidatorIndex] = set()
    for i in range(committees_count):
        participants.update(get_beacon_committee(shuffling_source, slot, CommitteeIndex(i)))
    return participants
```

##### `get_pulled_up_head_state`

```python
def get_pulled_up_head_state(store: Store) -> BeaconState:
    """
    Return the state of the head pulled up to the current epoch if needed.
    """
    head = get_head(store)
    head_state = store.block_states[head]
    if get_current_epoch(head_state) < get_current_store_epoch(store):
        pulled_up_state = copy(head_state)
        process_slots(pulled_up_state, compute_start_slot_at_epoch(get_current_store_epoch(store)))
        return pulled_up_state
    else:
        return head_state
```

##### `get_previous_balance_source`

*Notes:*

Reconfirmation is the only place where previous balance source is used.
Implementations MAY switch to the current epoch balance source after they run
reconfirmation and before the logic to confirm new blocks is called. In this
case implementations will need to keep only a single balance source around.

```python
def get_previous_balance_source(store: Store) -> BeaconState:
    return store.checkpoint_states[store.previous_epoch_observed_justified_checkpoint]
```

##### `get_current_balance_source`

```python
def get_current_balance_source(store: Store) -> BeaconState:
    return store.checkpoint_states[store.current_epoch_observed_justified_checkpoint]
```

#### LMD-GHOST helpers

##### `get_block_support_between_slots`

*Notes:*

Validator votes from slots before `start_slot` and after `end_slot` might not be
distinguished from votes submitted by that same validator in
`[start_slot; end_slot]` interval. Due to committee shuffling near epoch
boundary the following cases are possible:

1. Validator assigned to `start_slot - 1` and `end_slot` votes for `block_root`
   in `start_slot - 1` but does not vote in `end_slot`.
2. Validator assigned to `start_slot` and `end_slot + 1` misses a vote in
   `start_slot`, but votes for `block_root` in `end_slot + 1`.

In both cases the support would count a vote outside of the
`[start_slot; end_slot]` range. This inaccuracy is acceptable as it doesn't
affect safety.

Due to the algorithm logic, maximum distance between `balance_source` and
shuffling is two epochs which is less than `MAX_SEED_LOOKAHEAD` and thus the
balances are always consistent with the shuffling.

```python
def get_block_support_between_slots(
    store: Store,
    balance_source: BeaconState,
    block_root: Root,
    start_slot: Slot,
    end_slot: Slot,
) -> Gwei:
    """
    Return support of the block by validators assigned to slots
    between ``start_slot`` and ``end_slot`` (inclusive of both).
    """
    participants: set[ValidatorIndex] = set()
    for slot in range(start_slot, end_slot + 1):
        participants.update(get_slot_committee(store, Slot(slot)))

    return Gwei(
        sum(
            balance_source.validators[i].effective_balance
            for i in participants
            # Check that validator is in the balance source set,
            # has voted in the support of the block
            # and hasn't been slashed.
            if (
                i < len(balance_source.validators)
                and i in store.latest_messages
                and store.latest_messages[i].root == block_root
                and i not in store.equivocating_indices
                and not balance_source.validators[i].slashed
            )
        )
    )
```

##### `is_full_validator_set_covered`

```python
def is_full_validator_set_covered(start_slot: Slot, end_slot: Slot) -> bool:
    """
    Return ``True`` if the range between ``start_slot`` and ``end_slot`` (inclusive of both) includes an entire epoch.
    """
    start_full_epoch = compute_epoch_at_slot(start_slot + (SLOTS_PER_EPOCH - 1))
    end_full_epoch = compute_epoch_at_slot(Slot(end_slot + 1))

    return start_full_epoch < end_full_epoch
```

##### `adjust_committee_weight_estimate_to_ensure_safety`

*Notes*:

This function adjust the estimate of the weight of a committee for a sequence of
slots not covering a full epoch to ensure the safety of FCR with high
probability.

See https://gist.github.com/saltiniroberto/9ee53d29c33878d79417abb2b4468c20 for
an explanation of why this is required.

```python
def adjust_committee_weight_estimate_to_ensure_safety(estimate: Gwei) -> Gwei:
    """
    Return adjusted ``estimate`` of the weight of a committee for a sequence of slots not covering a full epoch.
    """
    return Gwei(estimate // 1000 * (1000 + COMMITTEE_WEIGHT_ESTIMATION_ADJUSTMENT_FACTOR))
```

##### `estimate_committee_weight_between_slots`

```python
def estimate_committee_weight_between_slots(
    total_active_balance: Gwei, start_slot: Slot, end_slot: Slot
) -> Gwei:
    """
    Return estimate of the total weight of committees
    between ``start_slot`` and ``end_slot`` (inclusive of both).
    """

    # Sanity check
    if start_slot > end_slot:
        return Gwei(0)

    # If an entire epoch is covered by the range, return the total active balance
    if is_full_validator_set_covered(start_slot, end_slot):
        return total_active_balance

    start_epoch = compute_epoch_at_slot(start_slot)
    end_epoch = compute_epoch_at_slot(end_slot)
    committee_weight = total_active_balance // SLOTS_PER_EPOCH
    if start_epoch == end_epoch:
        return committee_weight * (end_slot - start_slot + 1)
    else:
        # First, calculate the number of committees in the end epoch
        num_slots_in_end_epoch = compute_slots_since_epoch_start(end_slot) + 1
        # Next, calculate the number of slots remaining in the end epoch
        remaining_slots_in_end_epoch = SLOTS_PER_EPOCH - num_slots_in_end_epoch
        # Then, calculate the number of slots in the start epoch
        num_slots_in_start_epoch = SLOTS_PER_EPOCH - compute_slots_since_epoch_start(start_slot)

        start_epoch_weight = committee_weight * num_slots_in_start_epoch
        end_epoch_weight = committee_weight * num_slots_in_end_epoch

        # A range that spans an epoch boundary, but does not span any full epoch
        # needs pro-rata calculation, see https://gist.github.com/saltiniroberto/9ee53d29c33878d79417abb2b4468c20
        # start_epoch_weight_pro_rated = start_epoch_weight * (1 - num_slots_in_end_epoch / SLOTS_PER_EPOCH)
        start_epoch_weight_pro_rated = (
            start_epoch_weight // SLOTS_PER_EPOCH * remaining_slots_in_end_epoch
        )

        return adjust_committee_weight_estimate_to_ensure_safety(
            Gwei(start_epoch_weight_pro_rated + end_epoch_weight)
        )
```

##### `get_equivocation_score`

*Note:* For simplicity, this function doesn't seek `balance_source` for slashed
validators as it is very unlikely that those validators aren't already in
`store.equivocating_indices`.

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

    equivocating_participants = committee_indices.intersection(store.equivocating_indices)
    return Gwei(
        sum(
            balance_source.validators[i].effective_balance
            for i in equivocating_participants
            # Check that validator is in the balance source set.
            if i < len(balance_source.validators)
        )
    )
```

##### `compute_adversarial_weight`

*Notes*:

This function computes maximum possible weight that can be adversarial in the
committees of the span of slots assuming `CONFIRMATION_BYZANTINE_THRESHOLD` and
discounting already equivocated validators.

```python
def compute_adversarial_weight(
    store: Store,
    balance_source: BeaconState,
    start_slot: Slot,
    end_slot: Slot,
) -> Gwei:
    """
    Return maximum possible adversarial weight in the committees of the slots
    between ``start_slot`` and ``end_slot`` (inclusive of both).
    """
    total_active_balance = get_total_active_balance(balance_source)
    maximum_weight = estimate_committee_weight_between_slots(
        total_active_balance, start_slot, end_slot
    )
    max_adversarial_weight = maximum_weight // 100 * CONFIRMATION_BYZANTINE_THRESHOLD

    # Discount total weight of equivocating validators.
    equivocation_score = get_equivocation_score(store, balance_source, start_slot, end_slot)
    if max_adversarial_weight > equivocation_score:
        return Gwei(max_adversarial_weight - equivocation_score)
    else:
        return Gwei(0)
```

##### `get_adversarial_weight`

```python
def get_adversarial_weight(store: Store, balance_source: BeaconState, block_root: Root) -> Gwei:
    """
    Return maximum adversarial weight that can support the block.
    """
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    if get_block_epoch(store, block_root) > get_block_epoch(store, block.parent_root):
        # Use the first epoch slot as the start slot when crossing epoch boundary.
        start_slot = compute_start_slot_at_epoch(get_block_epoch(store, block_root))
        return compute_adversarial_weight(store, balance_source, start_slot, Slot(current_slot - 1))
    else:
        return compute_adversarial_weight(store, balance_source, block.slot, Slot(current_slot - 1))
```

##### `compute_empty_slot_support_discount`

*Note:* This function MAY compute parent's block support and adversarial weight
for empty slots belonging to `current_epoch - 2`. It can only happen in
reconfirmation, in all other cases the earliest possible epoch is
`current_epoch - 1`.

```python
def compute_empty_slot_support_discount(
    store: Store, balance_source: BeaconState, block_root: Root
) -> Gwei:
    """
    Return weight that can be discounted during the safety threshold computation
    if there are empty slots preceding the block.
    """
    block = store.blocks[block_root]
    parent_block = store.blocks[block.parent_root]
    # No empty slot.
    if parent_block.slot + 1 == block.slot:
        return Gwei(0)

    # Discount votes supporting the parent block if they are from the committees of empty slots.
    parent_support_in_empty_slots = get_block_support_between_slots(
        store,
        balance_source,
        block.parent_root,
        Slot(parent_block.slot + 1),
        Slot(block.slot - 1),
    )
    # Adversarial weight is not discounted.
    adversarial_weight = compute_adversarial_weight(
        store, balance_source, Slot(parent_block.slot + 1), Slot(block.slot - 1)
    )
    if parent_support_in_empty_slots > adversarial_weight:
        return parent_support_in_empty_slots - adversarial_weight
    else:
        return Gwei(0)
```

##### `get_support_discount`

```python
def get_support_discount(store: Store, balance_source: BeaconState, block_root: Root) -> Gwei:
    """
    Return weight that can be discounted during the safety threshold computation for the block.
    """

    # Empty slot support discount
    return compute_empty_slot_support_discount(store, balance_source, block_root)
```

##### `compute_safety_threshold`

```python
def compute_safety_threshold(store: Store, block_root: Root, balance_source: BeaconState) -> Gwei:
    """
    Compute the LMD_GHOST safety threshold for ``block_root``.
    """
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    parent_block = store.blocks[block.parent_root]

    total_active_balance = get_total_active_balance(balance_source)
    proposer_score = compute_proposer_score(balance_source)
    maximum_support = estimate_committee_weight_between_slots(
        total_active_balance, Slot(parent_block.slot + 1), Slot(current_slot - 1)
    )
    support_discount = get_support_discount(store, balance_source, block_root)
    adversarial_weight = get_adversarial_weight(store, balance_source, block_root)

    # The subtraction is safe as maximum_support is always greater than support_discount
    return (maximum_support + proposer_score - support_discount) // 2 + adversarial_weight
```

##### `is_one_confirmed`

*Notes:*

This function checks if a single block is LMD-GHOST safe by computing LMD-GHOST
safety indicator and comparing its value to the safety threshold.

At a high level the computation checks whether the actual score of the block
outweighs potential score of any block conflicting with it cosidering total
weight of the committees and maximal adversarial weight.

If this check passes the block is deemed LMD-GHOST safe, but it's not enough to
say that the block will remain canonical. To ensure the latter, each ancestor of
the block would also have to pass this check.

More details on this check can be found in the
[paper](https://arxiv.org/abs/2405.00549).

```python
def is_one_confirmed(store: Store, balance_source: BeaconState, block_root: Root) -> bool:
    """
    Return ``True`` if and only if the block is LMD-GHOST safe.
    """
    support = get_attestation_score(store, block_root, balance_source)
    safety_threshold = compute_safety_threshold(store, block_root, balance_source)

    return support > safety_threshold
```

##### `is_confirmed_chain_safe`

*Notes*:

This function should be called at the start of each epoch to ensure that the
confirmed chain starting from
`store.current_epoch_observed_justified_checkpoint.root` remains LMD-GHOST safe.

This check relaxes synchrony assumption by allowing GST to start from the
beginning of the previous slot. If such check was not run, GST start would have
to be assumed from the time of the first run of the algorithm which could happen
big number of epochs ago.

```python
def is_confirmed_chain_safe(store: Store, confirmed_root: Root) -> bool:
    """
    Return ``True`` if and only if all blocks of the confirmed chain
    starting from current_epoch_observed_justified_checkpoint are LMD-GHOST safe.
    """

    # Check if the confirmed_root is descendant of current_epoch_observed_justified_checkpoint.
    if not is_ancestor(
        store, confirmed_root, store.current_epoch_observed_justified_checkpoint.root
    ):
        return False

    current_epoch = get_current_store_epoch(store)
    if store.current_epoch_observed_justified_checkpoint.epoch + 1 >= current_epoch:
        # Exclude the justified checkpoint block if it is from the previous epoch
        # as then this block will always be canonical in this case.
        start_root_exclusive = store.current_epoch_observed_justified_checkpoint.root
    else:
        # Limit reconfirmation to the first block of the previous epoch
        # as if it's successful, reconfirmation of the ancestors is implied.
        ancestor_at_previous_epoch_start = get_ancestor(
            store, confirmed_root, compute_start_slot_at_epoch(Epoch(current_epoch - 1))
        )
        if get_block_epoch(store, ancestor_at_previous_epoch_start) + 1 == current_epoch:
            # The parent of the first block of the previous epoch.
            start_root_exclusive = store.blocks[ancestor_at_previous_epoch_start].parent_root
        else:
            # The last block of the epoch before the previous one.
            start_root_exclusive = ancestor_at_previous_epoch_start

    # Run is_one_confirmed for each block in the confirmed chain with the previous epoch balance source.
    chain_roots = get_ancestor_roots(store, confirmed_root, start_root_exclusive)
    return all(
        is_one_confirmed(store, get_previous_balance_source(store), root) for root in chain_roots
    )
```

#### FFG helpers

##### `get_current_target_score`

*Notes:*

This function uses LMD-GHOST votes to estimate the FFG support of the current
epoch target. Due to the way the computation happens, it MUST be used no later
than the end of the current epoch.

```python
def get_current_target_score(store: Store) -> Gwei:
    """
    Return the estimate of FFG support of the current epoch target by using LMD-GHOST votes.
    """
    target = get_current_target(store)
    state = get_pulled_up_head_state(store)
    unslashed_and_active_indices = [
        i
        for i in get_active_validator_indices(state, get_current_epoch(state))
        if not state.validators[i].slashed
    ]
    return Gwei(
        sum(
            state.validators[i].effective_balance
            for i in unslashed_and_active_indices
            if (
                i in store.latest_messages
                and i not in store.equivocating_indices
                and target
                == get_checkpoint_for_block(
                    store,
                    store.latest_messages[i].root,
                    get_latest_message_epoch(store.latest_messages[i]),
                )
            )
        )
    )
```

##### `compute_honest_ffg_support_for_current_target`

*Notes*:

This function computes honest FFG support of the current epoch target by
assuming `CONFIRMATION_BYZANTINE_THRESHOLD` and network synchrony, and taking
into account votes supporting the target that have been received till now.

```python
def compute_honest_ffg_support_for_current_target(store: Store) -> Gwei:
    """
    Compute honest FFG support of the current epoch target.
    """
    current_slot = get_current_slot(store)
    current_epoch = compute_epoch_at_slot(current_slot)
    balance_source = get_pulled_up_head_state(store)
    total_active_balance = get_total_active_balance(balance_source)

    # Compute FFG support for the target
    ffg_support_for_checkpoint = get_current_target_score(store)

    # Compute total FFG weight till current slot exclusive
    ffg_weight_till_now = estimate_committee_weight_between_slots(
        total_active_balance, compute_start_slot_at_epoch(current_epoch), Slot(current_slot - 1)
    )

    # Compute remaining honest FFG weight
    remaining_ffg_weight = total_active_balance - ffg_weight_till_now
    remaining_honest_ffg_weight = Gwei(
        remaining_ffg_weight // 100 * (100 - CONFIRMATION_BYZANTINE_THRESHOLD)
    )

    # Compute potential adversarial weight
    adversarial_weight = compute_adversarial_weight(
        store, balance_source, compute_start_slot_at_epoch(current_epoch), Slot(current_slot - 1)
    )

    # Compute min honest FFG support
    min_honest_ffg_support = ffg_support_for_checkpoint - min(
        adversarial_weight, ffg_support_for_checkpoint
    )

    return Gwei(min_honest_ffg_support + remaining_honest_ffg_weight)
```

##### `will_no_conflicting_checkpoint_be_justified`

*Note:* This function assumes that all honest validators will be voting in
support of the current epoch target starting from the current moment in time.

```python
def will_no_conflicting_checkpoint_be_justified(store: Store) -> bool:
    """
    Return ``True`` if and only if no checkpoint conflicting with the current target can ever be justified.
    """

    # If the target is unrealized justified then no conflicting checkpoint can be justified.
    if get_current_target(store) == store.unrealized_justified_checkpoint:
        return True

    state = get_pulled_up_head_state(store)
    total_active_balance = get_total_active_balance(state)
    honest_ffg_support = compute_honest_ffg_support_for_current_target(store)
    return 3 * honest_ffg_support >= 1 * total_active_balance
```

##### `will_current_target_be_justified`

*Note:* This function assumes that all honest validators will be voting in
support of the current epoch target starting from the current moment in time.

```python
def will_current_target_be_justified(store: Store) -> bool:
    """
    Return ``True`` if and only if the current target will eventually be justified.
    """
    state = get_pulled_up_head_state(store)
    total_active_balance = get_total_active_balance(state)
    honest_ffg_support = compute_honest_ffg_support_for_current_target(store)
    return 3 * honest_ffg_support >= 2 * total_active_balance
```

#### `update_fast_confirmation_variables`

*Note:* This function updates variables used by the fast confirmation rule.

```python
def update_fast_confirmation_variables(store: Store) -> None:
    # Update prev and curr slot head.
    store.previous_slot_head = store.current_slot_head
    store.current_slot_head = get_head(store)

    # Update greatest unrealized justified checkpoint at the last slot of an epoch.
    if is_start_slot_at_epoch(Slot(get_current_slot(store) + 1)):
        store.previous_epoch_greatest_unrealized_checkpoint = store.unrealized_justified_checkpoint

    # Update observed justified checkpoints at the start of an epoch.
    if is_start_slot_at_epoch(get_current_slot(store)):
        store.previous_epoch_observed_justified_checkpoint = (
            store.current_epoch_observed_justified_checkpoint
        )
        store.current_epoch_observed_justified_checkpoint = (
            store.previous_epoch_greatest_unrealized_checkpoint
        )
```

#### `find_latest_confirmed_descendant`

*Notes*:

This function examines canonical chain blocks starting from
`latest_confirmed_root` and returns the most recent block that satisfies FCR
conditions:

1. Each block in its chain is LMD-GHOST safe, i.e. will be the winner of the
   LMD-GHOST fork choice rule starting from the current moment in time.
2. The block will not be filtered out during the current and the next epochs.

Assuming synchrony and `CONFIRMATION_BYZANTINE_THRESHOLD` value, the above
criteria ensures that the block returned by this function will remain canonical
in the view of all honest validators starting from the current moment in time.

This function works correctly only if the `latest_confirmed_root` belongs to the
canonical chain and is either from the previous or from the current epoch.

```python
def find_latest_confirmed_descendant(store: Store, latest_confirmed_root: Root) -> Root:
    """
    Return the most recent confirmed block in the suffix of the canonical chain
    starting from ``latest_confirmed_root``.
    """
    head = get_head(store)
    current_epoch = get_current_store_epoch(store)
    confirmed_root = latest_confirmed_root

    if (
        get_block_epoch(store, confirmed_root) + 1 == current_epoch
        and get_voting_source(store, store.previous_slot_head).epoch + 2 >= current_epoch
        and (
            is_start_slot_at_epoch(get_current_slot(store))
            or (
                will_no_conflicting_checkpoint_be_justified(store)
                and (
                    store.unrealized_justifications[store.previous_slot_head].epoch + 1
                    >= current_epoch
                    or store.unrealized_justifications[head].epoch + 1 >= current_epoch
                )
            )
        )
    ):
        # Get suffix of the canonical chain
        canonical_roots = get_ancestor_roots(store, head, confirmed_root)

        # Starting with the child of the latest_confirmed_root
        # move towards the head in attempt to advance confirmed block
        # and stop when the first unconfirmed descendant is encountered
        for block_root in canonical_roots:
            block_epoch = get_block_epoch(store, block_root)

            # If the current epoch is reached, exit the loop
            # as this code is meant to confirm blocks from the previous epoch
            if block_epoch == current_epoch:
                break

            # The algorithm can only rely on the previous head
            # if it is a descendant of the block that is attempted to be confirmed
            if not is_ancestor(store, store.previous_slot_head, block_root):
                break

            if not is_one_confirmed(store, get_current_balance_source(store), block_root):
                break

            confirmed_root = block_root

    if (
        is_start_slot_at_epoch(get_current_slot(store))
        or store.unrealized_justifications[head].epoch + 1 >= current_epoch
    ):
        # Get suffix of the canonical chain
        canonical_roots = get_ancestor_roots(store, head, confirmed_root)

        tentative_confirmed_root = confirmed_root

        for block_root in canonical_roots:
            block_epoch = get_block_epoch(store, block_root)
            tentative_confirmed_epoch = get_block_epoch(store, tentative_confirmed_root)

            # The following condition can only be true the first time
            # the algorithm advances to a block from the current epoch
            if block_epoch > tentative_confirmed_epoch:
                # To confirm blocks from the current epoch ensure that
                # current epoch target will be justified
                if not will_current_target_be_justified(store):
                    break

            if not is_one_confirmed(store, get_current_balance_source(store), block_root):
                break

            tentative_confirmed_root = block_root

        # The tentative_confirmed_root can only be confirmed
        # if it is for sure not going to be reorged out in either the current or next epoch.
        if get_block_epoch(store, tentative_confirmed_root) == current_epoch or (
            get_voting_source(store, tentative_confirmed_root).epoch + 2 >= current_epoch
            and (
                is_start_slot_at_epoch(get_current_slot(store))
                or will_no_conflicting_checkpoint_be_justified(store)
            )
        ):
            confirmed_root = tentative_confirmed_root

    return confirmed_root
```

#### `get_latest_confirmed`

*Notes:*

This function executes the FCR algorithm which takes the following sequence of
actions:

1. Check if the `store.confirmed_root` belongs to the canonical chain and is not
   older than the previous epoch.
2. Check if the confirmed chain starting from the
   `store.current_epoch_observed_justified_checkpoint` can be re-confirmed at
   the start of the current epoch which resets GST to the start of the current
   epoch.
3. If any of the above checks fail, set `store.confirmed_root` to the
   `store.finalized_checkpoint.root`. Either of the above conditions signify
   that FCR assumptions (at least synchrony) are broken and the confirmed block
   might not be safe.
4. Restart the confirmation chain by setting `store.confirmed_root` to
   `store.current_epoch_observed_justified_checkpoint.root` if the restart
   conditions are met. Under synchrony, such a checkpoint is for sure now the
   greatest justified checkpoint in the view of any honest validator and,
   therefore, any honest validator will keep voting for it for the entire epoch.
5. Attempt to advance the `store.confirmed_root` by calling
   `find_latest_confirmed_descendant`.

```python
def get_latest_confirmed(store: Store) -> Root:
    """
    Return the most recent confirmed block by executing the FCR algorithm.
    """
    confirmed_root = store.confirmed_root
    current_epoch = get_current_store_epoch(store)

    # Revert to finalized block if either of the following is true:
    # 1) the latest confirmed block's epoch is older than the previous epoch,
    # 2) the latest confirmed block doesn't belong to the canonical chain,
    # 3) the confirmed chain starting from the current epoch observed justified checkpoint
    #    cannot be re-confirmed at the start of the current epoch.
    head = get_head(store)
    if (
        get_block_epoch(store, confirmed_root) + 1 < current_epoch
        or not is_ancestor(store, head, confirmed_root)
        or (
            is_start_slot_at_epoch(get_current_slot(store))
            and not is_confirmed_chain_safe(store, confirmed_root)
        )
    ):
        confirmed_root = store.finalized_checkpoint.root

    # Restart the confirmation chain if each of the following conditions are true:
    # 1) it is the start of the current epoch,
    # 2) epoch of store.current_epoch_observed_justified_checkpoint equals to the previous epoch,
    # 3) store.current_epoch_observed_justified_checkpoint equals to unrealized justification of the head,
    # 4) confirmed block is older than the block of store.current_epoch_observed_justified_checkpoint.
    if (
        is_start_slot_at_epoch(get_current_slot(store))
        and store.current_epoch_observed_justified_checkpoint.epoch + 1 == current_epoch
        and store.current_epoch_observed_justified_checkpoint
        == store.unrealized_justifications[head]
        and get_block_slot(store, confirmed_root)
        < get_block_slot(store, store.current_epoch_observed_justified_checkpoint.root)
    ):
        confirmed_root = store.current_epoch_observed_justified_checkpoint.root

    # Attempt to further advance the latest confirmed block.
    if get_block_epoch(store, confirmed_root) + 1 >= current_epoch:
        return find_latest_confirmed_descendant(store, confirmed_root)
    else:
        return confirmed_root
```

### Handlers

#### `on_fast_confirmation`

*Notes:*

This handler calls `update_fast_confirmation_variables` and then
`get_latest_confirmed` to update `store.confirmed_root` with the response of
that call.

Implementations MUST strictly follow the call sequence:

1. `update_fast_confirmation_variables`
2. `get_latest_confirmed`

Implementations MUST call `update_fast_confirmation_variables` in the first part
of a slot after attestations from past slots have been applied and before
`get_attestation_due_ms(epoch)` milliseconds has transpired since the start of
the slot.

Implementations MAY call `update_fast_confirmation_variables` after a valid
block from the expected block proposer for the assigned `slot` has been received
and processed if this happens before `get_attestation_due_ms(epoch)`
milliseconds has transpired since the start of the `slot`.

Implementations MAY call `get_latest_confirmed` at any point in time throughout
a slot.

```python
def on_fast_confirmation(store: Store) -> None:
    update_fast_confirmation_variables(store)
    store.confirmed_root = get_latest_confirmed(store)
```
