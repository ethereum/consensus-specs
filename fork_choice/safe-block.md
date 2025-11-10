# Fork Choice -- Safe Block

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [`get_safe_beacon_block_root`](#get_safe_beacon_block_root)
- [`get_safe_execution_block_hash`](#get_safe_execution_block_hash)

<!-- mdformat-toc end -->

## Introduction

Under honest majority and certain network synchronicity assumptions there exists
a block that is safe from re-orgs. Normally this block is pretty close to the
head of canonical chain which makes it valuable to expose a safe block to users.

This section describes an algorithm to find a safe block.

## `get_safe_beacon_block_root`

```python
def get_safe_beacon_block_root(store: Store) -> Root:
    # Use most recent justified block as a stopgap
    return store.justified_checkpoint.root
```

*Note*: Currently safe block algorithm simply returns
`store.justified_checkpoint.root` and is meant to be improved in the future.

## `get_safe_execution_block_hash`

```python
def get_safe_execution_block_hash(store: Store) -> Hash32:
    safe_block_root = get_safe_beacon_block_root(store)
    safe_block = store.blocks[safe_block_root]

    # Return Hash32() if no payload is yet justified
    if compute_epoch_at_slot(safe_block.slot) >= BELLATRIX_FORK_EPOCH:
        return safe_block.body.execution_payload.block_hash
    else:
        return Hash32()
```

*Note*: This helper uses beacon block container extended in
[Bellatrix](../specs/bellatrix/beacon-chain.md).
