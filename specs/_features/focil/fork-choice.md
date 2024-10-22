# FOCIL -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `validate_inclusion_lists`](#new-validate_inclusion_lists)
  - [Modified `Store`](#modified-store)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying the FOCIL upgrade.

## Helpers

### New `validate_inclusion_lists`

```python
def validate_inclusion_lists(store: Store, inclusion_list_transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST * IL_COMMITTEE_SIZE], execution_payload: ExecutionPayload) -> bool:
    """
    Return ``True`` if and only if the input ``inclusion_list_transactions`` satifies validation, that to verify if the `execution_payload` satisfies `inclusion_list_transactions` validity conditions either when all transactions are present in payload or when any missing transactions are found to be invalid when appended to the end of the payload unless the block is full.
    """
    ...
```

### Modified `Store` 
**Note:** `Store` is modified to track the seen inclusion lists.

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
    inclusion_lists: Dict[Tuple[Slot, Root], List[InclusionList]] = field(default_factory=dict) # [New in FOCIL]
    inclusion_list_equivocators: Dict[Tuple[Slot, Root], Set[ValidatorIndex]] = field(default_factory=dict)# [New in FOCIL]


### New `on_inclusion_list`

`on_inclusion_list` is called to import `signed_inclusion_list` to the fork choice store.
```python
def on_inclusion_list(
        store: Store, signed_inclusion_list: SignedInclusionList) -> None:
    """
    ``on_inclusion_list`` verify the inclusion list before importing it to fork choice store.
    If there exists more than 1 inclusion list in store with the same slot and validator index, remove the original one.
    """
    message = signed_inclusion_list.message
    # Verify inclusion list slot is bounded to the current slot
    assert get_current_slot(store) == message.slot

    assert message.beacon_block_root in store.block_states
    # Get the inclusion list committee for this slot
    state = copy(store.block_states[message.beacon_block_root])
    if state.slot < message.slot:
        process_slots(state, message.slot)
    inclusion_list_committee = get_inclusion_list_committee(state, message.slot)

    # Verify inclusion list validator is part of the committee
    validator_index = message.validator_index
    assert validator_index.validator_index in inclusion_list_committee
   
    # Verify inclusion list signature
    assert is_valid_inclusion_list_signature(state, signed_inclusion_list)

    root = hash_tree_root(inclusion_list_committee)
    if validator_index not in inclusion_list_equivocators[(message.slot, root)]:
        if validator_index in [il.validator_index for il in inclusion_lists[(message.slot, root)]]
            il = [il for il in inclusion_lists[(message.slot, root)] if il.validator_index == validator_index][0]
            if not il == message:
                inclusion_list_equivocators[(message.slot, root)].add(validator_index)
        else:
            inclusion_lists[(message.slot, root)].append(message)
```


