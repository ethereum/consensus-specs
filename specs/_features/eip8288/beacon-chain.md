# EIP-8288 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `DependencyProof`](#new-dependencyproof)
- [Preset](#preset)
  - [Execution](#execution)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`ExecutionPayload`](#executionpayload)
- [Execution engine](#execution-engine)
  - [Engine APIs](#engine-apis)
    - [Modified `notify_new_payload`](#modified-notify_new_payload)
- [Dependency proof retention](#dependency-proof-retention)

<!-- mdformat-toc end -->

## Introduction

[EIP-8288](https://eips.ethereum.org/EIPS/eip-8288) lets frame transactions
declare dependencies that one recursive STARK per block, the *dependency proof*,
proves. The proof is in neither the execution block header nor the execution
block body. The execution layer hands it to the consensus layer in the execution
payload, and the execution block header commits to it through
`dependency_proof_hash`, next to `block_deps_hash`. This document appends the
proof to the `ExecutionPayload` container.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Types

### New `DependencyProof`

```python
class DependencyProof(ByteList):
    """
    A serialized EIP-8288 dependency proof: the recursive STARK proving every
    dependency the payload's transactions declare, empty when they declare
    none.
    """

    LIMIT = MAX_DEPENDENCY_PROOF_BYTES
```

## Preset

### Execution

| Name                         | Value                         | Description                                            |
| ---------------------------- | ----------------------------- | ------------------------------------------------------ |
| `MAX_DEPENDENCY_PROOF_BYTES` | `Uint64(2**20)` (= 1,048,576) | EIP-8288 `MAX_DEPENDENCY_PROOF_BYTES`, the proof limit |

## Containers

### Modified containers

#### `ExecutionPayload`

```python
class ExecutionPayload(ProgressiveContainer):
    # [Modified in EIP8288]
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
    # [New in EIP8288]
    dependency_proof: DependencyProof
```

*Note*: `block_hash` already commits to `dependency_proof`: the execution block
header carries `keccak256(dependency_proof)`. The consensus layer does not
verify the proof; the execution engine does, as part of
`verify_and_notify_new_payload`. Neither `ExecutionPayloadBid` nor `BeaconState`
changes, since a bid commits to the payload through `block_hash`.

## Execution engine

### Engine APIs

#### Modified `notify_new_payload`

`notify_new_payload` is unchanged in behavior. The `engine_newPayload` call it
makes for a payload of this fork uses the method version that carries
`dependencyProof` in the execution payload (`engine_newPayloadV7` in the
execution-apis Bogota specification), and the payload's `dependency_proof` is
sent unchanged as `dependencyProof`. An execution engine that cannot run the
proof verifier does not return `INVALID`; it returns `SYNCING` or an error, so
`verify_and_notify_new_payload` does not treat an unverified proof as an invalid
payload.

`engine_getPayload` for this fork returns the payload with `dependencyProof`
set; a block builder places it in `ExecutionPayloadEnvelope.payload` unchanged.

## Dependency proof retention

The full `dependency_proof` bytes are needed only to verify a payload.
Implementations MAY prune them from stored payloads and keep only
`hash_tree_root(payload.dependency_proof)`, which preserves the `hash_tree_root`
of the `ExecutionPayload` and therefore of the envelope. Implementations SHOULD
keep the full proof of every payload within the weak subjectivity period, so
that a node syncing by re-execution can obtain it, as the execution layer is
required to retain it for that period.
