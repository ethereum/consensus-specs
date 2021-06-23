# Ethereum 2.0 The Merge

**Warning:** This document is currently based on [Phase 0](../phase0/validator.md) but will be rebased to [Altair](../altair/validator.md) once the latter is shipped.

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [`assemble_block`](#assemble_block)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Execution Payload](#execution-payload)
        - [`get_pow_chain_head`](#get_pow_chain_head)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement executable beacon chain proposal.

## Prerequisites

This document is an extension of the [Phase 0 -- Validator](../phase0/validator.md). All behaviors and definitions defined in the Phase 0 doc carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [The Merge](./beacon-chain.md) are requisite for this document and used throughout. Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Protocols

### `ExecutionEngine`

The following methods are added to the `ExecutionEngine` protocol for use as a validator:

#### `assemble_block`

Produces a new instance of an execution payload, with the specified `timestamp`,
on top of the execution payload chain tip identified by `block_hash`.

The body of this function is implementation dependent.
The Consensus API may be used to implement this with an external execution engine.

```python
def assemble_block(self: ExecutionEngine, block_hash: Hash32, timestamp: uint64, random: Bytes32) -> ExecutionPayload:
    ...
```

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below. Namely, the transition block handling and the addition of `ExecutionPayload`.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### Execution Payload

###### `get_pow_chain_head`

Let `get_pow_chain_head() -> PowBlock` be the function that returns the head of the PoW chain. The body of the function is implementation specific.

* Set `block.body.execution_payload = get_execution_payload(state, transition_store, execution_engine)` where:

```python
def compute_randao_mix(state: BeaconState, randao_reveal: BLSSignature) -> Bytes32:
    epoch = get_current_epoch(state)
    return xor(get_randao_mix(state, epoch), hash(randao_reveal))


def produce_execution_payload(state: BeaconState,
                              parent_hash: Hash32,
                              randao_reveal: BLSSignature,
                              execution_engine: ExecutionEngine) -> ExecutionPayload:
    timestamp = compute_timestamp_at_slot(state, state.slot)
    randao_mix = compute_randao_mix(state, randao_reveal)
    return execution_engine.assemble_block(parent_hash, timestamp, randao_mix)


def get_execution_payload(state: BeaconState,
                          transition_store: TransitionStore,
                          randao_reveal: BLSSignature,
                          execution_engine: ExecutionEngine) -> ExecutionPayload:
    if not is_merge_complete(state):
        pow_block = get_pow_chain_head()
        if not is_valid_terminal_pow_block(transition_store, pow_block):
            # Pre-merge, empty payload
            return ExecutionPayload()
        else:
            # Signify merge via producing on top of the last PoW block
            return produce_execution_payload(state, pow_block.block_hash, randao_reveal, execution_engine)

    # Post-merge, normal payload
    parent_hash = state.latest_execution_payload_header.block_hash
    return produce_execution_payload(state, parent_hash, randao_reveal, execution_engine)
```
