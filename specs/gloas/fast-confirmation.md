# Gloas -- Fast Confirmation

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `get_node_for_root`](#modified-get_node_for_root)
- [Safe execution block](#safe-execution-block)
  - [Modified `get_safe_execution_block_hash`](#modified-get_safe_execution_block_hash)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fast confirmation rule specification
accompanying Gloas.

## Helpers

### Modified `get_node_for_root`

*Note*: This function is modified to return an extended `ForkChoiceNode`
structure with `PAYLOAD_STATUS_PENDING` payload status.

```python
def get_node_for_root(block_root: Root) -> ForkChoiceNode:
    # [Modified in Gloas:EIP7732]
    return ForkChoiceNode(root=block_root, payload_status=PAYLOAD_STATUS_PENDING)
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
