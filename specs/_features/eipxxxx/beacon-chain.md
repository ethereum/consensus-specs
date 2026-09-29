# EIP-XXXX -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `InclusionListClaims`](#new-inclusionlistclaims)
- [Presets](#presets)
  - [Inclusion list claims](#inclusion-list-claims)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`InclusionListClaim`](#inclusionlistclaim)
  - [Modified containers](#modified-containers)
    - [`ExecutionPayloadBid`](#executionpayloadbid)
    - [`ExecutionPayloadEnvelope`](#executionpayloadenvelope)

<!-- mdformat-toc end -->

## Introduction

EIP-XXXX lets a builder claim, for an inclusion list transaction omitted from
its payload, the payload index at which the omission is evaluated. The builder
commits the claims in its bid and reveals them in the payload envelope. The
execution engine resolves the claims when it checks the inclusion list
constraints.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Types

### New `InclusionListClaims`

```python
class InclusionListClaims(List[InclusionListClaim]):
    """
    The inclusion list claims committed to by a payload bid.
    """

    LIMIT = MAX_INCLUSION_LIST_CLAIMS
```

## Presets

### Inclusion list claims

| Name                        | Value                     |
| --------------------------- | ------------------------- |
| `MAX_INCLUSION_LIST_CLAIMS` | `Uint64(2**10)` (= 1,024) |

## Containers

### New containers

#### `InclusionListClaim`

```python
class InclusionListClaim(Container):
    transaction_hash: Bytes32
    transaction_index: Uint64
```

### Modified containers

#### `ExecutionPayloadBid`

```python
class ExecutionPayloadBid(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=14)

    parent_block_hash: Hash32
    parent_block_root: Root
    block_hash: Hash32
    prev_randao: Bytes32
    fee_recipient: ExecutionAddress
    gas_limit: Uint64
    builder_index: BuilderIndex
    slot: Slot
    value: Gwei
    execution_payment: Gwei
    blob_kzg_commitments: BlobKZGCommitments
    execution_requests_root: Root
    inclusion_list_bits: InclusionListBits
    # [New in EIPXXXX]
    inclusion_claims_root: Root
```

#### `ExecutionPayloadEnvelope`

```python
class ExecutionPayloadEnvelope(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=6)

    payload: ExecutionPayload
    execution_requests: ExecutionRequests
    builder_index: BuilderIndex
    beacon_block_root: Root
    parent_beacon_block_root: Root
    # [New in EIPXXXX]
    inclusion_claims: InclusionListClaims
```
