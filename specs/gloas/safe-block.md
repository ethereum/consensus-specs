# Gloas -- Safe Block

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `get_safe_execution_block_hash`](#modified-get_safe_execution_block_hash)

<!-- mdformat-toc end -->

## Introduction

This document is an extension of
[Bellatrix -- Safe Block](../bellatrix/safe-block.md). All behaviors and
definitions defined in this document, and documents it extends, carry over
unless explicitly noted or overridden.

This document describes an algorithm to find a safe block. Under honest majority
and certain network synchronicity assumptions there exists a block that is safe
from re-orgs. Normally this block is pretty close to the head of canonical chain
which makes it valuable to expose a safe block to users.

## Helpers

### Modified `get_safe_execution_block_hash`

```python
def get_safe_execution_block_hash(fcr_store: FastConfirmationStore) -> Hash32:
    safe_block_root = fcr_store.confirmed_root
    safe_block = fcr_store.store.blocks[safe_block_root]

    # [Modified in Gloas]
    if compute_epoch_at_slot(safe_block.slot) >= GLOAS_FORK_EPOCH:
        safe_block_bid = safe_block.body.signed_execution_payload_bid.message
        return safe_block_bid.parent_block_hash
    elif compute_epoch_at_slot(safe_block.slot) >= BELLATRIX_FORK_EPOCH:
        return safe_block.body.execution_payload.block_hash
    else:
        # No safe block is available yet
        return Hash32()
```
