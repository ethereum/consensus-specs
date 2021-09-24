# Sharding -- Networking

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Misc](#misc)
- [Gossip domain](#gossip-domain)
  - [Topics and messages](#topics-and-messages)
    - [Shard blob subnets](#shard-blob-subnets)
      - [`shard_blob_{subnet_id}`](#shard_blob_subnet_id)
    - [Global topics](#global-topics)
      - [`shard_blob_header`](#shard_blob_header)
      - [`shard_blob_tx`](#shard_blob_tx)
      - [`shard_proposer_slashing`](#shard_proposer_slashing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->


## Introduction

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.
The adjustments and additions for Shards are outlined in this document.

## Constants

### Misc

| Name | Value | Description |
| ---- | ----- | ----------- |
| `SHARD_BLOB_SUBNET_COUNT` | `64` | The number of `shard_blob_{subnet_id}` subnets used in the gossipsub protocol. |
| `SHARD_TX_PROPAGATION_GRACE_SLOTS` | `4` | The number of slots for a late transaction to propagate |
| `SHARD_TX_PROPAGATION_BUFFER_SLOTS` | `8` | The number of slots for an early transaction to propagate |


## Gossip domain

### Topics and messages

Following the same scheme as the [Phase0 gossip topics](../phase0/p2p-interface.md#topics-and-messages), names and payload types are:

| Name                            | Message Type             |
|---------------------------------|--------------------------|
| `shard_blob_{subnet_id}`        | `SignedShardBlob`        |
| `shard_blob_header`             | `SignedShardBlobHeader`  |
| `shard_blob_tx`                 | `SignedShardBlobHeader`  |
| `shard_proposer_slashing`       | `ShardProposerSlashing`  |

The [DAS network specification](./das-p2p.md) defines additional topics.

#### Shard blob subnets

Shard blob subnets are used by builders to make their blobs available after selection by shard proposers.

##### `shard_blob_{subnet_id}`

Shard blob data, in the form of a `SignedShardBlob` is published to the `shard_blob_{subnet_id}` subnets.

```python
def compute_subnet_for_shard_blob(state: BeaconState, slot: Slot, shard: Shard) -> uint64:
    """
    Compute the correct subnet for a shard blob publication.
    Note, this mimics compute_subnet_for_attestation().
    """
    committee_index = compute_committee_index_from_shard(state, slot, shard)
    committees_per_slot = get_committee_count_per_slot(state, compute_epoch_at_slot(slot))
    slots_since_epoch_start = Slot(slot % SLOTS_PER_EPOCH)
    committees_since_epoch_start = committees_per_slot * slots_since_epoch_start

    return uint64((committees_since_epoch_start + committee_index) % SHARD_BLOB_SUBNET_COUNT)
```

The following validations MUST pass before forwarding the `signed_blob`,
on the horizontal subnet or creating samples for it. Alias `blob = signed_blob.message`.

- _[IGNORE]_ The `blob` is published 1 slot early or later (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. validate that `blob.slot <= current_slot + 1`
  (a client MAY queue future blobs for propagation at the appropriate slot).
- _[IGNORE]_ The `blob` is new enough to still be processed --
  i.e. validate that `compute_epoch_at_slot(blob.slot) >= get_previous_epoch(state)`
- _[REJECT]_ The shard blob is for an active shard --
  i.e. `blob.shard < get_active_shard_count(state, compute_epoch_at_slot(blob.slot))`
- _[REJECT]_ The `blob.shard` MUST have a committee at the `blob.slot` --
  i.e. validate that `compute_committee_index_from_shard(state, blob.slot, blob.shard)` doesn't raise an error
- _[REJECT]_ The shard blob is for the correct subnet --
  i.e. `compute_subnet_for_shard_blob(state, blob.slot, blob.shard) == subnet_id`
- _[IGNORE]_ The blob is the first blob with valid signature received for the `(blob.proposer_index, blob.slot, blob.shard)` combination.
- _[REJECT]_ The blob is not too large -- the data MUST NOT be larger than the SSZ list-limit, and a client MAY apply stricter bounds.
- _[REJECT]_ The `blob.body.data` MUST NOT contain any point `p >= MODULUS`. Although it is a `uint256`, not the full 256 bit range is valid.
- _[REJECT]_ The blob builder defined by `blob.builder_index` exists and has sufficient balance to back the fee payment.
- _[REJECT]_ The blob signature, `signed_blob.signature`, is valid for the aggregate of proposer and builder --
  i.e. `bls.FastAggregateVerify([builder_pubkey, proposer_pubkey], blob_signing_root, signed_blob.signature)`.
- _[REJECT]_ The blob is proposed by the expected `proposer_index` for the blob's `slot` and `shard`,
  in the context of the current shuffling (defined by the current node head state and `blob.slot`).
  If the `proposer_index` cannot immediately be verified against the expected shuffling,
  the blob MAY be queued for later processing while proposers for the blob's branch are calculated --
  in such a case _do not_ `REJECT`, instead `IGNORE` this message.

#### Global topics

There are three additional global topics for Sharding.

- `shard_blob_header`: co-signed headers to be included on-chain and to serve as a signal to the builder to publish full data.
- `shard_blob_tx`: builder-signed headers, also known as "data transaction".
- `shard_proposer_slashing`: slashings of duplicate shard proposals.

##### `shard_blob_header`

Shard header data, in the form of a `SignedShardBlobHeader` is published to the global `shard_blob_header` subnet.
Shard blob headers select shard blob bids by builders
and should be timely to ensure builders can publish the full shard blob before subsequent attestations.

The following validations MUST pass before forwarding the `signed_blob_header` on the network. Alias `header = signed_blob_header.message`.

- _[IGNORE]_ The `header` is published 1 slot early or later (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. validate that `header.slot <= current_slot + 1`
  (a client MAY queue future headers for propagation at the appropriate slot).
- _[IGNORE]_ The header is new enough to still be processed --
  i.e. validate that `compute_epoch_at_slot(header.slot) >= get_previous_epoch(state)`
- _[REJECT]_ The shard header is for an active shard --
  i.e. `header.shard < get_active_shard_count(state, compute_epoch_at_slot(header.slot))`
- _[REJECT]_ The `header.shard` MUST have a committee at the `header.slot` --
  i.e. validate that `compute_committee_index_from_shard(state, header.slot, header.shard)` doesn't raise an error.
- _[IGNORE]_ The header is the first header with valid signature received for the `(header.proposer_index, header.slot, header.shard)` combination.
- _[REJECT]_ The blob builder defined by `blob.builder_index` exists and has sufficient balance to back the fee payment.
- _[REJECT]_ The header signature, `signed_blob_header.signature`, is valid for the aggregate of proposer and builder --
  i.e. `bls.FastAggregateVerify([builder_pubkey, proposer_pubkey], blob_signing_root, signed_blob_header.signature)`.
- _[REJECT]_ The header is proposed by the expected `proposer_index` for the blob's `header.slot` and `header.shard`
  in the context of the current shuffling (defined by the current node head state and `header.slot`).
  If the `proposer_index` cannot immediately be verified against the expected shuffling,
  the blob MAY be queued for later processing while proposers for the blob's branch are calculated --
  in such a case _do not_ `REJECT`, instead `IGNORE` this message.

##### `shard_blob_tx`

Shard data-transactions in the form of a `SignedShardBlobHeader` are published to the global `shard_blob_tx` subnet.
These shard blob headers are signed solely by the blob-builder.

The following validations MUST pass before forwarding the `signed_blob_header` on the network. Alias `header = signed_blob_header.message`.

- _[IGNORE]_ The header is not propagating more than `SHARD_TX_PROPAGATION_BUFFER_SLOTS` slots ahead of time --
  i.e. validate that `header.slot <= current_slot + SHARD_TX_PROPAGATION_BUFFER_SLOTS`.
- _[IGNORE]_ The header is not propagating later than `SHARD_TX_PROPAGATION_GRACE_SLOTS` slots too late --
  i.e. validate that `header.slot + SHARD_TX_PROPAGATION_GRACE_SLOTS >= current_slot`
- _[REJECT]_ The shard header is for an active shard --
  i.e. `header.shard < get_active_shard_count(state, compute_epoch_at_slot(header.slot))`
- _[REJECT]_ The `header.shard` MUST have a committee at the `header.slot` --
  i.e. validate that `compute_committee_index_from_shard(state, header.slot, header.shard)` doesn't raise an error.
- _[IGNORE]_ The header is not stale -- i.e. the corresponding shard proposer has not already selected a header for `(header.slot, header.shard)`.
- _[IGNORE]_ The header is the first header with valid signature received for the `(header.builder_index, header.slot, header.shard)` combination.
- _[REJECT]_ The blob builder, define by `header.builder_index`, exists and has sufficient balance to back the fee payment.
- _[IGNORE]_ The header fee SHOULD be higher than previously seen headers for `(header.slot, header.shard)`, from any builder.
  Propagating nodes MAY increase fee increments in case of spam.
- _[REJECT]_ The header signature, `signed_blob_header.signature`, is valid for ONLY the builder --
  i.e. `bls.Verify(builder_pubkey, blob_signing_root, signed_blob_header.signature)`. The signature is not an aggregate with the proposer.
- _[REJECT]_ The header is designated for proposal by the expected `proposer_index` for the blob's `header.slot` and `header.shard`
  in the context of the current shuffling (defined by the current node head state and `header.slot`).
  If the `proposer_index` cannot immediately be verified against the expected shuffling,
  the blob MAY be queued for later processing while proposers for the blob's branch are calculated --
  in such a case _do not_ `REJECT`, instead `IGNORE` this message.

##### `shard_proposer_slashing`

Shard proposer slashings, in the form of `ShardProposerSlashing`, are published to the global `shard_proposer_slashing` topic.

The following validations MUST pass before forwarding the `shard_proposer_slashing` on to the network.
- _[IGNORE]_ The shard proposer slashing is the first valid shard proposer slashing received
  for the proposer with index `proposer_slashing.proposer_index`.
  The `proposer_slashing.slot` and `proposer_slashing.shard` are ignored, there are no repeated or per-shard slashings.
- _[REJECT]_ All of the conditions within `process_shard_proposer_slashing` pass validation.
