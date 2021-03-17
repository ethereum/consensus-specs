# Ethereum 2.0 The Merge

**Warning:** This document is based on [Phase 0](../phase0/beacon-chain.md) and considered to be rebased to [Altair](../altair/beacon-chain.md) once the latter is shipped.

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Execution](#execution)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
  - [New containers](#new-containers)
    - [`Transaction`](#transaction)
    - [`ApplicationPayload`](#applicationpayload)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [`compute_randao_mix`](#compute_randao_mix)
    - [`compute_time_at_slot`](#compute_time_at_slot)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_recent_beacon_block_roots`](#get_recent_beacon_block_roots)
    - [`get_evm_beacon_block_roots`](#get_evm_beacon_block_roots)
  - [Block processing](#block-processing)
    - [Modified `process_eth1_data`](#modified-process_eth1_data)
    - [Application payload processing](#application-payload-processing)
      - [`BeaconChainData`](#beaconchaindata)
      - [`get_application_state`](#get_application_state)
      - [`application_state_transition`](#application_state_transition)
      - [`process_application_payload`](#process_application_payload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is a patch implementing executable beacon chain proposal. 
It enshrines application execution and validity as a first class citizen at the core of the beacon chain.

## Constants

### Execution

| Name | Value |
| - | - |
| `MAX_BYTES_PER_TRANSACTION_PAYLOAD` | `2**20` |
| `MAX_APPLICATION_TRANSACTIONS` | `2**14` |
| `BYTES_PER_LOGS_BLOOM` | `2**8` |
| `EVM_BLOCK_ROOTS_SIZE` | `2**8` |


## Containers

### Extended containers

*Note*: Extended SSZ containers inherit all fields from the parent in the original
order and append any additional fields to the end.

#### `BeaconBlockBody`

*Note*: `BeaconBlockBody` fields remain unchanged other than the addition of `application_payload`.

```python
class BeaconBlockBody(phase0.BeaconBlockBody):
    application_payload: ApplicationPayload  # [Added in Merge] application payload
```

#### `BeaconState`

*Note*: `BeaconState` fields remain unchanged other than the removal of `eth1_data_votes` and addition of `application_state_root` and `application_block_hash`. 


```python
class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    # Eth1
    eth1_data: Eth1Data
    # [Removed in Merge] eth1_data_votes
    eth1_deposit_index: uint64
    # [Added in Merge] hash of the root of application state
    application_state_root: Bytes32
    # [Added in Merge] hash of recent application block
    application_block_hash: Bytes32
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Attestations
    previous_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    current_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint  # Previous epoch snapshot
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
```

### New containers

#### `Transaction`

Application transaction fields structured as an SSZ object for inclusion in an `ApplicationPayload` contained within a `BeaconBlock`.

```python
class Transaction(Container):
    nonce: uint64
    gas_price: uint256
    gas_limit: uint64
    recipient: Bytes20
    value: uint256
    input: List[Bytes1, MAX_BYTES_PER_TRANSACTION_PAYLOAD]
    v: uint256
    r: uint256
    s: uint256
```

#### `ApplicationPayload`

The application payload included in a `BeaconBlock`.

```python
class ApplicationPayload(Container):
    block_hash: Bytes32  # Hash of application block
    coinbase: Bytes20
    state_root: Bytes32
    gas_limit: uint64
    gas_used: uint64
    receipt_root: Bytes32
    logs_bloom: Vector[Bytes1, BYTES_PER_LOGS_BLOOM]
    difficulty: uint64  # Temporary field, will be removed later on
    transactions: List[Transaction, MAX_APPLICATION_TRANSACTIONS]
```

## Helper functions

### Misc

#### `compute_randao_mix`

```python
def compute_randao_mix(state: BeaconState, randao_reveal: BLSSignature) -> Bytes32:
    epoch = get_current_epoch(state)
    return xor(get_randao_mix(state, epoch), hash(randao_reveal))
```

#### `compute_time_at_slot` 

```python
def compute_time_at_slot(state: BeaconState, slot: Slot) -> uint64:
    slots_since_genesis = slot - GENESIS_SLOT
    return uint64(state.genesis_time + slots_since_genesis * SECONDS_PER_SLOT)
```

### Beacon state accessors

#### `get_recent_beacon_block_roots`

```python
def get_recent_beacon_block_roots(state: BeaconState, qty: uint64) -> Sequence[Bytes32]:
    return [
        get_block_root_at_slot(state.slot - i) if GENESIS_SLOT + i < state.slot else Bytes32()
        for i in reversed(range(1, qty + 1))
    ]
```

#### `get_evm_beacon_block_roots`

```python
def get_evm_beacon_block_roots(state: BeaconState) -> Sequence[Bytes32]:
    # EVM_BLOCK_ROOTS_SIZE must be less or equal to SLOTS_PER_HISTORICAL_ROOT
    return get_recent_beacon_block_roots(state, EVM_BLOCK_ROOTS_SIZE)
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)  # [Modified in Merge]
    process_operations(state, block.body)
    process_application_payload(state, block.body)  # [New in Merge]
```

#### Modified `process_eth1_data`

*Note*: The function `process_eth1_data` is modified to update `state.eth1_data` with `eth1_data` of each block.

```python
def process_eth1_data(state: BeaconState, body: BeaconBlockBody) -> None:
    state.eth1_data = body.eth1_data
```

#### Application payload processing

##### `BeaconChainData`

*Note*: `BeaconChainData` contains beacon state data that is used by the application state transition function.

```python
class BeaconChainData(Container):
    slot: Slot
    randao_mix: Bytes32
    timestamp: uint64
    recent_block_roots: Vector[Bytes32, EVM_BLOCK_ROOTS_SIZE]
```

##### `get_application_state`

*Note*: `ApplicationState` class is an abstract class representing ethereum application state.

Let `get_application_state(application_state_root: Bytes32) -> ApplicationState`  be the function that given the root hash returns a copy of ethereum application state. 
The body of the function is implementation dependent.

##### `application_state_transition`

Let `application_state_transition(application_state: ApplicationState, beacon_chain_data: BeaconChainData, application_payload: ApplicationPayload) -> None` be the transition function of ethereum application state. 
The body of the function is implementation dependant.

*Note*: `application_state_transition` must throw `AssertionError` if either the transition itself or one of the post-transition verifications has failed.

##### `process_application_payload`

```python
def process_application_payload(state: BeaconState, body: BeaconBlockBody) -> None:
    """
    Note: This function is designed to be able to be run in parallel with 
    the other `process_block` sub-functions
    """
    
    # Utilizes `compute_randao_mix` to avoid any assumptions about
    # the processing of other `process_block` sub-functions
    beacon_chain_data = BeaconChainData(
        slot=state.slot,
        randao_mix=compute_randao_mix(state, body.randao_reveal),
        timestamp=compute_time_at_slot(state.genesis_time, state.slot),
        recent_block_roots=get_evm_beacon_block_roots(state) 
    )
    
    application_state = get_application_state(state.application_state_root)
    application_state_transition(application_state, beacon_chain_data, body.application_payload)

    state.application_state_root = body.application_payload.state_root
    state.application_block_hash = body.application_payload.block_hash
```
