# Ethereum 2.0 Sharding -- Network specification

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
      - [`shard_block_{subnet_id}`](#shard_block_subnet_id)
    - [Global topics](#global-topics)
      - [`shard_header`](#shard_header)
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
| `SHARD_BLOCK_SUBNET_COUNT` | `64` | The number of `shard_block_{subnet_id}` subnets used in the gossipsub protocol. |

## Gossip domain

### Topics and messages

Following the same scheme as the [Phase0 gossip topics](../phase0/p2p-interface.md#topics-and-messages), names and payload types are:

| Name                             | Message Type              |
|----------------------------------|---------------------------|
| `shard_block_{subnet_id}`        | `SignedShardBlock`        |
| `shard_block_header`             | `SignedShardBlockHeader`  |
| `shard_proposer_slashing`        | `ShardProposerSlashing`   |

The [DAS network specification](./das-p2p.md) defines additional topics.

#### Shard block subnets

Shard block subnets are used by builders to make their blobs available after selection by shard proposers.

##### `shard_block_{subnet_id}`

Shard block data, in the form of a `SignedShardBlock` is published to the `shard_block_{subnet_id}` subnets.

```python
def compute_subnet_for_shard_block(state: BeaconState, slot: Slot, shard: Shard) -> uint64:
    """
    Compute the correct subnet for a shard blob publication.
    Note, this mimics compute_subnet_for_attestation().
    """
    committee_index = compute_committee_index_from_shard(state, slot, shard)
    committees_per_slot = get_committee_count_per_slot(state, compute_epoch_at_slot(slot))
    slots_since_epoch_start = Slot(slot % SLOTS_PER_EPOCH)
    committees_since_epoch_start = committees_per_slot * slots_since_epoch_start

    return uint64((committees_since_epoch_start + committee_index) % SHARD_BLOCK_SUBNET_COUNT)
```

The following validations MUST pass before forwarding the `signed_block` on the horizontal subnet or creating samples for it.

We define some aliases to the nested contents of `signed_block`:
```python
block: ShardBlock = signed_block.message
signed_blob: SignedShardBlob = block.signed_blob
blob: ShardBlob = signed_blob.message
```

- _[IGNORE]_ The `block` is not from a future slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. validate that `blob.slot <= current_slot`
  (a client MAY queue future blobs for processing at the appropriate slot).
- _[IGNORE]_ The `blob` is new enough to be still be processed --
  i.e. validate that `compute_epoch_at_slot(blob.slot) >= get_previous_epoch(state)`
- _[REJECT]_ The shard should have a committee at slot --
  i.e. validate that `compute_committee_index_from_shard(state, blob.slot, blob.shard)` doesn't raise an error
- _[REJECT]_ The shard blob is for the correct subnet --
  i.e. `compute_subnet_for_shard_block(state, blob.slot, blob.shard) == subnet_id`
- _[IGNORE]_ The block is the first block with valid signature received for the `(block.proposer_index, blob.slot, blob.shard)` combination.
- _[REJECT]_ The blob is not too large, the data MUST NOT be larger than the SSZ list-limit, and a client MAY be more strict.
- _[REJECT]_ The `blob.body.data` MUST NOT contain any point `p >= MODULUS`. Although it is a `uint256`, not the full 256 bit range is valid.
- _[REJECT]_ The block proposer signature, `signed_block.signature`, is valid with respect to the `proposer_index` pubkey.
- _[REJECT]_ The blob builder exists and has sufficient balance to back the fee payment.
- _[REJECT]_ The blob builder signature, `signed_blob.signature`, is valid with respect to the `builder_index` pubkey.
- _[REJECT]_ The block is proposed by the expected `proposer_index` for the block's slot
  in the context of the current shuffling (defined by `blob.body.beacon_block_root`/`slot`).
  If the `proposer_index` cannot immediately be verified against the expected shuffling,
  the block MAY be queued for later processing while proposers for the block's branch are calculated --
  in such a case _do not_ `REJECT`, instead `IGNORE` this message.

#### Global topics

There are two additional global topics for Sharding.

One is used to propagate shard block headers (`shard_block_header`) to all nodes on the network.
Another one is used to propagate shard proposer slashings (`shard_proposer_slashing`).

##### `shard_block_header`

Shard header data, in the form of a `SignedShardBlockHeader` is published to the global `shard_block_header` subnet.
Shard block headers select shard blob bids by builders, and should be timely to ensure builders can publish the full shard block timely.

The following validations MUST pass before forwarding the `signed_block_header` (with inner `message` as `header`) on the network.

We define some aliases to the nested contents of `signed_block_header`:
```python
block_header: ShardBlockHeader = signed_block_header.message
signed_blob_header: SignedShardBlobHeader = header.signed_blob_header
blob_header: ShardBlobHeader = signed_blob_header.message
```

- _[IGNORE]_ The header is not from a future slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. validate that `blob_header.slot <= current_slot`
  (a client MAY queue future headers for processing at the appropriate slot).
- _[IGNORE]_ The header is new enough to be still be processed --
  i.e. validate that `compute_epoch_at_slot(blob_header.slot) >= get_previous_epoch(state)`
- _[IGNORE]_ The header is the first header with valid signature received for the `(block_header.proposer_index, blob_header.slot, blob_header.shard)` combination.
- _[REJECT]_ The `shard` MUST have a committee at the `slot` --
  i.e. validate that `compute_committee_index_from_shard(state, blob_header.slot, blob_header.shard)` doesn't raise an error
- _[REJECT]_ The proposer signature, `signed_shard_block_header.signature`, is valid with respect to the `block_header.proposer_index` pubkey.
- _[REJECT]_ The header is proposed by the expected `proposer_index` for the block's slot
  in the context of the current shuffling (defined by `header.body_summary.beacon_block_root`/`slot`).
  If the `proposer_index` cannot immediately be verified against the expected shuffling,
  the block MAY be queued for later processing while proposers for the block's branch are calculated --
  in such a case _do not_ `REJECT`, instead `IGNORE` this message.


##### `shard_proposer_slashing`

Shard proposer slashings, in the form of `ShardProposerSlashing`, are published to the global `shard_proposer_slashing` topic.

The following validations MUST pass before forwarding the `shard_proposer_slashing` on to the network.
- _[IGNORE]_ The shard proposer slashing is the first valid shard proposer slashing received
  for the proposer with index `proposer_slashing.signed_reference_1.message.proposer_index`.
  The `slot` and `shard` are ignored, there are no per-shard slashings.
- _[REJECT]_ All of the conditions within `process_shard_proposer_slashing` pass validation.
