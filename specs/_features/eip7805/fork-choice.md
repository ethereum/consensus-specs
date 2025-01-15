# EIP-7805 -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Fork choice](#fork-choice)
  - [Configuration](#configuration)
  - [Helpers](#helpers)
    - [Modified `Store`](#modified-store)
    - [New `validate_inclusion_lists`](#new-validate_inclusion_lists)
    - [New `get_attester_head`](#new-get_attester_head)
    - [New `on_inclusion_list`](#new-on_inclusion_list)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying the EIP-7805 upgrade.

## Fork choice

### Configuration

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `VIEW_FREEZE_DEADLINE` | `uint64(9)` | seconds | 9 seconds |

### Helpers

#### Modified `Store`

**Note:** `Store` is modified to track the seen inclusion lists and inclusion list equivocators.

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
    inclusion_lists: Dict[Tuple[Slot, Root], List[InclusionList]] = field(default_factory=dict)
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

    # Verify inclusion list is a valid length
    assert len(inclusion_list_transactions) <= MAX_TRANSACTIONS_PER_INCLUSION_LIST * INCLUSION_LIST_COMMITTEE_SIZE

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
            store.inclusion_lists[(message.slot, root)].append(message)
```


