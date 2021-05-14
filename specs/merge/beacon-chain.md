# Ethereum 2.0 The Merge

**Warning:** This document is currently based on [Phase 0](../phase0/beacon-chain.md) but will be rebased to [Altair](../altair/beacon-chain.md) once the latter is shipped.

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Execution](#execution)
- [Configuration](#configuration)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
  - [New containers](#new-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [`new_block`](#new_block)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [`is_execution_enabled`](#is_execution_enabled)
    - [`is_transition_completed`](#is_transition_completed)
    - [`is_transition_block`](#is_transition_block)
    - [`compute_time_at_slot`](#compute_time_at_slot)
  - [Block processing](#block-processing)
    - [Execution payload processing](#execution-payload-processing)
      - [`process_execution_payload`](#process_execution_payload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is a patch implementing the executable beacon chain proposal. 
It enshrines transaction execution and validity as a first class citizen at the core of the beacon chain.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `OpaqueTransaction` | `ByteList[MAX_BYTES_PER_OPAQUE_TRANSACTION]` | a byte-list containing a single [typed transaction envelope](https://eips.ethereum.org/EIPS/eip-2718#opaque-byte-array-rather-than-an-rlp-array) structured as `TransactionType \|\| TransactionPayload` |

## Constants

### Execution

| Name | Value |
| - | - |
| `MAX_BYTES_PER_OPAQUE_TRANSACTION` | `uint64(2**20)` (= 1,048,576) |
| `MAX_EXECUTION_TRANSACTIONS` | `uint64(2**14)` (= 16,384) |
| `BYTES_PER_LOGS_BLOOM` | `uint64(2**8)` (= 256) |

## Configuration

Warning: this configuration is not definitive.

| Name | Value |
| - | - |
| `MERGE_FORK_VERSION` | `Version('0x02000000')` |
| `MERGE_FORK_EPOCH` | `Epoch(18446744073709551615)` **TBD** |
| `TRANSITION_TOTAL_DIFFICULTY` | **TBD** |

## Containers

### Extended containers

*Note*: Extended SSZ containers inherit all fields from the parent in the original
order and append any additional fields to the end.

#### `BeaconBlockBody`

*Note*: `BeaconBlockBody` fields remain unchanged other than the addition of `execution_payload`.

```python
class BeaconBlockBody(phase0.BeaconBlockBody):
    execution_payload: ExecutionPayload  # [New in Merge]
```

#### `BeaconState`

*Note*: `BeaconState` fields remain unchanged other than addition of `latest_execution_payload_header`.

```python
class BeaconState(phase0.BeaconState):
    # Execution-layer
    latest_execution_payload_header: ExecutionPayloadHeader  # [New in Merge]
```

### New containers

#### `ExecutionPayload`

The execution payload included in a `BeaconBlockBody`.

```python
class ExecutionPayload(Container):
    block_hash: Hash32  # Hash of execution block
    parent_hash: Hash32
    coinbase: Bytes20
    state_root: Bytes32
    number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    receipt_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    transactions: List[OpaqueTransaction, MAX_EXECUTION_TRANSACTIONS]
```

#### `ExecutionPayloadHeader`

The execution payload header included in a `BeaconState`.

*Note:* Holds execution payload data without transaction bodies.

```python
class ExecutionPayloadHeader(Container):
    block_hash: Hash32  # Hash of execution block
    parent_hash: Hash32
    coinbase: Bytes20
    state_root: Bytes32
    number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    receipt_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    transactions_root: Root
```

## Protocols

### `ExecutionEngine`

The `ExecutionEngine` protocol separates the consensus and execution sub-systems.
The consensus implementation references an instance of this sub-system with `EXECUTION_ENGINE`. 

The following methods are added to the `ExecutionEngine` protocol for use in the state transition:

#### `new_block`

Verifies the given `execution_payload` with respect to execution state transition, and persists changes if valid.

The body of this function is implementation dependent.
The Consensus API may be used to implement this with an external execution engine.

```python
def new_block(self: ExecutionEngine, execution_payload: ExecutionPayload) -> bool:
    """
    Returns True if the ``execution_payload`` was verified and processed successfully, False otherwise. 
    """
    ...
```

## Helper functions

### Misc

#### `is_execution_enabled`

```python
def is_execution_enabled(state: BeaconState, block: BeaconBlock) -> bool:
    return is_transition_completed(state) or is_transition_block(state, block)
```

#### `is_transition_completed`

```python
def is_transition_completed(state: BeaconState) -> bool:
    return state.latest_execution_payload_header != ExecutionPayloadHeader()
```

#### `is_transition_block`

```python
def is_transition_block(state: BeaconState, block: BeaconBlock) -> bool:
    return not is_transition_completed(state) and block.body.execution_payload != ExecutionPayload()
```

#### `compute_time_at_slot`

*Note*: This function is unsafe with respect to overflows and underflows.

```python
def compute_time_at_slot(state: BeaconState, slot: Slot) -> uint64:
    slots_since_genesis = slot - GENESIS_SLOT
    return uint64(state.genesis_time + slots_since_genesis * SECONDS_PER_SLOT)
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    # Pre-merge, skip execution payload processing
    if is_execution_enabled(state, block):
        process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE)  # [New in Merge]
```

#### Execution payload processing

##### `process_execution_payload`

```python
def process_execution_payload(state: BeaconState,
                              execution_payload: ExecutionPayload,
                              execution_engine: ExecutionEngine) -> None:
    """
    Note: This function is designed to be able to be run in parallel with the other `process_block` sub-functions
    """
    if is_transition_completed(state):
        assert execution_payload.parent_hash == state.latest_execution_payload_header.block_hash
        assert execution_payload.number == state.latest_execution_payload_header.number + 1

    assert execution_payload.timestamp == compute_time_at_slot(state, state.slot)

    assert execution_engine.new_block(execution_payload)

    state.latest_execution_payload_header = ExecutionPayloadHeader(
        block_hash=execution_payload.block_hash,
        parent_hash=execution_payload.parent_hash,
        coinbase=execution_payload.coinbase,
        state_root=execution_payload.state_root,
        number=execution_payload.number,
        gas_limit=execution_payload.gas_limit,
        gas_used=execution_payload.gas_used,
        timestamp=execution_payload.timestamp,
        receipt_root=execution_payload.receipt_root,
        logs_bloom=execution_payload.logs_bloom,
        transactions_root=hash_tree_root(execution_payload.transactions),
    )
```
