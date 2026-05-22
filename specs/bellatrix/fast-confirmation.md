# Bellatrix -- Fast Confirmation

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Safe execution block](#safe-execution-block)
  - [`get_safe_execution_block_hash`](#get_safe_execution_block_hash)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fast confirmation accompanying Bellatrix.

## Safe execution block

With Bellatrix introducing execution payload, `get_safe_execution_block_hash`
function is introduced. This function returns the block hash of the payload
included into the most recent confirmed block. This block hash is communicated
to ExecutionEngine as a hash of a safe block.

### New `get_safe_execution_block_hash`

```python
def get_safe_execution_block_hash(fcr_store: FastConfirmationStore) -> Hash32:
    safe_block = fcr_store.store.blocks[fcr_store.confirmed_root]
    return safe_block.body.execution_payload.block_hash
```
