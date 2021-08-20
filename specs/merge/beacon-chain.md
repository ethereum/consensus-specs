# The Merge -- The Beacon Chain

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
  - [Genesis testing settings](#genesis-testing-settings)
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
    - [`is_valid_gas_limit`](#is_valid_gas_limit)
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
| `GAS_LIMIT_DENOMINATOR` | `uint64(2**10)` (= 1,024) |
| `MIN_GAS_LIMIT` | `uint64(5000)` (= 5,000) |

## Configuration

### Genesis testing settings

*Note*: These configuration settings do not apply to the mainnet and are utilized only by pure Merge testing.

| Name | Value |
| - | - |
| `GENESIS_GAS_LIMIT` | `uint64(30000000)` (= 30,000,000) |
| `GENESIS_BASE_FEE_PER_GAS` | `Bytes32('0x00ca9a3b00000000000000000000000000000000000000000000000000000000')` (= 1,000,000,000) |

## Containers

### Extended containers

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    # Execution
    execution_payload: ExecutionPayload  # [New in Merge]
```

#### `BeaconState`

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
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Participation
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Inactivity
    inactivity_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    # Sync
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # Execution
    latest_execution_payload_header: ExecutionPayloadHeader  # [New in Merge]
```

### New containers

#### `ExecutionPayload`

*Note*: The `base_fee_per_gas` field is serialized in little-endian.

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
    base_fee_per_gas: Bytes32  # base fee introduced in EIP-1559, little-endian serialized
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
    base_fee_per_gas: Bytes32
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
    process_sync_aggregate(state, block.body.sync_aggregate)
    if is_execution_enabled(state, block.body):
        process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE)  # [New in Merge]
```

### Execution payload processing

#### `is_valid_gas_limit`

```python
def is_valid_gas_limit(payload: ExecutionPayload, parent: ExecutionPayloadHeader) -> bool:
    parent_gas_limit = parent.gas_limit

    # Check if the payload used too much gas
    if payload.gas_used > payload.gas_limit:
        return False

    # Check if the payload changed the gas limit too much
    if payload.gas_limit >= parent_gas_limit + parent_gas_limit // GAS_LIMIT_DENOMINATOR:
        return False
    if payload.gas_limit <= parent_gas_limit - parent_gas_limit // GAS_LIMIT_DENOMINATOR:
        return False

    # Check if the gas limit is at least the minimum gas limit
    if payload.gas_limit < MIN_GAS_LIMIT:
        return False

    return True
```

#### `process_execution_payload`

*Note:* This function depends on `process_randao` function call as it retrieves the most recent randao mix from the `state`. Implementations that are considering parallel processing of execution payload with respect to beacon chain state transition function should work around this dependency.

```python
def process_execution_payload(state: BeaconState, payload: ExecutionPayload, execution_engine: ExecutionEngine) -> None:
    # Verify consistency of the parent hash, block number, random, base fee per gas and gas limit
    if is_merge_complete(state):
        assert payload.parent_hash == state.latest_execution_payload_header.block_hash
        assert payload.block_number == state.latest_execution_payload_header.block_number + uint64(1)
        assert payload.random == get_randao_mix(state, get_current_epoch(state))
        assert is_valid_gas_limit(payload, state.latest_execution_payload_header)
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify the execution payload is valid
    assert execution_engine.on_payload(payload)
    # Cache execution payload header
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
        base_fee_per_gas=payload.base_fee_per_gas,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
    )
```

## Testing

*Note*: The function `initialize_beacon_state_from_eth1` is modified for pure Merge testing only.

*Note*: The function `initialize_beacon_state_from_eth1` is modified: (1) using `MERGE_FORK_VERSION` as the current fork version, (2) utilizing the Merge `BeaconBlockBody` when constructing the initial `latest_block_header`, and (3) initialize `latest_execution_payload_header`.

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

    # Fill in sync committees
    # Note: A duplicate committee is assigned for the current and next committee at genesis
    state.current_sync_committee = get_next_sync_committee(state)
    state.next_sync_committee = get_next_sync_committee(state)

    # [New in Merge] Initialize the execution payload header (with block number set to 0)
    state.latest_execution_payload_header.block_hash = eth1_block_hash
    state.latest_execution_payload_header.timestamp = eth1_timestamp
    state.latest_execution_payload_header.random = eth1_block_hash
    state.latest_execution_payload_header.gas_limit = GENESIS_GAS_LIMIT
    state.latest_execution_payload_header.base_fee_per_gas = GENESIS_BASE_FEE_PER_GAS

    return state
```
