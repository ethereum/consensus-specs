# EIP-XXXX -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `GetPayloadResponse`](#modified-getpayloadresponse)
- [Builder activities](#builder-activities)
  - [Constructing the `SignedExecutionPayloadBid`](#constructing-the-signedexecutionpayloadbid)
  - [Constructing the `SignedExecutionPayloadEnvelope`](#constructing-the-signedexecutionpayloadenvelope)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
builder" to implement EIP-XXXX.

## Helpers

### Modified `GetPayloadResponse`

```python
@dataclass
class GetPayloadResponse:
    execution_payload: ExecutionPayload
    block_value: Uint256
    blobs_bundle: BlobsBundle
    execution_requests: Sequence[bytes]
    # [New in EIPXXXX]
    inclusion_list_claims: Sequence[InclusionListClaim]
```

## Builder activities

### Constructing the `SignedExecutionPayloadBid`

*Note*: The only change is to set `bid.inclusion_claims_root`.

1. Set `bid.inclusion_claims_root` to
   `hash_tree_root(InclusionListClaims(data=inclusion_list_claims))`, where
   `inclusion_list_claims` is the `inclusionListClaims` field returned by
   `engine_getPayloadV7`.

### Constructing the `SignedExecutionPayloadEnvelope`

*Note*: The only change is to set `envelope.inclusion_claims`.

1. Set `envelope.inclusion_claims` to the `InclusionListClaims` committed to by
   `bid.inclusion_claims_root`.
