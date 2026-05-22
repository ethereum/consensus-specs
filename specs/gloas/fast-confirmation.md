# Gloas -- Fast Confirmation

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Safe execution block](#safe-execution-block)
  - [`get_safe_execution_block_hash`](#get_safe_execution_block_hash)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fast confirmation accompanying Bellatrix.

## Safe execution block

### `get_safe_execution_block_hash`

*Note:* Starting with Gloas only the parent payload of a confirmed beacon block
can be deemed safe.

```python
def get_safe_execution_block_hash(fcr_store: FastConfirmationStore) -> Hash32:
    safe_block = fcr_store.store.blocks[fcr_store.confirmed_root]
    # [Modified in Gloas:EIP7732]
    safe_block_bid = safe_block.body.signed_execution_payload_bid.message
    return safe_block_bid.parent_block_hash
```
