# Ethereum 2.0 The Merge

**Warning**: This document is currently based on [Phase 0](../phase0/beacon-chain.md) and will be rebased on [Altair](../altair/beacon-chain.md).

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Execution](#execution)
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
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution engine](#execution-engine)
    - [`on_payload`](#on_payload)
  - [Block processing](#block-processing)
  - [Execution payload processing](#execution-payload-processing)
    - [`process_execution_payload`](#process_execution_payload)
- [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This patch adds transaction execution to the beacon chain as part of the Merge fork.

## Custom types

*Note*: The `Transaction` type is a stub which is not final.

| Name | SSZ equivalent | Description |
| - | - | - |
| `OpaqueTransaction` | `ByteList[MAX_BYTES_PER_OPAQUE_TRANSACTION]` | a [typed transaction envelope](https://eips.ethereum.org/EIPS/eip-2718#opaque-byte-array-rather-than-an-rlp-array) structured as `TransactionType \|\| TransactionPayload` |
| `Transaction` | `Union[OpaqueTransaction]` | a transaction |

## Constants

### Execution

| Name | Value |
| - | - |
| `MAX_BYTES_PER_OPAQUE_TRANSACTION` | `uint64(2**20)` (= 1,048,576) |
| `MAX_TRANSACTIONS_PER_PAYLOAD` | `uint64(2**14)` (= 16,384) |
| `BYTES_PER_LOGS_BLOOM` | `uint64(2**8)` (= 256) |

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
    receipt_root: Bytes32  # 'receipts root' in the yellow paper
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    random: Bytes32  # 'difficulty' in the yellow paper
    block_number: uint64  # 'number' in the yellow paper
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
```

#### `ExecutionPayloadHeader`

```python
class ExecutionPayloadHeader(Container):
    # Execution block header fields
    parent_hash: Hash32
    coinbase: Bytes20
    state_root: Bytes32
    receipt_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    random: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions_root: Root
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

## Beacon chain state transition function

### Execution engine

The implementation-dependent `ExecutionEngine` protocol encapsulates the execution sub-system logic via:

* a state object `self.execution_state` of type `ExecutionState`
* a state transition function `self.on_payload` which mutates `self.execution_state`

#### `on_payload`

```python
def on_payload(self: ExecutionEngine, execution_payload: ExecutionPayload) -> bool:
    """
    Returns ``True`` iff ``execution_payload`` is valid with respect to ``self.execution_state``.
    """
    ...
```

The above function is accessed through the `EXECUTION_ENGINE` module which instantiates the `ExecutionEngine` protocol.

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    if is_execution_enabled(state, block.body):
        process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE)  # [New in Merge]
```

### Execution payload processing

#### `process_execution_payload`

*Note:* This function depends on `process_randao` function call as it retrieves the most recent randao mix from the `state`. Implementations that are considering parallel processing of execution payload with respect to beacon chain state transition function should work around this dependency.

```python
def process_execution_payload(state: BeaconState, payload: ExecutionPayload, execution_engine: ExecutionEngine) -> None:
    # Verify consistency of the parent hash, block number and random
    if is_merge_complete(state):
        assert payload.parent_hash == state.latest_execution_payload_header.block_hash
        assert payload.block_number == state.latest_execution_payload_header.block_number + uint64(1)
        assert payload.random == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify the execution payload is valid
    assert execution_engine.on_payload(payload)
    # Cache execution payload
    state.latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=payload.parent_hash,
        coinbase=payload.coinbase,
        state_root=payload.state_root,
        receipt_root=payload.receipt_root,
        logs_bloom=payload.logs_bloom,
        random=payload.random,
        block_number=payload.block_number,
        gas_limit=payload.gas_limit,
        gas_used=payload.gas_used,
        timestamp=payload.timestamp,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
    )
```

## Testing

*Note*: The function `initialize_beacon_state_from_eth1` is modified for pure Merge testing only.

*Note*: The function `initialize_beacon_state_from_eth1` is modified to use `MERGE_FORK_VERSION` and initialize `latest_execution_payload_header`.

```python
def initialize_beacon_state_from_eth1(eth1_block_hash: Bytes32,
                                      eth1_timestamp: uint64,
                                      deposits: Sequence[Deposit]) -> BeaconState:
    fork = Fork(
        previous_version=GENESIS_FORK_VERSION,
        current_version=MERGE_FORK_VERSION,  # [Modified in Merge]
        epoch=GENESIS_EPOCH,
    )
    state = BeaconState(
        genesis_time=eth1_timestamp + GENESIS_DELAY,
        fork=fork,
        eth1_data=Eth1Data(block_hash=eth1_block_hash, deposit_count=uint64(len(deposits))),
        latest_block_header=BeaconBlockHeader(body_root=hash_tree_root(BeaconBlockBody())),
        randao_mixes=[eth1_block_hash] * EPOCHS_PER_HISTORICAL_VECTOR,  # Seed RANDAO with Eth1 entropy
    )

    # Process deposits
    leaves = list(map(lambda deposit: deposit.data, deposits))
    for index, deposit in enumerate(deposits):
        deposit_data_list = List[DepositData, 2**DEPOSIT_CONTRACT_TREE_DEPTH](*leaves[:index + 1])
        state.eth1_data.deposit_root = hash_tree_root(deposit_data_list)
        process_deposit(state, deposit)

    # Process activations
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        validator.effective_balance = min(balance - balance % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
        if validator.effective_balance == MAX_EFFECTIVE_BALANCE:
            validator.activation_eligibility_epoch = GENESIS_EPOCH
            validator.activation_epoch = GENESIS_EPOCH

    # Set genesis validators root for domain separation and chain versioning
    state.genesis_validators_root = hash_tree_root(state.validators)

    # [New in Merge] Initialize the execution payload header (with block number set to 0)
    state.latest_execution_payload_header.block_hash = eth1_block_hash
    state.latest_execution_payload_header.timestamp = eth1_timestamp
    state.latest_execution_payload_header.random = eth1_block_hash

    return state
```
