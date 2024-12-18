# Fork Choice -- Confirmation Rule

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Confirmation Rule](#confirmation-rule)
  - [Helper Functions](#helper-functions)
    - [Modified `get_ffg_support`](#modified-get_ffg_support)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Confirmation Rule

### Helper Functions

#### Modified `get_ffg_support`

```python
def get_ffg_support(store: Store, checkpoint: Root) -> Gwei:
    """
    Returns the total weight supporting the checkpoint in the block's chain at block's epoch.
    """
    current_epoch = get_current_store_epoch(store)

    # This function is only applicable to current and previous epoch blocks
    assert current_epoch in [checkpoint.epoch, checkpoint.epoch + 1]

    if checkpoint not in store.checkpoint_states:
        return Gwei(0)

    checkpoint_state = store.checkpoint_states[checkpoint]

    leaf_roots = [
        leaf for leaf in get_leaf_block_roots(store, checkpoint.root)
        if get_checkpoint_block(store, leaf, checkpoint.epoch) == checkpoint.root]

    active_checkpoint_indices = get_active_validator_indices(checkpoint_state, checkpoint.epoch)
    participating_indices_from_blocks = set().union(*[
        get_epoch_participating_indices(
            store.block_states[root],
            active_checkpoint_indices,
            checkpoint.epoch == current_epoch
        )
        for root in leaf_roots
    ])

    participating_indices_from_lmds = set([
        i
        for i in store.latest_messages
        if get_checkpoint_block(
            store, store.latest_messages[i].root,
            compute_epoch_at_slot(store.latest_messages[i].slot),  # Modified in EIP7732
        ) == checkpoint.root
    ])

    return get_total_balance(checkpoint_state, participating_indices_from_blocks.union(participating_indices_from_lmds))
```