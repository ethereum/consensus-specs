# Fulu -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Execution](#execution)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconBlock`](#beaconblock)
    - [`SignedBeaconBlock`](#signedbeaconblock)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)
- [Beacon chain state transition function](#beacon-chain-state-transition-function-1)
  - [Execution engine](#execution-engine)
    - [Request data](#request-data)
      - [Modified `NewPayloadRequest`](#modified-newpayloadrequest)
    - [Engine APIs](#engine-apis)
      - [Modified `is_valid_block_hash`](#modified-is_valid_block_hash)
      - [Modified `is_valid_versioned_hashes`](#modified-is_valid_versioned_hashes)
      - [Modified `notify_new_payload`](#modified-notify_new_payload)
      - [Modified `verify_and_notify_new_payload`](#modified-verify_and_notify_new_payload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

*Note*: This specification is built upon [Electra](../electra/beacon-chain.md) and is under active development.

## Configuration

### Execution

| Name | Value | Description |
| - | - | - |
| `MAX_BLOBS_PER_BLOCK_FULU` | `uint64(12)` | *[New in Fulu:EIP7594]* Maximum number of blobs in a single block limited by `MAX_BLOB_COMMITMENTS_PER_BLOCK` |

## Containers

### Extended containers

#### `ExecutionPayload`

*Note*: The container `ExecutionPayload` is modified to include a new `proof_version` field.

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
    blob_gas_used: uint64
    excess_blob_gas: uint64
    proof_version: uint8  # [New in Fulu:7594]
```

#### `BeaconBlockBody`

*Note*: The container `BeaconBlockBody` is modified to use the updated `ExecutionPayload` container.

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
    execution_payload: ExecutionPayload  # [Modified in Fulu:7594]
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
```

#### `BeaconBlock`

*Note*: The container `BeaconBlock` is modified to use the updated `BeaconBlockBody` container.

```python
class BeaconBlock(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    parent_root: Root
    state_root: Root
    body: BeaconBlockBody  # [Modified in Fulu:7594]
```

#### `SignedBeaconBlock`

*Note*: The container `SignedBeaconBlock` is modified to use the updated `BeaconBlock` container.

```python
class SignedBeaconBlock(Container):
    message: BeaconBlock  # [Modified in Fulu:7594]
    signature: BLSSignature
```

## Beacon chain state transition function

### Block processing

*Note*: The function `process_block` is modified to use the updated `process_execution_payload` function.

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_withdrawals(state, block.body.execution_payload)
    process_execution_payload(state, block.body, EXECUTION_ENGINE)  # [Modified in Fulu:7594]
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Execution payload

##### Modified `process_execution_payload`

*Note*: The function `process_execution_payload` is modified to use the updated `BeaconBlockBody`
container, the new `MAX_BLOBS_PER_BLOCK_FULU` configuration value in the commitments limit check,
and the updated `verify_and_notify_new_payload` function from the engine API.

```python
def process_execution_payload(
    state: BeaconState,
    body: BeaconBlockBody,  # [Modified in Fulu:EIP7594]
    execution_engine: ExecutionEngine
) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert len(body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK_FULU  # [Modified in Fulu:EIP7594]
    # Verify the execution payload is valid
    versioned_hashes = [kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments]
    assert execution_engine.verify_and_notify_new_payload(  # [Modified in Fulu:EIP7594]
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=body.execution_requests,
        )
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
        blob_gas_used=payload.blob_gas_used,
        excess_blob_gas=payload.excess_blob_gas,
    )
```

## Beacon chain state transition function

### Execution engine

#### Request data

##### Modified `NewPayloadRequest`

*Note*: The dataclass `NewPayloadRequest` is modified to use the updated `ExecutionPayload` container.

```python
@dataclass
class NewPayloadRequest(object):
    execution_payload: ExecutionPayload  # [Modified in Fulu:7594]
    versioned_hashes: Sequence[VersionedHash]
    parent_beacon_block_root: Root
    execution_requests: ExecutionRequests
```

#### Engine APIs

##### Modified `is_valid_block_hash`

*Note*: The function `is_valid_block_hash` is modified to use the updated `ExecutionPayload` container.

```python
def is_valid_block_hash(
    self: ExecutionEngine,
    execution_payload: ExecutionPayload,  # [Modified in Fulu:7594]
    parent_beacon_block_root: Root,
    execution_requests_list: Sequence[bytes],
) -> bool:
    """
    Return ``True`` if and only if ``execution_payload.block_hash`` is computed correctly.
    """
    ...
```

##### Modified `is_valid_versioned_hashes`

*Note*: The function `is_valid_versioned_hashes` is modified to use the updated `NewPayloadRequest` dataclass.

```python
def is_valid_versioned_hashes(
    self: ExecutionEngine,
    new_payload_request: NewPayloadRequest,  # [Modified in Fulu:7594]
) -> bool:
    """
    Return ``True`` if and only if the version hashes computed by the blob transactions of
    ``new_payload_request.execution_payload`` matches ``new_payload_request.versioned_hashes``.
    """
    ...
```

##### Modified `notify_new_payload`

*Note*: The function `notify_new_payload` is modified to use the updated `ExecutionPayload` container.

```python
def notify_new_payload(
    self: ExecutionEngine,
    execution_payload: ExecutionPayload,  # [Modified in Fulu:7594]
    parent_beacon_block_root: Root,
    execution_requests_list: Sequence[bytes],
) -> bool:
    """
    Return ``True`` if and only if ``execution_payload`` and ``execution_requests_list``
    are valid with respect to ``self.execution_state``.
    """
    ...
```

##### Modified `verify_and_notify_new_payload`

*Note*: The function `verify_and_notify_new_payload` is modified to use the updated `NewPayloadRequest` dataclass.

```python
def verify_and_notify_new_payload(
    self: ExecutionEngine,
    new_payload_request: NewPayloadRequest  # [Modified in Fulu:7594]
) -> bool:
    """
    Return ``True`` if and only if ``new_payload_request`` is valid with respect to ``self.execution_state``.
    """
    execution_payload = new_payload_request.execution_payload
    parent_beacon_block_root = new_payload_request.parent_beacon_block_root
    execution_requests_list = get_execution_requests_list(new_payload_request.execution_requests)

    if b'' in execution_payload.transactions:
        return False

    if not self.is_valid_block_hash(
            execution_payload,
            parent_beacon_block_root,
            execution_requests_list):
        return False

    if not self.is_valid_versioned_hashes(new_payload_request):
        return False

    if not self.notify_new_payload(
            execution_payload,
            parent_beacon_block_root,
            execution_requests_list):
        return False

    return True
```
