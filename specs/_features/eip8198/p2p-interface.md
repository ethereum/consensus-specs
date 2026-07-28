# EIP-8198 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in EIP-8198](#modifications-in-eip-8198)
  - [Helpers](#helpers)
    - [Modified `compute_time_at_slot_ms`](#modified-compute_time_at_slot_ms)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8198.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modifications in EIP-8198

### Helpers

#### Modified `compute_time_at_slot_ms`

*Note*: This is the millisecond counterpart of the modified
`compute_time_at_slot` (see the beacon chain document): slots after
`EIP8198_FORK_EPOCH` start at `SLOT_DURATION_MS_EIP8198` intervals from the fork
time, not at `SLOT_DURATION_MS` intervals from genesis. The gossip validation
gates `is_not_from_future_slot` and `is_within_slot_range` are defined in terms
of this function and inherit the corrected timeline without further changes.
Without this override, honest messages would be rejected as coming from the
future by an ever-growing margin after the fork.

```python
def compute_time_at_slot_ms(state: BeaconState, slot: Slot) -> Uint64:
    """
    Return the time in milliseconds at the start of the given slot.
    """
    slots_since_genesis = slot - GENESIS_SLOT
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return Uint64(state.genesis_time * 1000 + slots_since_genesis * SLOT_DURATION_MS)
    fork_slot = EIP8198_FORK_EPOCH * SLOTS_PER_EPOCH
    if slot < fork_slot:
        return Uint64(state.genesis_time * 1000 + slots_since_genesis * SLOT_DURATION_MS)
    time_before_fork_ms = fork_slot * SLOT_DURATION_MS
    time_after_fork_ms = (slots_since_genesis - fork_slot) * SLOT_DURATION_MS_EIP8198
    return Uint64(state.genesis_time * 1000 + time_before_fork_ms + time_after_fork_ms)
```
