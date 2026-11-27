# EIP-8141 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `DependencyProof`](#new-dependencyproof)
- [Presets](#presets)
  - [Execution](#execution)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`ExecutionPayload`](#executionpayload)
- [Execution engine](#execution-engine)
  - [Engine APIs](#engine-apis)

<!-- mdformat-toc end -->

## Introduction

[EIP-8141](https://eips.ethereum.org/EIPS/eip-8141) frame transactions declare
claims whose witnesses are segregated from the transaction body. A block carries
the witnesses of all its claims in a single *dependency proof*, which is in
neither the execution block header nor the execution block body. The execution
layer hands it to the consensus layer in the execution payload, and the
execution block header commits to it through `dependency_proof_hash`. This
document appends the proof to the `ExecutionPayload` container.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Types

### New `DependencyProof`

```python
class DependencyProof(ByteList):
    """
    A serialized EIP-8141 dependency proof, opaque to the consensus layer.
    Empty when the payload's transactions declare no dependencies.
    """

    LIMIT = MAX_DEPENDENCY_PROOF_BYTES
```

## Presets

### Execution

| Name                         | Value                         | Description                                            |
| ---------------------------- | ----------------------------- | ------------------------------------------------------ |
| `MAX_DEPENDENCY_PROOF_BYTES` | `Uint64(2**23)` (= 8,388,608) | EIP-8141 `MAX_DEPENDENCY_PROOF_BYTES`, the proof limit |

## Containers

### Modified containers

#### `ExecutionPayload`

```python
class ExecutionPayload(ProgressiveContainer):
    # [Modified in EIP8141]
    ACTIVE_FIELDS = active_fields(width=20)

    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: LogsBloom
    prev_randao: Bytes32
    block_number: Uint64
    gas_limit: Uint64
    gas_used: Uint64
    timestamp: Uint64
    extra_data: ExtraData
    base_fee_per_gas: Uint256
    block_hash: Hash32
    transactions: Transactions
    withdrawals: Withdrawals
    blob_gas_used: Uint64
    excess_blob_gas: Uint64
    block_access_list: BlockAccessList
    slot_number: Uint64
    # [New in EIP8141]
    dependency_proof: DependencyProof
```

*Note*: The consensus layer does not parse or verify `dependency_proof`; it only
enforces the `MAX_DEPENDENCY_PROOF_BYTES` bound, which SSZ decoding already
does, and forwards the proof to the execution engine. `block_hash` commits to
it, since the execution block header carries `keccak256(dependency_proof)`.
Neither `ExecutionPayloadBid` nor `BeaconState` changes, since a bid commits to
the payload through `block_hash`.

## Execution engine

### Engine APIs

The behavior of `notify_new_payload` and `get_payload` is unchanged. For a
payload of this fork they use the Engine API method versions whose execution
payload carries `dependencyProof` (`engine_newPayloadV7` and
`engine_getPayloadV7` in the execution-apis Bogota specification), and
`payload.dependency_proof` is exchanged unchanged as `dependencyProof`.
