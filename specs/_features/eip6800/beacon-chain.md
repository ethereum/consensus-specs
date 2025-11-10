# EIP6800 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Preset](#preset)
  - [Execution](#execution)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
  - [New containers](#new-containers)
    - [`SuffixStateDiff`](#suffixstatediff)
    - [`StemStateDiff`](#stemstatediff)
    - [`IPAProof`](#ipaproof)
    - [`VerkleProof`](#verkleproof)
    - [`ExecutionWitness`](#executionwitness)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [`process_execution_payload`](#process_execution_payload)
- [Testing](#testing)

<!-- mdformat-toc end -->

## Introduction

This upgrade adds transaction execution to the beacon chain as part of the
eip6800 upgrade.

## Custom types

| Name                      | SSZ equivalent | Description |
| ------------------------- | -------------- | ----------- |
| `BanderwagonGroupElement` | `Bytes32`      |             |
| `BanderwagonFieldElement` | `Bytes32`      |             |
| `Stem`                    | `Bytes31`      |             |

## Preset

### Execution

| Name                       | Value                      |
| -------------------------- | -------------------------- |
| `MAX_STEMS`                | `uint64(2**16)` (= 65,536) |
| `MAX_COMMITMENTS_PER_STEM` | `uint64(33)`               |
| `VERKLE_WIDTH`             | `uint64(2**8)` (= 256)     |
| `IPA_PROOF_DEPTH`          | `uint64(2**3)` (= 8)       |

## Containers

### Modified containers

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
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
    block_hash: Hash32
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
    blob_gas_used: uint64
    excess_blob_gas: uint64
    # [New in EIP6800]
    execution_witness: ExecutionWitness
```

#### `ExecutionPayloadHeader`

```python
class ExecutionPayloadHeader(Container):
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
    block_hash: Hash32
    transactions_root: Root
    withdrawals_root: Root
    blob_gas_used: uint64
    excess_data_gas: uint64
    # [New in EIP6800]
    execution_witness_root: Root
```

### New containers

#### `SuffixStateDiff`

```python
class SuffixStateDiff(Container):
    suffix: Bytes1
    current_value: Optional[Bytes32]
    new_value: Optional[Bytes32]
```

*Note*: on the Kaustinen testnet, `new_value` is omitted from the container.

#### `StemStateDiff`

*Note*: `suffix_diffs` is only valid if the list is sorted by suffixes.

```python
class StemStateDiff(Container):
    stem: Stem
    suffix_diffs: List[SuffixStateDiff, VERKLE_WIDTH]
```

#### `IPAProof`

```python
class IPAProof(Container):
    cl: Vector[BanderwagonGroupElement, IPA_PROOF_DEPTH]
    cr: Vector[BanderwagonGroupElement, IPA_PROOF_DEPTH]
    final_evaluation: BanderwagonFieldElement
```

#### `VerkleProof`

```python
class VerkleProof(Container):
    other_stems: List[Bytes31, MAX_STEMS]
    depth_extension_present: ByteList[MAX_STEMS]
    commitments_by_path: List[BanderwagonGroupElement, MAX_STEMS * MAX_COMMITMENTS_PER_STEM]
    d: BanderwagonGroupElement
    ipa_proof: IPAProof
```

#### `ExecutionWitness`

```python
class ExecutionWitness(Container):
    state_diff: List[StemStateDiff, MAX_STEMS]
    verkle_proof: VerkleProof
```

## Beacon chain state transition function

### Block processing

#### Execution payload

##### `process_execution_payload`

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
    # Verify commitments are under limit
    assert len(body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK

    # Compute list of versioned hashes
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments
    ]

    # Verify the execution payload is valid
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
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
        excess_data_gas=payload.excess_data_gas,
        # [New in EIP6800]
        execution_witness_root=hash_tree_root(payload.execution_witness),
    )
```

## Testing

TBD
