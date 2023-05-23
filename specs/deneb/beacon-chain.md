# Deneb -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Domain types](#domain-types)
  - [Blob](#blob)
- [Preset](#preset)
  - [Execution](#execution)
- [Configuration](#configuration)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [`kzg_commitment_to_versioned_hash`](#kzg_commitment_to_versioned_hash)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution engine](#execution-engine)
    - [Request data](#request-data)
      - [Modified `NewPayloadRequest`](#modified-newpayloadrequest)
    - [Engine APIs](#engine-apis)
    - [Modified `notify_new_payload`](#modified-notify_new_payload)
    - [Execution payload](#execution-payload)
      - [`process_execution_payload`](#process_execution_payload)
- [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This upgrade adds blobs to the beacon chain as part of Deneb. This is an extension of the Capella upgrade.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `VersionedHash` | `Bytes32` | |
| `BlobIndex` | `uint64` | |

## Constants

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_BLOB_SIDECAR` | `DomainType('0x0B000000')` |

### Blob

| Name | Value |
| - | - |
| `BLOB_TX_TYPE` | `uint8(0x03)` |
| `VERSIONED_HASH_VERSION_KZG` | `Bytes1('0x01')` |

## Preset

### Execution

| Name | Value |
| - | - |
| `MAX_BLOBS_PER_BLOCK` | `uint64(2**2)` (= 4) |

## Configuration


## Containers

### Extended containers

#### `BeaconBlockBody`

Note: `BeaconBlock` and `SignedBeaconBlock` types are updated indirectly.

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
    execution_payload: ExecutionPayload  # [Modified in Deneb]
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOBS_PER_BLOCK]  # [New in Deneb]
```

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
    # Execution block header fields
    parent_hash: Hash32
    fee_recipient: ExecutionAddress  # 'beneficiary' in the yellow paper
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32  # 'difficulty' in the yellow paper
    block_number: uint64  # 'number' in the yellow paper
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
    excess_data_gas: uint256  # [New in Deneb]
```

#### `ExecutionPayloadHeader`

```python
class ExecutionPayloadHeader(Container):
    # Execution block header fields
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions_root: Root
    withdrawals_root: Root
    excess_data_gas: uint256  # [New in Deneb]
```

## Helper functions

### Misc

#### `kzg_commitment_to_versioned_hash`

```python
def kzg_commitment_to_versioned_hash(kzg_commitment: KZGCommitment) -> VersionedHash:
    return VERSIONED_HASH_VERSION_KZG + hash(kzg_commitment)[1:]
```

## Beacon chain state transition function

### Execution engine

#### Request data

##### Modified `NewPayloadRequest`

```python
@dataclass
class NewPayloadRequest(object):
    execution_payload: ExecutionPayload
    versioned_hashes: Sequence[VersionedHash]
```

#### Engine APIs

#### Modified `notify_new_payload`

```python
def notify_new_payload(self: ExecutionEngine, new_payload_request: NewPayloadRequest) -> bool:
    """
    Return ``True`` if and only if ``new_payload_request`` is valid with respect to ``self.execution_state``.
    """
    ...
```

#### Execution payload

##### `process_execution_payload`

```python
def process_execution_payload(state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    if is_merge_transition_complete(state):
        assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify the execution payload is valid
    # [Modified in Deneb]
    versioned_hashes = [kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments]
    assert execution_engine.notify_new_payload(
        NewPayloadRequest(execution_payload=payload, versioned_hashes=versioned_hashes)
    )

    # Cache execution payload header
    state.latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=payload.parent_hash,
        fee_recipient=payload.fee_recipient,
        state_root=payload.state_root,
        receipts_root=payload.receipts_root,
        logs_bloom=payload.logs_bloom,
        prev_randao=payload.prev_randao,
        block_number=payload.block_number,
        gas_limit=payload.gas_limit,
        gas_used=payload.gas_used,
        timestamp=payload.timestamp,
        extra_data=payload.extra_data,
        base_fee_per_gas=payload.base_fee_per_gas,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
        withdrawals_root=hash_tree_root(payload.withdrawals),
        excess_data_gas=payload.excess_data_gas,  # [New in Deneb]
    )
```

## Testing

*Note*: The function `initialize_beacon_state_from_eth1` is modified for pure Deneb testing only.

The `BeaconState` initialization is unchanged, except for the use of the updated `deneb.BeaconBlockBody` type
when initializing the first body-root.

```python
def initialize_beacon_state_from_eth1(eth1_block_hash: Hash32,
                                      eth1_timestamp: uint64,
                                      deposits: Sequence[Deposit],
                                      execution_payload_header: ExecutionPayloadHeader=ExecutionPayloadHeader()
                                      ) -> BeaconState:
    fork = Fork(
        previous_version=DENEB_FORK_VERSION,  # [Modified in Deneb] for testing only
        current_version=DENEB_FORK_VERSION,  # [Modified in Deneb]
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

    # Initialize the execution payload header
    # If empty, will initialize a chain that has not yet gone through the Merge transition
    state.latest_execution_payload_header = execution_payload_header

    return state
```
