# Capella -- Honest Validator

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
    - [`get_payload`](#get_payload)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [ExecutionPayload](#executionpayload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement the Capella upgrade.

## Prerequisites

This document is an extension of the [Bellatrix -- Honest Validator](../bellatrix/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [Capella](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Helpers

## Protocols

### `ExecutionEngine`

#### `get_payload`

`get_payload` returns the upgraded Capella `ExecutionPayload` type.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayload

`ExecutionPayload`s are constructed as they were in Bellatrix, except that the
expected withdrawals for the slot must be gathered from the `state` (utilizing the
helper `get_expected_withdrawals`) and passed into the `ExecutionEngine` within `prepare_execution_payload`.


```python
def get_expected_withdrawals(state: BeaconState) -> Sequence[Withdrawal]:
    num_withdrawals = min(MAX_WITHDRAWALS_PER_PAYLOAD, len(state.withdrawal_queue))
    return state.withdrawal_queue[:num_withdrawals]
```

*Note*: The only change made to `prepare_execution_payload` is to call
`get_expected_withdrawals()` to set the new `withdrawals` field of `PayloadAttributes`.

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
        withdrawals=get_expected_withdrawals(state),  # [New in Capella]
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=parent_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```
