# Gloas -- Fast Confirmation

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Fast Confirmation Rule](#fast-confirmation-rule)
  - [Helpers](#helpers)
    - [Modified `get_node_for_root`](#modified-get_node_for_root)
  - [LMD-GHOST helpers](#lmd-ghost-helpers)
    - [Modified `compute_empty_slot_support_discount`](#modified-compute_empty_slot_support_discount)
- [Safe execution block](#safe-execution-block)
  - [Modified `get_safe_execution_block_hash`](#modified-get_safe_execution_block_hash)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fast confirmation rule specification
accompanying Gloas.

## Fast Confirmation Rule

### Helpers

#### Modified `get_node_for_root`

```python
def get_node_for_root(block_root: Root) -> ForkChoiceNode:
    # [Modified in Gloas:EIP7732]
    return ForkChoiceNode(root=block_root, payload_status=PAYLOAD_STATUS_PENDING)
```

### LMD-GHOST helpers

#### Modified `compute_empty_slot_support_discount`

*Note*: This function has been modified to count direct support for the parent
node, whether it is full or empty, *together* with support for the pending node
of the parent beacon block.

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
    # No empty slot
    if parent_block.slot + 1 == block.slot:
        return Gwei(0)

    # Discount votes supporting the parent block if they are from the committees of empty slots
    # [Modified in Gloas:EIP7732]
    parent_node = get_ancestor(store, get_node_for_root(block_root), parent_block.slot)
    parent_pending_node = get_node_for_root(block.parent_root)
    parent_support_in_empty_slots = get_node_support_between_slots(
        store,
        balance_source,
        # [Modified in Gloas:EIP7732]
        {parent_pending_node, parent_node},
        parent_block.slot + 1,
        block.slot - 1,
    )
    # Adversarial weight is not discounted
    adversarial_weight = compute_adversarial_weight(
        store, balance_source, parent_block.slot + 1, block.slot - 1
    )
    if parent_support_in_empty_slots > adversarial_weight:
        return parent_support_in_empty_slots - adversarial_weight
    else:
        return Gwei(0)
```

## Safe execution block

### Modified `get_safe_execution_block_hash`

*Note*: In Gloas, only the parent payload of a confirmed beacon block is safe.

```python
def get_safe_execution_block_hash(fcr_store: FastConfirmationStore) -> Hash32:
    safe_block = fcr_store.store.blocks[fcr_store.confirmed_root]
    # [Modified in Gloas:EIP7732]
    return safe_block.body.signed_execution_payload_bid.message.parent_block_hash
```
