# EIP-4788 -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [Modified `get_payload`](#modified-get_payload)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [ExecutionPayload](#executionpayload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement the EIP-4788 feature.

## Prerequisites

This document is an extension of the [Capella -- Honest Validator](../capella/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [Capella](../capella/beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Helpers

## Protocols

### `ExecutionEngine`

#### Modified `get_payload`

`get_payload` returns the upgraded EIP-4788 `ExecutionPayload` type.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayload

`ExecutionPayload`s are constructed as they were in Capella, except that the parent beacon block root is also supplied.

*Note*: In this section, `state` is the state of the slot for the block proposal _without_ the block yet applied.
That is, `state` is the `previous_state` processed through any empty slots up to the assigned slot using `process_slots(previous_state, slot)`.

*Note*: The only change made to `prepare_execution_payload` is to add the parent beacon block root as an additional
parameter to the `PayloadAttributes`.

```python
def prepare_execution_payload(state: BeaconState,
                              pow_chain: Dict[Hash32, PowBlock],
                              safe_block_hash: Hash32,
                              finalized_block_hash: Hash32,
                              suggested_fee_recipient: ExecutionAddress,
                              execution_engine: ExecutionEngine) -> Optional[PayloadId]:
    if not is_merge_transition_complete(state):
        is_terminal_block_hash_set = TERMINAL_BLOCK_HASH != Hash32()
        is_activation_epoch_reached = get_current_epoch(state) >= TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH
        if is_terminal_block_hash_set and not is_activation_epoch_reached:
            # Terminal block hash is set but activation epoch is not yet reached, no prepare payload call is needed
            return None

        terminal_pow_block = get_terminal_pow_block(pow_chain)
        if terminal_pow_block is None:
            # Pre-merge, no prepare payload call is needed
            return None
        # Signify merge via producing on top of the terminal PoW block
        parent_hash = terminal_pow_block.block_hash
    else:
        # Post-merge, normal payload
        parent_hash = state.latest_execution_payload_header.block_hash

    # Set the forkchoice head and initiate the payload build process
    payload_attributes = PayloadAttributes(
        timestamp=compute_timestamp_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        withdrawals=get_expected_withdrawals(state),
        parent_beacon_block_root=hash_tree_root(state.latest_block_header), # [New in EIP-4788]
        current_slot=state.slot,                                            # [New in EIP-4788]
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=parent_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```
