# The Verge -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Preset](#preset)
  - [Execution](#execution)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
  - [New containers](#new-containers)
    - [`SuffixStateDiff`](#suffixstatediff)
    - [`StemStateDiff`](#stemstatediff)
    - [`IPAProof`](#ipaproof)
    - [`VerkleProof`](#verkleproof)
    - [`ExecutionWitness`](#executionwitness)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution engine](#execution-engine)
    - [`notify_new_payload`](#notify_new_payload)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [`process_execution_payload`](#process_execution_payload)
- [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This upgrade adds transaction execution to the beacon chain as part of the Verge upgrade.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `StateDiff` | `List[StemStateDiff, MAX_STEMS]` | Only valid if list is sorted by stems |
| `BandersnatchGroupElement` | `Bytes32` | |
| `BandersnatchFieldElement` | `Bytes32` | |
| `Stem` | `Bytes31` | |

## Preset

### Execution

| Name | Value |
| - | - |
| `MAX_STEMS` | `2**16` |
| `MAX_COMMITMENTS_PER_STEM` | `33` |
| `VERKLE_WIDTH` | `256` |
| `IPA_PROOF_DEPTH` | `8` |

## Containers

### Extended containers

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
    block_hash: Hash32  # Hash of execution block
    # Extra payload field
    execution_witness: ExecutionWitness
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
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
    block_hash: Hash32  # Hash of execution block
    transactions_root: Root
    # Extra payload fields
    execution_witness: ExecutionWitness
```

### New containers

#### `SuffixStateDiff`

```python
class SuffixStateDiff(Container):
    suffix: Byte

    # Null means not currently present
    current_value: Union[Null, Bytes32]

    # Null means value not updated
    new_value: Union[Null, Bytes32]
```

*Note*: on the Kaustinen testnet, `new_value` is ommitted from the container.

#### `StemStateDiff`

```python
class StemStateDiff(Container):
    stem: Stem
    # Valid only if list is sorted by suffixes
    suffix_diffs: List[SuffixStateDiff, VERKLE_WIDTH]
```

```python
# Valid only if list is sorted by stems
StateDiff = List[StemStateDiff, MAX_STEMS]
```

#### `IPAProof`

```python
class IpaProof(Container):
    C_L = Vector[BandersnatchGroupElement, IPA_PROOF_DEPTH]
    C_R = Vector[BandersnatchGroupElement, IPA_PROOF_DEPTH]
    final_evaluation = BandersnatchFieldElement
```

#### `VerkleProof`

```python
class VerkleProof(Container):
    other_stems: List[Bytes32, MAX_STEMS]
    depth_extension_present: List[uint8, MAX_STEMS]
    commitments_by_path: List[BandersnatchGroupElement, MAX_STEMS * MAX_COMMITMENTS_PER_STEM]
    D: BandersnatchGroupElement
    ipa_proof: IpaProof
```

#### `ExecutionWitness`

```python
class ExecutionWitness(container):
    state_diff: StateDiff
    verkle_proof: VerkleProof
```

## Beacon chain state transition function

### Block processing

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
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
        execution_witness=payload.execution_witness,
    )
```

## Testing

TBD