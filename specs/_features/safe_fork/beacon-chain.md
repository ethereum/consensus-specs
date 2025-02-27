# Safe Fork -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
  - [Misc](#misc)
- [Epoch processing](#epoch-processing)
  - [Justification and finalization](#justification-and-finalization)
    - [Modified `weigh_justification_and_finalization`](#modified-weigh_justification_and_finalization)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification of the safe fork feature.

## Preset

### Misc

| Name | Value |
| - | - |
| `HIGH_JUSTIFICATION_RATE_EPOCHS` | `uint64(2**4)` (=16)  # (New in Safe Fork) |

## Epoch processing

### Justification and finalization

#### Modified `weigh_justification_and_finalization`

*Note*: This function is modified to increase the bar of justification for `HIGH_JUSTIFICATION_RATE_EPOCHS` after a Fork.

```python
def weigh_justification_and_finalization(state: BeaconState,
                                         total_active_balance: Gwei,
                                         previous_epoch_target_balance: Gwei,
                                         current_epoch_target_balance: Gwei) -> None:
    previous_epoch = get_previous_epoch(state)
    current_epoch = get_current_epoch(state)
    old_previous_justified_checkpoint = state.previous_justified_checkpoint
    old_current_justified_checkpoint = state.current_justified_checkpoint

    # Process justifications
    state.previous_justified_checkpoint = state.current_justified_checkpoint
    state.justification_bits[1:] = state.justification_bits[:JUSTIFICATION_BITS_LENGTH - 1]
    state.justification_bits[0] = 0b0

    # Modified in [Safe Fork]
    epochs_after_fork = current_epoch - state.fork.epoch + 1
    if epochs_after_fork > HIGH_JUSTIFICATION_RATE_EPOCHS:
        if previous_epoch_target_balance * 3 >= total_active_balance * 2:
            state.current_justified_checkpoint = Checkpoint(epoch=previous_epoch,
                                                          root=get_block_root(state, previous_epoch))
            state.justification_bits[1] = 0b1
        if current_epoch_target_balance * 3 >= total_active_balance * 2:
            state.current_justified_checkpoint = Checkpoint(epoch=current_epoch,
                                                          root=get_block_root(state, current_epoch))
            state.justification_bits[0] = 0b1
    else:
        if previous_epoch_target_balance * 20 >= total_active_balance * 19:
            state.current_justified_checkpoint = Checkpoint(epoch=previous_epoch,
                                                          root=get_block_root(state, previous_epoch))
            state.justification_bits[1] = 0b1
        if current_epoch_target_balance * 20 >= total_active_balance * 19:
            state.current_justified_checkpoint = Checkpoint(epoch=current_epoch,
                                                          root=get_block_root(state, current_epoch))
            state.justification_bits[0] = 0b1


    # Process finalizations
    bits = state.justification_bits
    # The 2nd/3rd/4th most recent epochs are justified, the 2nd using the 4th as source
    if all(bits[1:4]) and old_previous_justified_checkpoint.epoch + 3 == current_epoch:
        state.finalized_checkpoint = old_previous_justified_checkpoint
    # The 2nd/3rd most recent epochs are justified, the 2nd using the 3rd as source
    if all(bits[1:3]) and old_previous_justified_checkpoint.epoch + 2 == current_epoch:
        state.finalized_checkpoint = old_previous_justified_checkpoint
    # The 1st/2nd/3rd most recent epochs are justified, the 1st using the 3rd as source
    if all(bits[0:3]) and old_current_justified_checkpoint.epoch + 2 == current_epoch:
        state.finalized_checkpoint = old_current_justified_checkpoint
    # The 1st/2nd most recent epochs are justified, the 1st using the 2nd as source
    if all(bits[0:2]) and old_current_justified_checkpoint.epoch + 1 == current_epoch:
        state.finalized_checkpoint = old_current_justified_checkpoint
```
