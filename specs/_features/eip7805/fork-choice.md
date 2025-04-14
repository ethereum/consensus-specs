# EIP-7805 -- Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
- [Fork choice](#fork-choice)
  - [Helpers](#helpers)
    - [Modified `Store`](#modified-store)
    - [New `validate_inclusion_lists`](#new-validate_inclusion_lists)
    - [New `get_attester_head`](#new-get_attester_head)
      - [Modified `get_proposer_head`](#modified-get_proposer_head)
    - [New `on_inclusion_list`](#new-on_inclusion_list)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice accompanying the EIP-7805 upgrade.

## Configuration

### Time parameters

| Name                   | Value                           |  Unit   | Duration  |
| ---------------------- | ------------------------------- | :-----: | :-------: |
| `VIEW_FREEZE_DEADLINE` | `SECONDS_PER_SLOT * 2 // 3 + 1` | seconds | 9 seconds |

## Fork choice

### Helpers

#### Modified `Store`

*Note*: `Store` is modified to track the seen inclusion lists and inclusion list equivocators.

```python
@dataclass
class Store(object):
    time: uint64
    genesis_time: uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    unrealized_justified_checkpoint: Checkpoint
    unrealized_finalized_checkpoint: Checkpoint
    proposer_boost_root: Root
    equivocating_indices: Set[ValidatorIndex]
    blocks: Dict[Root, BeaconBlock] = field(default_factory=dict)
    block_states: Dict[Root, BeaconState] = field(default_factory=dict)
    block_timeliness: Dict[Root, boolean] = field(default_factory=dict)
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
    unrealized_justifications: Dict[Root, Checkpoint] = field(default_factory=dict)
    # [New in EIP-7805]
    inclusion_lists: Dict[Tuple[Slot, Root], Set[InclusionList]] = field(default_factory=dict)
    inclusion_list_equivocators: Dict[Tuple[Slot, Root], Set[ValidatorIndex]] = field(default_factory=dict)
    unsatisfied_inclusion_list_blocks: Set[Root] = field(default_factory=Set)
```

#### New `validate_inclusion_lists`

```python
def validate_inclusion_lists(store: Store,
                             inclusion_list_transactions: Sequence[Transaction],
                             execution_payload: ExecutionPayload) -> None:
    """
    The ``execution_payload`` satisfies ``inclusion_list_transactions`` validity conditions either
    when all transactions are present in payload or when any missing transactions are found to be
    invalid when appended to the end of the payload unless the block is full.
    """
    # pylint: disable=unused-argument

    # Verify inclusion list transactions are present in the execution payload
    contains_all_txs = all(tx in execution_payload.transactions for tx in inclusion_list_transactions)
    if contains_all_txs:
        return

    # TODO: check remaining validity conditions
```

#### New `get_attester_head`

```python
def get_attester_head(store: Store, head_root: Root) -> Root:
    head_block = store.blocks[head_root]

    if head_root in store.unsatisfied_inclusion_list_blocks:
        return head_block.parent_root
    return head_root

```

##### Modified `get_proposer_head`

The implementation of `get_proposer_head` is modified to also account for `store.unsatisfied_inclusion_list_blocks`.

```python
def get_proposer_head(store: Store, head_root: Root, slot: Slot) -> Root:
    head_block = store.blocks[head_root]
    parent_root = head_block.parent_root
    parent_block = store.blocks[parent_root]

    # Only re-org the head block if it arrived later than the attestation deadline.
    head_late = is_head_late(store, head_root)

    # Do not re-org on an epoch boundary where the proposer shuffling could change.
    shuffling_stable = is_shuffling_stable(slot)

    # Ensure that the FFG information of the new head will be competitive with the current head.
    ffg_competitive = is_ffg_competitive(store, head_root, parent_root)

    # Do not re-org if the chain is not finalizing with acceptable frequency.
    finalization_ok = is_finalization_ok(store, slot)

    # Only re-org if we are proposing on-time.
    proposing_on_time = is_proposing_on_time(store)

    # Only re-org a single slot at most.
    parent_slot_ok = parent_block.slot + 1 == head_block.slot
    current_time_ok = head_block.slot + 1 == slot
    single_slot_reorg = parent_slot_ok and current_time_ok

    # Check that the head has few enough votes to be overpowered by our proposer boost.
    assert store.proposer_boost_root != head_root  # ensure boost has worn off
    head_weak = is_head_weak(store, head_root)

    # Check that the missing votes are assigned to the parent and not being hoarded.
    parent_strong = is_parent_strong(store, parent_root)

    reorg_prerequisites = all([shuffling_stable, ffg_competitive, finalization_ok,
                               proposing_on_time, single_slot_reorg, head_weak, parent_strong])

    # Check that the head block is in the unsatisfied inclusion list blocks
    inclusion_list_not_satisfied = head_root in store.unsatisfied_inclusion_list_blocks  # [New in EIP-7805]

    if reorg_prerequisites and (head_late or inclusion_list_not_satisfied):
        return parent_root
    else:
        return head_root
```

#### New `on_inclusion_list`

`on_inclusion_list` is called to import `signed_inclusion_list` to the fork choice store.

```python
def on_inclusion_list(
        store: Store,
        state: BeaconState,
        signed_inclusion_list: SignedInclusionList,
        inclusion_list_committee: Vector[ValidatorIndex, INCLUSION_LIST_COMMITTEE_SIZE]) -> None:
    """
    Verify the inclusion list and import it into the fork choice store. If there exists more than
    one inclusion list in the store with the same slot and validator index, add the equivocator to
    the ``inclusion_list_equivocators`` cache. Otherwise, add the inclusion list to the
    ``inclusion_lists` cache.
    """
    message = signed_inclusion_list.message

    # Verify inclusion list slot is either from the current or previous slot
    assert get_current_slot(store) in [message.slot, message.slot + 1]

    time_into_slot = (store.time - store.genesis_time) % SECONDS_PER_SLOT
    is_before_attesting_interval = time_into_slot < SECONDS_PER_SLOT // INTERVALS_PER_SLOT

    # If the inclusion list is from the previous slot, ignore it if already past the attestation deadline
    if get_current_slot(store) == message.slot + 1:
        assert is_before_attesting_interval

    # Sanity check that the given `inclusion_list_committee` matches the root in the inclusion list
    root = message.inclusion_list_committee_root
    assert hash_tree_root(inclusion_list_committee) == root

    # Verify inclusion list validator is part of the committee
    validator_index = message.validator_index
    assert validator_index in inclusion_list_committee

    # Verify inclusion list signature
    assert is_valid_inclusion_list_signature(state, signed_inclusion_list)

    is_before_freeze_deadline = get_current_slot(store) == message.slot and time_into_slot < VIEW_FREEZE_DEADLINE

    # Do not process inclusion lists from known equivocators
    if validator_index not in store.inclusion_list_equivocators[(message.slot, root)]:
        if validator_index in [il.validator_index for il in store.inclusion_lists[(message.slot, root)]]:
            validator_inclusion_list = [
                il for il in store.inclusion_lists[(message.slot, root)]
                if il.validator_index == validator_index
            ][0]
            if validator_inclusion_list != message:
                # We have equivocation evidence for `validator_index`, record it as equivocator
                store.inclusion_list_equivocators[(message.slot, root)].add(validator_index)
        # This inclusion list is not an equivocation. Store it if prior to the view freeze deadline
        elif is_before_freeze_deadline:
            store.inclusion_lists[(message.slot, root)].add(message)
```
