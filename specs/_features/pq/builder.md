# PQ -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Builder activities](#builder-activities)
  - [Constructing the `SignedExecutionPayloadBid`](#constructing-the-signedexecutionpayloadbid)
  - [Constructing the `SignedExecutionPayloadEnvelope`](#constructing-the-signedexecutionpayloadenvelope)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
builder" to implement PQ.

Builders sign with leanXMSS instead of BLS. A builder's private key, `privkey`,
is the 32-byte seed from which its XMSS key is derived. As for validators, an
XMSS key MUST NOT sign two different messages at the same leaf, because that
exposes the leaf and lets others forge signatures at it.

At the upgrade, each builder moves to `state.pq_builders` at the same index,
with the XMSS public key it registered with EIP-8483 using the builder role. A
builder without a registration is exited at the upgrade, and there is no way yet
to register an XMSS public key after it.

## Builder activities

### Constructing the `SignedExecutionPayloadBid`

*Note*: Every bid for a slot is signed at the same leaf. A builder MUST NOT sign
two different bids for the same slot, so it cannot raise a bid it has broadcast
or bid on more than one parent.

*Note*: Blobs are disabled in PQ, so `bid.blob_kzg_commitments` MUST be empty
and the payload MUST NOT contain blob transactions.

```python
def get_execution_payload_bid_signature(
    state: BeaconState,
    bid: ExecutionPayloadBid,
    # [Modified in PQ]
    privkey: Bytes32,
) -> XMSSSignature:
    domain = get_domain(state, DOMAIN_BEACON_BUILDER, compute_epoch_at_slot(bid.slot))
    signing_root = compute_signing_root(bid, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(bid.slot, LEAF_OFFSET_EXECUTION_PAYLOAD_BID)
    return xmss.Sign(privkey, leaf_index, signing_root)
```

### Constructing the `SignedExecutionPayloadEnvelope`

*Note*: The envelope is signed at the leaf of the slot of its beacon block,
which is `state.latest_block_header.slot` when `state` is the post-state of that
block. If the proposer includes the bid in two blocks, a builder signs an
envelope for at most one of them.

```python
def get_execution_payload_envelope_signature(
    state: BeaconState,
    envelope: ExecutionPayloadEnvelope,
    # [Modified in PQ]
    privkey: Bytes32,
) -> XMSSSignature:
    domain = get_domain(state, DOMAIN_BEACON_BUILDER, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(envelope, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(
        state.latest_block_header.slot, LEAF_OFFSET_EXECUTION_PAYLOAD_ENVELOPE
    )
    return xmss.Sign(privkey, leaf_index, signing_root)
```
