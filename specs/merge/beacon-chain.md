# Ethereum 2.0 The Merge

**Warning**: This document is currently based on [Phase 0](../phase0/beacon-chain.md) and will be rebased for [Altair](../altair/beacon-chain.md).

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
  - [Merge](#merge)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
  - [New containers](#new-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
- [Helper functions](#helper-functions)
  - [Predicates](#predicates)
    - [`is_merge_complete`](#is_merge_complete)
    - [`is_merge_block`](#is_merge_block)
    - [`is_execution_enabled`](#is_execution_enabled)
  - [Misc](#misc)
    - [`compute_timestamp_at_slot`](#compute_timestamp_at_slot)
- [Execution engine](#execution-engine)
  - [`on_payload`](#on_payload)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
  - [Execution payload processing](#execution-payload-processing)
    - [`process_execution_payload`](#process_execution_payload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This patch adds transaction execution to the beacon chain as part of the merge.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `OpaqueTransaction` | `ByteList[MAX_BYTES_PER_OPAQUE_TRANSACTION]` | a [typed transaction envelope](https://eips.ethereum.org/EIPS/eip-2718#opaque-byte-array-rather-than-an-rlp-array) structured as `TransactionType \|\| TransactionPayload` |

## Constants

### Execution

| Name | Value |
| - | - |
| `MAX_BYTES_PER_OPAQUE_TRANSACTION` | `uint64(2**20)` (= 1,048,576) |
| `MAX_OPAQUE_TRANSACTIONS` | `uint64(2**14)` (= 16,384) |
| `BYTES_PER_LOGS_BLOOM` | `uint64(2**8)` (= 256) |

## Configuration

### Merge

*Note*: The configuration value `MERGE_FORK_EPOCH` is not final.

| Name | Value |
| - | - |
| `MERGE_FORK_VERSION` | `Version('0x02000000')` |
| `MERGE_FORK_EPOCH` | `Epoch(18446744073709551615)` |

## Containers

### Extended containers

#### `BeaconBlockBody`

```python
class BeaconBlockBody(phase0.BeaconBlockBody):
    # Execution
    execution_payload: ExecutionPayload  # [New in Merge]
```

#### `BeaconState`

```python
class BeaconState(phase0.BeaconState):
    # Execution
    latest_execution_payload_header: ExecutionPayloadHeader  # [New in Merge]
```

### New containers

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
    # Execution block header fields
    parent_hash: Hash32
    coinbase: Bytes20  # 'beneficiary' in the yellow paper
    state_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    receipt_root: Bytes32  # 'receipts root' in the yellow paper
    block_number: uint64  # 'number' in the yellow paper
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    opaque_transactions: List[OpaqueTransaction, MAX_OPAQUE_TRANSACTIONS]
```

#### `ExecutionPayloadHeader`

```python
class ExecutionPayloadHeader(Container):
    # Execution block header fields
    parent_hash: Hash32
    coinbase: Bytes20
    state_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    receipt_root: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    opaque_transactions_root: Root
```

## Helper functions

### Predicates

#### `is_merge_complete`

```python
def is_merge_complete(state: BeaconState) -> bool:
    return state.latest_execution_payload_header != ExecutionPayloadHeader()
```

#### `is_merge_block`

```python
def is_merge_block(state: BeaconState, body: BeaconBlockBody) -> bool:
    return not is_merge_complete(state) and body.execution_payload != ExecutionPayload()
```

#### `is_execution_enabled`

```python
def is_execution_enabled(state: BeaconState, body: BeaconBlockBody) -> bool:
    return is_merge_block(state, body) or is_merge_complete(state)
```

### Misc

#### `compute_timestamp_at_slot`

*Note*: This function is unsafe with respect to overflows and underflows.

```python
def compute_timestamp_at_slot(state: BeaconState, slot: Slot) -> uint64:
    slots_since_genesis = slot - GENESIS_SLOT
    return uint64(state.genesis_time + slots_since_genesis * SECONDS_PER_SLOT)
```

## Execution engine

The implementation-dependent `ExecutionEngine` protocol encapsulates the execution sub-system logic via:

* a state object `self.execution_state` of type `ExecutionState`
* a state transition function `self.on_payload` which mutates `self.execution_state`

### `on_payload`

```python
def on_payload(self: ExecutionEngine, execution_payload: ExecutionPayload) -> bool:
    """
    Returns ``True`` iff ``execution_payload`` is valid with respect to ``self.execution_state``.
    """
    ...
```

The above function is accessed through the `execution_engine` module which instantiates the `ExecutionEngine` protocol.

## Beacon chain state transition function

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_execution_payload(state, block.body)  # [New in Merge]
```

### Execution payload processing

#### `process_execution_payload`

```python
def process_execution_payload(state: BeaconState, body: BeaconBlockBody) -> None:
    # Skip execution payload processing if execution is not enabled
    if not is_execution_enabled(state, body):
        return
    # Verify consistency of the parent hash and block number
    if is_merge_complete(state):
        assert body.execution_payload.parent_hash == state.latest_execution_payload_header.block_hash
        assert body.execution_payload.block_number == state.latest_execution_payload_header.block_number + uint64(1)
    # Verify timestamp
    assert body.execution_payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify the execution payload is valid
    assert execution_engine.on_payload(body.execution_payload)
    # Cache execution payload
    state.latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=execution_payload.parent_hash,
        coinbase=execution_payload.coinbase,
        state_root=execution_payload.state_root,
        logs_bloom=execution_payload.logs_bloom,
        receipt_root=execution_payload.receipt_root,
        block_number=execution_payload.block_number,
        gas_limit=execution_payload.gas_limit,
        gas_used=execution_payload.gas_used,
        timestamp=execution_payload.timestamp,
        block_hash=execution_payload.block_hash,
        opaque_transactions_root=hash_tree_root(execution_payload.opaque_transactions),
    )
```
