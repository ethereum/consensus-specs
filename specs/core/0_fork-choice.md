# Ethereum 2.0 Phase 0 -- Beacon Chain Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->

- [Ethereum 2.0 Phase 0 -- Beacon Chain Fork Choice](#ethereum-20-phase-0----beacon-chain-fork-choice)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Prerequisites](#prerequisites)
    - [Configuration](#configuration)
        - [Time parameters](#time-parameters)
    - [Beacon chain processing](#beacon-chain-processing)
        - [Beacon chain fork choice rule](#beacon-chain-fork-choice-rule)
    - [Implementation notes](#implementation-notes)
        - [Justification and finality at genesis](#justification-and-finality-at-genesis)

<!-- /TOC -->

## Introduction

This document represents the specification for the beacon chain fork choice rule, part of Ethereum 2.0 Phase 0.

## Prerequisites

All terminology, constants, functions, and protocol mechanics defined in the [Phase 0 -- The Beacon Chain](./0_beacon-chain.md) doc are requisite for this document and used throughout. Please see the Phase 0 doc before continuing and use as a reference throughout.

## Configuration

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SECONDS_PER_SLOT` | `6` | seconds | 6 seconds |

## Beacon chain processing

Processing the beacon chain is similar to processing the Ethereum 1.0 chain. Clients download and process blocks and maintain a view of what is the current "canonical chain", terminating at the current "head". For a beacon block, `block`, to be processed by a node, the following conditions must be met:

* The parent block with root `block.parent_root` has been processed and accepted.
* An Ethereum 1.0 block pointed to by the `state.eth1_data.block_hash` has been processed and accepted.
* The node's Unix time is greater than or equal to `state.genesis_time + block.slot * SECONDS_PER_SLOT`.

*Note*: Leap seconds mean that slots will occasionally last `SECONDS_PER_SLOT + 1` or `SECONDS_PER_SLOT - 1` seconds, possibly several times a year.

*Note*: Nodes needs to have a clock that is roughly (i.e. within `SECONDS_PER_SLOT` seconds) synchronized with the other nodes.

### Beacon chain fork choice rule

The beacon chain fork choice rule is a hybrid that combines justification and finality with Latest Message Driven (LMD) Greediest Heaviest Observed SubTree (GHOST). At any point in time, a validator `v` subjectively calculates the beacon chain head as follows.

* Abstractly define `Store` as the type of storage object for the chain data, and let `store` be the set of attestations and blocks that the validator `v` has observed and verified (in particular, block ancestors must be recursively verified). Attestations not yet included in any chain are still included in `store`.
* Let `finalized_head` be the finalized block with the highest epoch. (A block `B` is finalized if there is a descendant of `B` in `store`, the processing of which sets `B` as finalized.)
* Let `justified_head` be the descendant of `finalized_head` with the highest epoch that has been justified for at least 1 epoch. (A block `B` is justified if there is a descendant of `B` in `store` the processing of which sets `B` as justified.) If no such descendant exists, set `justified_head` to `finalized_head`.
* Let `get_ancestor(store: Store, block: BeaconBlock, slot: Slot) -> BeaconBlock` be the ancestor of `block` with slot number `slot`. The `get_ancestor` function can be defined recursively as:

```python
def get_ancestor(store: Store, block: BeaconBlock, slot: Slot) -> BeaconBlock:
    """
    Get the ancestor of ``block`` with slot number ``slot``; return ``None`` if not found.
    """
    if block.slot == slot:
        return block
    elif block.slot < slot:
        return None
    else:
        return get_ancestor(store, store.get_parent(block), slot)
```

* Let `get_latest_attestation(store: Store, index: ValidatorIndex) -> Attestation` be the attestation with the highest slot number in `store` from the validator with the given `index`. If several such attestations exist, use the one the validator `v` observed first.
* Let `get_attestation_target(store: Store, index: ValidatorIndex) -> BeaconBlock` be the target block in the attestation `get_latest_attestation(store, index)`.
* Let `get_children(store: Store, block: BeaconBlock) -> List[BeaconBlock]` return the child blocks of the given `block`.
* Let `justified_head_state` be the resulting `BeaconState` object from processing the chain up to the `justified_head`.
* The `head` is `lmd_ghost(store, justified_head_state, justified_head)` where the function `lmd_ghost` is defined below. Note that the implementation below is suboptimal; there are implementations that compute the head in time logarithmic in slot count.

```python
def lmd_ghost(store: Store, start_state: BeaconState, start_block: BeaconBlock) -> BeaconBlock:
    """
    Execute the LMD-GHOST algorithm to find the head ``BeaconBlock``.
    """
    validators = start_state.validators
    active_validator_indices = get_active_validator_indices(validators, slot_to_epoch(start_state.slot))
    attestation_targets = [(i, get_attestation_target(store, i)) for i in active_validator_indices]

    # Use the rounded-balance-with-hysteresis supplied by the protocol for fork
    # choice voting. This reduces the number of recomputations that need to be
    # made for optimized implementations that precompute and save data
    def get_vote_count(block: BeaconBlock) -> int:
        return sum(
            start_state.validators[validator_index].effective_balance
            for validator_index, target in attestation_targets
            if get_ancestor(store, target, block.slot) == block
        )

    head = start_block
    while 1:
        children = get_children(store, head)
        if len(children) == 0:
            return head
        # Ties broken by favoring block with lexicographically higher root
        head = max(children, key=lambda x: (get_vote_count(x), hash_tree_root(x)))
```

## Implementation notes

### Justification and finality at genesis

During genesis, justification and finality root fields within the `BeaconState` reference `ZERO_HASH` rather than a known block. `ZERO_HASH` in `previous_justified_root`, `current_justified_root`, and `finalized_root` should be considered as an alias to the root of the genesis block.
