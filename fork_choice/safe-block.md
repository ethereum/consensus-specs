# Fork Choice -- Safe Block

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [`get_safe_execution_block_hash`](#get_safe_execution_block_hash)

<!-- mdformat-toc end -->

## Introduction

Under honest majority and certain network synchronicity assumptions there exists
a block that is safe from re-orgs. Normally this block is pretty close to the
head of canonical chain which makes it valuable to expose a safe block to users.

This section describes an algorithm to find a safe block.

## `get_safe_execution_block_hash`

*Note*: `retrieve_fast_confirmed_root()` is an implementation dependent function
that retrieves the most recent `confirmed_root` determined by the
[Fast Confirmation](../specs/phase0/fast-confirmation.md) algorithm.

```python
def get_safe_execution_block_hash(store: Store) -> Hash32:
    safe_block_root = retrieve_fast_confirmed_root()
    safe_block = store.blocks[safe_block_root]

    # Return Hash32() if no payload is yet justified
    if compute_epoch_at_slot(safe_block.slot) >= BELLATRIX_FORK_EPOCH:
        return safe_block.body.execution_payload.block_hash
    else:
        return Hash32()
```

*Note*: This helper uses beacon block container extended in
[Bellatrix](../specs/bellatrix/beacon-chain.md).
