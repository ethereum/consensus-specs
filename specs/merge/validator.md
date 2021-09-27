# The Merge -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Custom types](#custom-types)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [`prepare_payload`](#prepare_payload)
    - [`get_payload`](#get_payload)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [ExecutionPayload](#executionpayload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement executable beacon chain proposal.

## Prerequisites

This document is an extension of the [Altair -- Honest Validator](../altair/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [The Merge](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `PayloadId` | `uint64` | Identifier of a payload building process |

## Protocols

### `ExecutionEngine`

*Note*: `prepare_payload` and `get_payload` functions are added to the `ExecutionEngine` protocol for use as a validator.

The body of each of these functions is implementation dependent.
The Engine API may be used to implement them with an external execution engine.

#### `prepare_payload`

Given the set of execution payload attributes, `prepare_payload` initiates a process of building an execution payload
on top of the execution chain tip identified by `parent_hash`.

```python
def prepare_payload(self: ExecutionEngine,
                    parent_hash: Hash32,
                    timestamp: uint64,
                    random: Bytes32,
                    fee_recipient: ExecutionAddress) -> PayloadId:
    """
    Return ``payload_id`` that is used to obtain the execution payload in a subsequent ``get_payload`` call.
    """
    ...
```

#### `get_payload`

Given the `payload_id`, `get_payload` returns the most recent version of the execution payload that
has been built since the corresponding call to `prepare_payload` method.

```python
def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> ExecutionPayload:
    """
    Return ``execution_payload`` object.
    """
    ...
```

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below. Namely, the transition block handling and the addition of `ExecutionPayload`.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayload

To obtain an execution payload, a block proposer building a block on top of a `state` must take the following actions:

1. Set `payload_id = prepare_execution_payload(state, pow_chain, fee_recipient, execution_engine)`, where:
    * `state` is the state object after applying `process_slots(state, slot)` transition to the resulting state of the parent block processing
    * `pow_chain` is a list that abstractly represents all blocks in the PoW chain
    * `fee_recipient` is the value suggested to be used for the `coinbase` field of the execution payload


```python
def get_pow_block_at_terminal_total_difficulty(pow_chain: Sequence[PowBlock]) -> Optional[PowBlock]:
    # `pow_chain` abstractly represents all blocks in the PoW chain
    for block in pow_chain:
        parent = get_pow_block(block.parent_hash)
        block_reached_ttd = block.total_difficulty >= TERMINAL_TOTAL_DIFFICULTY
        parent_reached_ttd = parent.total_difficulty >= TERMINAL_TOTAL_DIFFICULTY
        if block_reached_ttd and not parent_reached_ttd:
            return block

    return None


def get_terminal_pow_block(pow_chain: Sequence[PowBlock]) -> Optional[PowBlock]:
    if TERMINAL_BLOCK_HASH != Hash32():
        # Terminal block hash override takes precedence over terminal total difficulty
        pow_block_overrides = [block for block in pow_chain if block.block_hash == TERMINAL_BLOCK_HASH]
        if not any(pow_block_overrides):
            return None
        return pow_block_overrides[0]

    return get_pow_block_at_terminal_total_difficulty(pow_chain)


def prepare_execution_payload(state: BeaconState,
                              pow_chain: Sequence[PowBlock],
                              fee_recipient: ExecutionAddress,
                              execution_engine: ExecutionEngine) -> Optional[PayloadId]:
    if not is_merge_complete(state):
        terminal_pow_block = get_terminal_pow_block(pow_chain)
        if terminal_pow_block is None:
            # Pre-merge, no prepare payload call is needed
            return None
        # Signify merge via producing on top of the terminal PoW block
        parent_hash = terminal_pow_block.block_hash
    else:
        # Post-merge, normal payload
        parent_hash = state.latest_execution_payload_header.block_hash

    timestamp = compute_timestamp_at_slot(state, state.slot)
    random = get_randao_mix(state, get_current_epoch(state))
    return execution_engine.prepare_payload(parent_hash, timestamp, random, fee_recipient)
```

2. Set `block.body.execution_payload = get_execution_payload(payload_id, execution_engine)`, where:

```python
def get_execution_payload(payload_id: Optional[PayloadId], execution_engine: ExecutionEngine) -> ExecutionPayload:
    if payload_id is None:
        # Pre-merge, empty payload
        return ExecutionPayload()
    else:
        return execution_engine.get_payload(payload_id)
```

*Note*: It is recommended for a validator to call `prepare_execution_payload` as soon as input parameters become known,
and make subsequent calls to this function when any of these parameters gets updated.
