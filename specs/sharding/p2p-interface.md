# Ethereum 2.0 Sharding -- Network specification

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [New containers](#new-containers)
  - [ShardBlob](#shardblob)
  - [SignedShardBlob](#signedshardblob)
- [Gossip domain](#gossip-domain)
  - [Topics and messages](#topics-and-messages)
    - [Shard blobs: `shard_blob_{shard}`](#shard-blobs-shard_blob_shard)
    - [Shard header: `shard_header`](#shard-header-shard_header)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- /TOC -->

## Introduction

The specification of these changes continues in the same format as the [Phase0](../phase0/p2p-interface.md) and
[Altair](../altair/p2p-interface.md) network specifications, and assumes them as pre-requisite.
The adjustments and additions for Shards are outlined in this document.

## New containers

### ShardBlob

Network-only.

```python
class ShardBlob(Container):
    # Slot and shard that this blob is intended for
    slot: Slot
    shard: Shard
    # The actual data. Represented in header as data commitment and degree proof
    data: List[BLSPoint, POINTS_PER_SAMPLE * MAX_SAMPLES_PER_BLOCK]
```

Note that the hash-tree-root of the `ShardBlob` does not match the `ShardHeader`,
since the blob deals with full data, whereas the header includes the KZG commitment and degree proof instead.

### SignedShardBlob

Network-only.

```python
class SignedShardBlob(Container):
    message: ShardBlob
    # The signature, the message is the commitment on the blob
    signature: BLSSignature
```

## Gossip domain

### Topics and messages

Following the same scheme as the [Phase0 gossip topics](../phase0/p2p-interface.md#topics-and-messages), names and payload types are:

| Name                 | Message Type        |
| -------------------- | ------------------- |
| `shard_blob_{shard}` | `SignedShardBlob`   |
| `shard_header`       | `SignedShardHeader` |

The [DAS network specification](./das-p2p.md) defines additional topics.

#### Shard blobs: `shard_blob_{shard}`

Shard block data, in the form of a `SignedShardBlob` is published to the `shard_blob_{shard}` subnets.

The following validations MUST pass before forwarding the `signed_blob` (with inner `blob`) on the horizontal subnet or creating samples for it.

- _\[REJECT\]_ `blob.shard` MUST match the topic `{shard}` parameter. (And thus within valid shard index range)
- _\[IGNORE\]_ The `blob` is not from a future slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. validate that `blob.slot <= current_slot`
  (a client MAY queue future blobs for processing at the appropriate slot).
- _\[IGNORE\]_ The blob is the first blob with valid signature received for the proposer for the `(slot, shard)` combination.
- _\[REJECT\]_ As already limited by the SSZ list-limit, it is important the blob is well-formatted and not too large.
- _\[REJECT\]_ The `blob.data` MUST NOT contain any point `p >= MODULUS`. Although it is a `uint256`, not the full 256 bit range is valid.
- _\[REJECT\]_ The proposer signature, `signed_blob.signature`, is valid with respect to the `proposer_index` pubkey, signed over the SSZ output of `commit_to_data(blob.data)`.
- _\[REJECT\]_ The blob is proposed by the expected `proposer_index` for the blob's slot.

TODO: make double blob proposals slashable?

#### Shard header: `shard_header`

Shard header data, in the form of a `SignedShardHeader` is published to the global `shard_header` subnet.

TODO: validation conditions.
