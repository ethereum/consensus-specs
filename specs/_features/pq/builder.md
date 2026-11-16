# PQ -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Becoming a builder](#becoming-a-builder)
  - [Preregister](#preregister)
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

A builder signs each bid at a leaf reserved for bids, see
`is_builder_bid_leaf_index`. Its signer MUST use each of these leaves at most
once, for example by allocating them in increasing order, and its record of used
leaves must survive restarts and move with the key. A builder that runs out of
bid leaves exits and joins again with a new key.

At the upgrade, each builder that registered an XMSS public key with a builder
PQ registration request takes it in place of its BLS public key. A builder
without a registration has its balance withdrawn at the upgrade. A new builder
preregisters and then joins with a deposit instead, see
[Becoming a builder](#becoming-a-builder).

## Becoming a builder

### Preregister

A builder deposit carries no signature, so anyone who sees the first deposit for
a new XMSS public key before it is included could get in first with a builder
deposit of their own withdrawal credentials. To prevent this, a builder first
preregisters, binding its XMSS public key to its withdrawal credentials. It
signs the binding at a reserved leaf, one of the first `XMSS_RESERVED_LEAVES`
leaves, and submits it with the signature to the system contract, which verifies
the signature and emits a `BuilderPreregistrationRequest` without it. Its signer
MUST use each reserved leaf at most once.

The builder waits until its binding is in `state.builder_preregistrations`, then
submits its deposit before the binding's `expiry_slot`. If the binding is not
stored, a builder with the key may already exist, so the builder generates a new
key and preregisters that one instead.

To renew an expired binding, the builder resubmits the same request. To change
its binding, it generates a new key, since anyone can resubmit the old binding
once it expires.

### Submit deposit

After the upgrade, a builder deposit carries no signature. Its `pubkey` is
`XMSS_DEPOSIT_PREFIX`, 16 zero bytes, followed by the builder's XMSS public key,
and its `signature` is ignored. A deposit whose XMSS public key is already in
`state.builders` tops up that builder. While the key has an active builder
preregistration, a builder deposit for it is discarded unless its withdrawal
credentials match the binding.

*Note*: A builder deposit whose `pubkey` does not start with 16 zero bytes is
treated as a legacy deposit, so the builder it creates initiates its exit at
once.

### Exiting

A builder exit request names the builder the same way, by `XMSS_DEPOSIT_PREFIX`
followed by its XMSS public key.

## Builder activities

### Constructing the `SignedExecutionPayloadBid`

```python
def get_execution_payload_bid_signature(
    state: BeaconState,
    bid: ExecutionPayloadBid,
    # [Modified in PQ]
    privkey: Bytes32,
    # [New in PQ]
    leaf_index: Uint64,
) -> XMSSSignature:
    domain = compute_domain(
        DOMAIN_BEACON_BUILDER,
        compute_fork_version(compute_epoch_at_slot(bid.slot)),
        state.genesis_validators_root,
    )
    signing_root = compute_signing_root(bid, domain)
    # [Modified in PQ]
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
