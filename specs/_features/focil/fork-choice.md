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
    inclusion_lists: List[Transaction]  # [New in FOCIL


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

    state = store.block_states[message.beacon_block_root]
    ilc = get_inclusion_list_committee(state, message.slot)
    # Verify inclusion list validator is part of the committee
    assert message.validator_index in ilc
   
    # Verify inclusion list signature
    assert is_valid_inclusion_list_signature(state, signed_inclusion_list)

    # Check if an inclusion list with the same slot and validator index exists
    existing_inclusion_list = next(
        (il for il in store.inclusion_lists 
         if il.slot == message.slot and il.validator_index == message.validator_index),
        None
    )
    
    # If such an inclusion list exists, remove it
    if existing_inclusion_list:
        store.inclusion_lists.remove(existing_inclusion_list)
    else:
        # If no such inclusion list exists, add the new one
        store.inclusion_lists.append(message)
```