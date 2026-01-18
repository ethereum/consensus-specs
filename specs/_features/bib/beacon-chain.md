# BIB -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Versioned hash versions](#versioned-hash-versions)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
- [Helpers](#helpers)
  - [Misc](#misc)
    - [`kzg_commitment_to_payload_blob_versioned_hash`](#kzg_commitment_to_payload_blob_versioned_hash)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution engine](#execution-engine)
    - [Engine APIs](#engine-apis)
      - [Modified `is_valid_versioned_hashes`](#modified-is_valid_versioned_hashes)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)
- [Block production](#block-production)
  - [Constructing `BeaconBlockBody`](#constructing-beaconblockbody)

<!-- mdformat-toc end -->

## Introduction

BIB (Block-In-Blobs) is a protocol upgrade that extends the PeerDAS scheme to
include execution payload data in "payload blobs".

Key changes:

- `blob_kzg_commitments` contains commitments for both payload blobs and blob
  transaction blobs
- `execution_payload_blobs_count` indicates the number of payload blob
  commitments (which come first)
- Payload transactions are chunked into 128 KiB payload blobs and committed via
  KZG
- Payload blob versioned hashes use `0x11` prefix (blob transaction blobs use
  `0x01`)
- The existing `expectedBlobVersionedHashes` Engine API parameter carries both
  types combined

*Note*: This specification is built upon [Fulu](../../fulu/beacon-chain.md).

## Custom types

No new custom types are introduced in BIB.

## Constants

### Versioned hash versions

| Name                                  | Value            | Description                                                                  |
| ------------------------------------- | ---------------- | ---------------------------------------------------------------------------- |
| `VERSIONED_HASH_VERSION_PAYLOAD_BLOB` | `Bytes1('0x11')` | *[New in BIB]* Version byte for payload blob commitments (type=1, version=1) |

*Note*: The first byte of a versioned hash uses the format `0xTV` where the high
nibble (`T`) indicates the data type and the low nibble (`V`) indicates the
commitment scheme version:

- `0x01` = Blob transaction blobs (type=0), KZG v1 (existing EIP-4844)
- `0x11` = Payload blobs (type=1), KZG v1 (new in BIB)

## Containers

### Modified containers

#### `BeaconBlockBody`

*Note*: `BeaconBlock` and `SignedBeaconBlock` types are updated indirectly.

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS_ELECTRA]
    attestations: List[Attestation, MAX_ATTESTATIONS_ELECTRA]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload: ExecutionPayload
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    execution_requests: ExecutionRequests
    # [New in BIB]
    execution_payload_blobs_count: uint64
```

## Helpers

### Misc

#### `kzg_commitment_to_payload_blob_versioned_hash`

```python
def kzg_commitment_to_payload_blob_versioned_hash(kzg_commitment: KZGCommitment) -> VersionedHash:
    """
    Convert a KZG commitment to a payload blob versioned hash.
    Uses VERSIONED_HASH_VERSION_PAYLOAD_BLOB (0x11) prefix instead of
    VERSIONED_HASH_VERSION_KZG (0x01) used for blob transaction blobs.
    """
    return VERSIONED_HASH_VERSION_PAYLOAD_BLOB + hash(kzg_commitment)[1:]
```

## Beacon chain state transition function

### Execution engine

#### Engine APIs

##### Modified `is_valid_versioned_hashes`

*Note*: The function `is_valid_versioned_hashes` is modified to validate both
blob transaction versioned hashes (`0x01`) and payload blob versioned hashes
(`0x11`).

```python
def is_valid_versioned_hashes(
    self: ExecutionEngine, new_payload_request: NewPayloadRequest
) -> bool:
    """
    Return ``True`` if and only if the versioned hashes in ``new_payload_request``
    match the expected combined list of:
    1. Payload blob versioned hashes (0x11 prefix)
    2. Blob transaction versioned hashes (0x01 prefix)

    The combined list is constructed by concatenating payload blob hashes first,
    then blob tx hashes.
    """
    ...
```

### Block processing

#### Execution payload

##### Modified `process_execution_payload`

*Note*: The function `process_execution_payload` is modified to construct
`versioned_hashes` from `blob_kzg_commitments`, using
`execution_payload_blobs_count` to select the correct versioned hash prefix:

- Commitments before `execution_payload_blobs_count` use `0x11` prefix (payload
  blobs)
- Commitments at or after `execution_payload_blobs_count` use `0x01` prefix
  (blob transaction blobs)

```python
def process_execution_payload(
    state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine
) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)

    # Verify combined commitments are under dynamic limit
    assert (
        len(body.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )

    # [New in BIB]
    # Verify execution payload blobs count is valid
    assert body.execution_payload_blobs_count <= len(body.blob_kzg_commitments)

    # [New in BIB]
    # Compute versioned hashes
    versioned_hashes = [
        kzg_commitment_to_payload_blob_versioned_hash(commitment)
        if idx < body.execution_payload_blobs_count
        else kzg_commitment_to_versioned_hash(commitment)
        for (idx, commitment) in enumerate(body.blob_kzg_commitments)
    ]

    # Verify the execution payload is valid
    assert execution_engine.verify_and_notify_new_payload(
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

## Block production

### Constructing `BeaconBlockBody`

When constructing a `BeaconBlockBody` for proposal, the block producer **MUST**:

1. Call `engine_getPayloadV6` to obtain the `ExecutionPayload` and
   `BlobsBundleV3` from EL
2. Set:
   - `blob_kzg_commitments = blobsBundle.commitments`
   - `execution_payload_blobs_count = blobsBundle.executionPayloadBlobsCount`

The `blobsBundle` data are distributed via the blob sidecar mechanism.
