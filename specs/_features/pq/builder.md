# PQ -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Becoming a builder](#becoming-a-builder)
  - [Submit deposit](#submit-deposit)
  - [Exiting](#exiting)
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

At the upgrade, each builder that registered an XMSS public key with a builder
PQ registration request takes it in place of its BLS public key. A builder
without a registration has its balance withdrawn at the upgrade. A new builder
joins with a deposit instead, see [Submit deposit](#submit-deposit).

## Becoming a builder

### Submit deposit

After the upgrade, a builder deposit carries no signature. Its `pubkey` is
`XMSS_DEPOSIT_PREFIX`, 16 zero bytes, followed by the builder's XMSS public key,
and its `signature` is ignored. A deposit whose XMSS public key is already in
`state.builders` tops up that builder.

*Note*: A builder deposit whose `pubkey` does not start with 16 zero bytes is
treated as a legacy deposit, so the builder it creates initiates its exit at
once.

### Exiting

A builder exit request names the builder the same way, by `XMSS_DEPOSIT_PREFIX`
followed by its XMSS public key.

## Builder activities

### Constructing the `SignedExecutionPayloadBid`

*Note*: Every bid for a slot is signed at the same leaf. A builder MUST NOT sign
two different bids for the same slot, so it cannot raise a bid it has broadcast
or bid on more than one parent.

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
