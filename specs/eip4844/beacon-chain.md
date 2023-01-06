# EIP-4844 -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
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
    - [`validate_blobs_sidecar`](#validate_blobs_sidecar)
    - [`is_data_available`](#is_data_available)
    - [`kzg_commitment_to_versioned_hash`](#kzg_commitment_to_versioned_hash)
    - [`tx_peek_blob_versioned_hashes`](#tx_peek_blob_versioned_hashes)
    - [`verify_kzg_commitments_against_transactions`](#verify_kzg_commitments_against_transactions)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [`process_execution_payload`](#process_execution_payload)
    - [Blob KZG commitments](#blob-kzg-commitments)
- [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This upgrade adds blobs to the beacon chain as part of EIP-4844. This is an extension of the Capella upgrade.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `VersionedHash` | `Bytes32` | |

## Constants

### Blob

| Name | Value |
| - | - |
| `BLOB_TX_TYPE` | `uint8(0x05)` |
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
    execution_payload: ExecutionPayload  # [Modified in EIP-4844]
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOBS_PER_BLOCK]  # [New in EIP-4844]
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
    excess_data_gas: uint256  # [New in EIP-4844]
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
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
    excess_data_gas: uint256  # [New in EIP-4844]
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions_root: Root
    withdrawals_root: Root
```

## Helper functions

### Misc

#### `validate_blobs_sidecar`

```python
def validate_blobs_sidecar(slot: Slot,
                           beacon_block_root: Root,
                           expected_kzg_commitments: Sequence[KZGCommitment],
                           blobs_sidecar: BlobsSidecar) -> None:
    assert slot == blobs_sidecar.beacon_block_slot
    assert beacon_block_root == blobs_sidecar.beacon_block_root
    blobs = blobs_sidecar.blobs
    kzg_aggregated_proof = blobs_sidecar.kzg_aggregated_proof
    assert len(expected_kzg_commitments) == len(blobs)

    assert verify_aggregate_kzg_proof(blobs, expected_kzg_commitments, kzg_aggregated_proof)
```

#### `is_data_available`

The implementation of `is_data_available` will become more sophisticated during later sharding upgrades.
Initially, it requires every verifying actor to retrieve the matching `BlobsSidecar`,
and validate the sidecar with `validate_blobs_sidecar`.

The block MUST NOT be considered valid until a valid `BlobsSidecar` has been downloaded. Blocks that have been previously validated as available SHOULD be considered available even if the associated `BlobsSidecar` has subsequently been pruned.

```python
def is_data_available(slot: Slot, beacon_block_root: Root, blob_kzg_commitments: Sequence[KZGCommitment]) -> bool:
    # `retrieve_blobs_sidecar` is implementation and context dependent, raises an exception if not available.
    # Note: the p2p network does not guarantee sidecar retrieval outside of `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS`
    sidecar = retrieve_blobs_sidecar(slot, beacon_block_root)

    # For testing, `retrieve_blobs_sidecar` returns "TEST".
    # TODO: Remove it once we have a way to inject `BlobsSidecar` into tests.
    if isinstance(sidecar, str):
        return True

    validate_blobs_sidecar(slot, beacon_block_root, blob_kzg_commitments, sidecar)
    return True
```


#### `kzg_commitment_to_versioned_hash`

```python
def kzg_commitment_to_versioned_hash(kzg_commitment: KZGCommitment) -> VersionedHash:
    return VERSIONED_HASH_VERSION_KZG + hash(kzg_commitment)[1:]
```

#### `tx_peek_blob_versioned_hashes`

This function retrieves the hashes from the `SignedBlobTransaction` as defined in EIP-4844, using SSZ offsets.
Offsets are little-endian `uint32` values, as defined in the [SSZ specification](../../ssz/simple-serialize.md).
See [the full details of `blob_versioned_hashes` offset calculation](https://gist.github.com/protolambda/23bd106b66f6d4bb854ce46044aa3ca3).

```python
def tx_peek_blob_versioned_hashes(opaque_tx: Transaction) -> Sequence[VersionedHash]:
    assert opaque_tx[0] == BLOB_TX_TYPE
    message_offset = 1 + uint32.decode_bytes(opaque_tx[1:5])
    # field offset: 32 + 8 + 32 + 32 + 8 + 4 + 32 + 4 + 4 + 32 = 188
    blob_versioned_hashes_offset = (
        message_offset
        + uint32.decode_bytes(opaque_tx[(message_offset + 188):(message_offset + 192)])
    )
    return [
        VersionedHash(opaque_tx[x:(x + 32)])
        for x in range(blob_versioned_hashes_offset, len(opaque_tx), 32)
    ]
```

#### `verify_kzg_commitments_against_transactions`

```python
def verify_kzg_commitments_against_transactions(transactions: Sequence[Transaction],
                                                kzg_commitments: Sequence[KZGCommitment]) -> bool:
    all_versioned_hashes: List[VersionedHash] = []
    for tx in transactions:
        if tx[0] == BLOB_TX_TYPE:
            all_versioned_hashes += tx_peek_blob_versioned_hashes(tx)
    return all_versioned_hashes == [kzg_commitment_to_versioned_hash(commitment) for commitment in kzg_commitments]
```

## Beacon chain state transition function

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    if is_execution_enabled(state, block.body):
        process_withdrawals(state, block.body.execution_payload)
        process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE)  # [Modified in EIP-4844]
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
    process_blob_kzg_commitments(state, block.body)  # [New in EIP-4844]

    # New in EIP-4844
    assert is_data_available(block.slot, hash_tree_root(block), block.body.blob_kzg_commitments)
```

#### Execution payload

##### `process_execution_payload`

```python
def process_execution_payload(state: BeaconState, payload: ExecutionPayload, execution_engine: ExecutionEngine) -> None:
    # Verify consistency of the parent hash with respect to the previous execution payload header
    if is_merge_transition_complete(state):
        assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify the execution payload is valid
    assert execution_engine.notify_new_payload(payload)

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
        excess_data_gas=payload.excess_data_gas,  # [New in EIP-4844]
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
        withdrawals_root=hash_tree_root(payload.withdrawals),
    )
```

#### Blob KZG commitments

```python
def process_blob_kzg_commitments(state: BeaconState, body: BeaconBlockBody) -> None:
    # pylint: disable=unused-argument
    assert verify_kzg_commitments_against_transactions(body.execution_payload.transactions, body.blob_kzg_commitments)
```

## Testing

*Note*: The function `initialize_beacon_state_from_eth1` is modified for pure EIP-4844 testing only.

The `BeaconState` initialization is unchanged, except for the use of the updated `eip4844.BeaconBlockBody` type 
when initializing the first body-root.

```python
def initialize_beacon_state_from_eth1(eth1_block_hash: Hash32,
                                      eth1_timestamp: uint64,
                                      deposits: Sequence[Deposit],
                                      execution_payload_header: ExecutionPayloadHeader=ExecutionPayloadHeader()
                                      ) -> BeaconState:
    fork = Fork(
        previous_version=EIP4844_FORK_VERSION,  # [Modified in EIP-4844] for testing only
        current_version=EIP4844_FORK_VERSION,  # [Modified in EIP-4844]
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
