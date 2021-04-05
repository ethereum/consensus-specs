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
  - [Transition](#transition)
  - [Execution](#execution)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
  - [New containers](#new-containers)
    - [`ApplicationPayload`](#applicationpayload)
    - [`ApplicationBlockHeader`](#applicationblockheader)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [`is_transition_completed`](#is_transition_completed)
    - [`is_transition_block`](#is_transition_block)
  - [Block processing](#block-processing)
    - [Application payload processing](#application-payload-processing)
      - [`get_application_state`](#get_application_state)
      - [`application_state_transition`](#application_state_transition)
      - [`process_application_payload`](#process_application_payload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is a patch implementing the executable beacon chain proposal. 
It enshrines application-layer execution and validity as a first class citizen at the core of the beacon chain.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `OpaqueTransaction` | `ByteList[MAX_BYTES_PER_OPAQUE_TRANSACTION]` | a byte-list containing a single [typed transaction envelope](https://eips.ethereum.org/EIPS/eip-2718#opaque-byte-array-rather-than-an-rlp-array) structured as `TransactionType \|\| TransactionPayload` |

## Constants

### Transition

| Name | Value |
| - | - |
| `TRANSITION_TOTAL_DIFFICULTY` | **TBD** |

### Execution

| Name | Value |
| - | - |
| `MAX_BYTES_PER_OPAQUE_TRANSACTION` | `uint64(2**20)` (= 1,048,576) |
| `MAX_APPLICATION_TRANSACTIONS` | `uint64(2**14)` (= 16,384) |
| `BYTES_PER_LOGS_BLOOM` | `uint64(2**8)` (= 256) |

## Containers

### Extended containers

*Note*: Extended SSZ containers inherit all fields from the parent in the original
order and append any additional fields to the end.

#### `BeaconBlockBody`

*Note*: `BeaconBlockBody` fields remain unchanged other than the addition of `application_payload`.

```python
class BeaconBlockBody(phase0.BeaconBlockBody):
    application_payload: ApplicationPayload  # [New in Merge] application payload
```

#### `BeaconState`

*Note*: `BeaconState` fields remain unchanged other than addition of `latest_application_block_header`.

```python
class BeaconState(phase0.BeaconState):
    # Application-layer
    latest_application_block_header: ApplicationBlockHeader  # [New in Merge]
```

### New containers

#### `ApplicationPayload`

The application payload included in a `BeaconBlockBody`.

```python
class ApplicationPayload(Container):
    block_hash: Bytes32  # Hash of application block
    parent_hash: Bytes32
    coinbase: Bytes20
    state_root: Bytes32
    number: uint64
    gas_limit: uint64
    gas_used: uint64
    receipt_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    transactions: List[OpaqueTransaction, MAX_APPLICATION_TRANSACTIONS]
```

#### `ApplicationBlockHeader`

The application block header included in a `BeaconState`.

*Note:* Holds application payload data without transaction list.

```python
class ApplicationBlockHeader(Container):
    block_hash: Bytes32  # Hash of application block
    parent_hash: Bytes32
    coinbase: Bytes20
    state_root: Bytes32
    number: uint64
    gas_limit: uint64
    gas_used: uint64
    receipt_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    transactions_root: Root
```

## Helper functions

### Misc

#### `is_transition_completed`

```python
def is_transition_completed(state: BeaconState) -> boolean:
    return state.latest_application_block_header.block_hash != Bytes32()
```

#### `is_transition_block`

```python
def is_transition_block(state: BeaconState, block_body: BeaconBlockBody) -> boolean:
    is_empty_latest_application_block_header = state.latest_application_block_header.block_hash == Bytes32()
    is_empty_application_payload_block_hash = block_body.application_payload.block_hash == Bytes32()
    return is_empty_latest_application_block_header and not is_empty_application_payload_block_hash
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_application_payload(state, block.body)  # [New in Merge]
```

#### Application payload processing

##### `get_application_state`

*Note*: `ApplicationState` class is an abstract class representing ethereum application state.

Let `get_application_state(application_state_root: Bytes32) -> ApplicationState`  be the function that given the root hash returns a copy of ethereum application state. 
The body of the function is implementation dependent.

##### `application_state_transition`

Let `application_state_transition(application_state: ApplicationState, application_payload: ApplicationPayload) -> None` be the transition function of ethereum application state. 
The body of the function is implementation dependent.

*Note*: `application_state_transition` must throw `AssertionError` if either the transition itself or one of the post-transition verifications has failed.

##### `process_application_payload`

```python
def process_application_payload(state: BeaconState, body: BeaconBlockBody) -> None:
    """
    Note: This function is designed to be able to be run in parallel with the other `process_block` sub-functions
    """
    application_payload = body.application_payload

    if not is_transition_completed(state):
        assert application_payload == ApplicationPayload()
        return

    if not is_transition_block(state, body):
        assert application_payload.parent_hash == state.latest_application_block_header.block_hash
        assert application_payload.number == state.latest_application_block_header.number + 1

    application_state = get_application_state(state.latest_application_block_header.state_root)
    application_state_transition(application_state, body.application_payload)

    state.latest_application_block_header = ApplicationBlockHeader(
        block_hash=application_payload.block_hash,
        parent_hash=application_payload.parent_hash,
        coinbase=application_payload.coinbase,
        state_root=application_payload.state_root,
        number=application_payload.number,
        gas_limit=application_payload.gas_limit,
        gas_used=application_payload.gas_used,
        receipt_root=application_payload.receipt_root,
        logs_bloom=application_payload.logs_bloom,
        transactions_root=hash_tree_root(application_payload.transactions),
    )
```
