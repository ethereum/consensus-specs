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
**Note:** `Store` is modified to track the seen local inclusion lists.

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
    inclusion_lists: List[Transaction]  # [New in FOCIL]
    
#### Modified `get_head`
**Note:** `get_head` is modified to use `validate_inclusion_lists` as filter for head.

```python
def get_head(store: Store) -> Root:
    # Get filtered block tree that only includes viable branches
    blocks = get_filtered_block_tree(store)
    # Execute the LMD-GHOST fork choice
    head = store.justified_checkpoint.root
    while True:
        children = [
            root for root in blocks.keys()
            if blocks[root].parent_root == head
        ]
        if len(children) == 0:
            return head
        # Sort by latest attesting balance with ties broken lexicographically
        # Ties broken by favoring block with lexicographically higher root
        head = max(
            children, 
            key=lambda root: (get_weight(store, root), root) 
            0 if validate_inclusion_lists(store, store.inclusion_list_transactions, blocks[root].body.execution_payload) else root # [New in FOCIL]
)```


### New `on_local_inclusion_list`

`on_local_inclusion_list` is called to import `signed_local_inclusion_list` to the fork choice store.

```python
def on_inclusion_list(
        store: Store, signed_inclusion_list: SignedLocalInclusionList) -> None:
    """
    ``on_local_inclusion_list`` verify the inclusion list before import it to fork choice store.
    """
    message = signed_inclusion_list.message
    # Verify inclusion list slot is bouded to the current slot
    assert get_current_slot(store) != message.slot

    state = store.block_states[message.beacon_block_root]
    ilc = get_inclusion_list_committee(state, message.slot)
    # Verify inclusion list validator is part of the committee
    assert message.validator_index in ilc
   
    # Verify inclusion list signature
    assert is_valid_local_inclusion_list_signature(state, signed_inclusion_list) 

    if message.transaction not in store.inclusion_lists:
        store.inclusion_lists.append(message.transaction)    
```