# Bellatrix -- Safe Block

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `get_safe_execution_block_hash`](#new-get_safe_execution_block_hash)

<!-- mdformat-toc end -->

## Introduction

This document describes an algorithm to find a safe block. Under honest majority
and certain network synchronicity assumptions there exists a block that is safe
from re-orgs. Normally this block is pretty close to the head of canonical chain
which makes it valuable to expose a safe block to users.

## Helpers

### New `get_safe_execution_block_hash`

```python
def get_safe_execution_block_hash(fcr_store: FastConfirmationStore) -> Hash32:
    safe_block_root = fcr_store.confirmed_root
    safe_block = fcr_store.store.blocks[safe_block_root]

    if compute_epoch_at_slot(safe_block.slot) >= BELLATRIX_FORK_EPOCH:
        return safe_block.body.execution_payload.block_hash
    else:
        # No safe block is available yet
        return Hash32()
```
