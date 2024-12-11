# EIP7594 -- Honest Validator

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Block proposal](#block-proposal)
  - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
    - [Execution payload](#execution-payload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement EIP7594.

## Prerequisites

This document is an extension of the [Electra -- Honest Validator](../electra/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [EIP7594](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Block proposal

### Constructing the `BeaconBlockBody`

#### Execution payload

`prepare_execution_payload` is updated from the Electra specs.

*Note*: In this section, `state` is the state of the slot for the block proposal _without_ the block yet applied.
That is, `state` is the `previous_state` processed through any empty slots up to the assigned slot using `process_slots(previous_state, slot)`.

``python
def prepare_execution_payload(state: BeaconState,
                              safe_block_hash: Hash32,
                              finalized_block_hash: Hash32,
                              suggested_fee_recipient: ExecutionAddress,
                              execution_engine: ExecutionEngine) -> Optional[PayloadId]:
    # Verify consistency of the parent hash with respect to the previous execution payload header
    parent_hash = state.latest_execution_payload_header.block_hash

    # Set the forkchoice head and initiate the payload build process
    withdrawals, _ = get_expected_withdrawals(state)

    payload_attributes = PayloadAttributes(
        timestamp=compute_timestamp_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        withdrawals=withdrawals,
        parent_beacon_block_root=hash_tree_root(state.latest_block_header),
        target_blobs_per_block=TARGET_BLOBS_PER_BLOCK_EIP7594,  # [Modified in EIP7594]
        max_blobs_per_block=MAX_BLOBS_PER_BLOCK_EIP7594,  # [Modified in EIP7594]
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=parent_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```