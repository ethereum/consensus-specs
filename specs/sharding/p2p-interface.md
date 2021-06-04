# Ethereum 2.0 Sharding -- Network specification

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Misc](#misc)
- [New containers](#new-containers)
  - [ShardBlobBody](#shardblobbody)
  - [ShardBlob](#shardblob)
  - [SignedShardBlob](#signedshardblob)
- [Gossip domain](#gossip-domain)
  - [Topics and messages](#topics-and-messages)
    - [Shard blob subnets](#shard-blob-subnets)
      - [`shard_blob_{subnet_id}`](#shard_blob_subnet_id)
    - [Global topics](#global-topics)
      - [`shard_header`](#shard_header)
      - [`shard_proposer_slashing`](#shard_proposer_slashing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->


## Introduction

The specification of these changes continues in the same format as the [Phase0](../phase0/p2p-interface.md) and
[Altair](../altair/p2p-interface.md) network specifications, and assumes them as pre-requisite.
The adjustments and additions for Shards are outlined in this document.

## Constants

### Misc

| Name | Value | Description |
| ---- | ----- | ----------- |
| `SHARD_BLOB_SUBNET_COUNT` | `64` | The number of `shard_blob_{subnet_id}` subnets used in the gossipsub protocol. |

## New containers

### ShardBlobBody

```python
class ShardBlobBody(Container):
    # The actual data commitment
    commitment: DataCommitment
    # Proof that the degree < commitment.length
    degree_proof: BLSCommitment
    # The actual data. Should match the commitment and degree proof.
    data: List[BLSPoint, POINTS_PER_SAMPLE * MAX_SAMPLES_PER_BLOCK]
    # Latest block root of the Beacon Chain, before shard_blob.slot
    beacon_block_root: Root
```

The user MUST always verify the commitments in the `body` are valid for the `data` in the `body`.

### ShardBlob

```python
class ShardBlob(Container):
    # Slot and shard that this blob is intended for
    slot: Slot
    shard: Shard
    # Shard data with related commitments and beacon anchor
    body: ShardBlobBody
    # Proposer of the shard-blob
    proposer_index: ValidatorIndex
```

This is the expanded form of the `ShardBlobHeader` type.

### SignedShardBlob

```python
class SignedShardBlob(Container):
    message: ShardBlob
    signature: BLSSignature
```

## Gossip domain

### Topics and messages

Following the same scheme as the [Phase0 gossip topics](../phase0/p2p-interface.md#topics-and-messages), names and payload types are:

| Name                             | Message Type              |
|----------------------------------|---------------------------|
| `shard_blob_{subnet_id}`         | `SignedShardBlob`         |
| `shard_header`                   | `SignedShardBlobHeader`   |
| `shard_proposer_slashing`        | `ShardProposerSlashing`   |

The [DAS network specification](./das-p2p.md) defines additional topics.

#### Shard blob subnets

Shard blob subnets are used to propagate shard blobs to subsections of the network.

##### `shard_blob_{subnet_id}`

Shard block data, in the form of a `SignedShardBlob` is published to the `shard_blob_{subnet_id}` subnets.

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

The following validations MUST pass before forwarding the `signed_blob` (with inner `message` as `blob`) on the horizontal subnet or creating samples for it.
- _[IGNORE]_ The `blob` is not from a future slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. validate that `blob.slot <= current_slot`
  (a client MAY queue future blobs for processing at the appropriate slot).
- _[IGNORE]_ The `blob` is new enough to be still be processed --
  i.e. validate that `compute_epoch_at_slot(blob.slot) >= get_previous_epoch(state)`
- _[REJECT]_ The shard should have a committee at slot --
  i.e. validate that `compute_committee_index_from_shard(state, blob.slot, blob.shard)` doesn't raise an error
- _[REJECT]_ The shard blob is for the correct subnet --
  i.e. `compute_subnet_for_shard_blob(state, blob.slot, blob.shard) == subnet_id`
- _[IGNORE]_ The blob is the first blob with valid signature received for the `(blob.proposer_index, blob.slot, blob.shard)` combination.
- _[REJECT]_ As already limited by the SSZ list-limit, it is important the blob is well-formatted and not too large.
- _[REJECT]_ The `blob.body.data` MUST NOT contain any point `p >= MODULUS`. Although it is a `uint256`, not the full 256 bit range is valid.
- _[REJECT]_ The proposer signature, `signed_blob.signature`, is valid with respect to the `proposer_index` pubkey.
- _[REJECT]_ The blob is proposed by the expected `proposer_index` for the blob's slot
  in the context of the current shuffling (defined by `blob.body.beacon_block_root`/`slot`).
  If the `proposer_index` cannot immediately be verified against the expected shuffling,
  the block MAY be queued for later processing while proposers for the blob's branch are calculated --
  in such a case _do not_ `REJECT`, instead `IGNORE` this message.

#### Global topics

There are two additional global topics for Sharding, one is used to propagate shard blob headers (`shard_header`) to
all nodes on the network. Another one is used to propagate validator message (`shard_proposer_slashing`).

##### `shard_header`

Shard header data, in the form of a `SignedShardBlobHeader` is published to the global `shard_header` subnet.

The following validations MUST pass before forwarding the `signed_shard_blob_header` (with inner `message` as `header`) on the network.
- _[IGNORE]_ The `header` is not from a future slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. validate that `header.slot <= current_slot`
  (a client MAY queue future headers for processing at the appropriate slot).
- _[IGNORE]_ The `header` is new enough to be still be processed --
  i.e. validate that `compute_epoch_at_slot(header.slot) >= get_previous_epoch(state)`
- _[IGNORE]_ The header is the first header with valid signature received for the `(header.proposer_index, header.slot, header.shard)` combination.
- _[REJECT]_ The shard should have a committee at slot --
  i.e. validate that `compute_committee_index_from_shard(state, header.slot, header.shard)` doesn't raise an error
- _[REJECT]_ The proposer signature, `signed_shard_blob_header.signature`, is valid with respect to the `proposer_index` pubkey.
- _[REJECT]_ The header is proposed by the expected `proposer_index` for the block's slot
  in the context of the current shuffling (defined by `header.body_summary.beacon_block_root`/`slot`).
  If the `proposer_index` cannot immediately be verified against the expected shuffling,
  the block MAY be queued for later processing while proposers for the block's branch are calculated --
  in such a case _do not_ `REJECT`, instead `IGNORE` this message.


##### `shard_proposer_slashing`

Shard proposer slashings, in the form of `ShardProposerSlashing`, are published to the global `shard_proposer_slashing` topic.

The following validations MUST pass before forwarding the `shard_proposer_slashing` on to the network.
- _[IGNORE]_ The shard proposer slashing is the first valid shard proposer slashing received
  for the proposer with index `proposer_slashing.signed_header_1.message.proposer_index`.
  The `slot` and `shard` are ignored, there are no per-shard slashings.
- _[REJECT]_ All of the conditions within `process_shard_proposer_slashing` pass validation.
