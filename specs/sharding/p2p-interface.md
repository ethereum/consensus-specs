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

| Name                        | Value | Description                                                                      |
| --------------------------- | ----- | -------------------------------------------------------------------------------- |
| `SHARD_ROW_SUBNET_COUNT`    | `512` | The number of `shard_row_{subnet_id}` subnets used in the gossipsub protocol.    |
| `SHARD_COLUMN_SUBNET_COUNT` | `512` | The number of `shard_column_{subnet_id}` subnets used in the gossipsub protocol. |

## Gossip domain

### Topics and messages

Following the same scheme as the [Phase0 gossip topics](../phase0/p2p-interface.md#topics-and-messages), names and payload types are:

| Name                            | Message Type             |
|---------------------------------|--------------------------|
| `shard_row_{subnet_id}`         | `SignedShardSample`      |
| `shard_column_{subnet_id}`      | `SignedShardSample`      |

The [DAS network specification](./das-p2p.md) defines additional topics.

#### Shard sample subnets

Shard sample (row/column) subnets are used by builders to make their samples available as part of their intermediate block release after selection by beacon block proposers.

##### `shard_row_{subnet_id}`

Shard sample data, in the form of a `SignedShardSample` is published to the `shard_row_{subnet_id}` and `shard_column_{subnet_id}` subnets.

The following validations MUST pass before forwarding the `sample`.

- _[IGNORE]_ The `sample` is published 1 slot early or later (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. validate that `sample.slot <= current_slot + 1`
  (a client MAY queue future samples for propagation at the appropriate slot).
- _[IGNORE]_ The `sample` is new enough to still be processed --
  i.e. validate that `compute_epoch_at_slot(sample.slot) >= get_previous_epoch(state)`
- _[REJECT]_ The shard sample is for the correct subnet --
  i.e. `sample.row == subnet_id` for `shard_row_{subnet_id}` and `sample.column == subnet_id` for `shard_column_{subnet_id}`
- _[IGNORE]_ The sample is the first sample with valid signature received for the `(sample.builder, sample.slot, sample.row, sample.column)` combination.
- _[REJECT]_ The `sample.data` MUST NOT contain any point `x >= MODULUS`. Although it is a `uint256`, not the full 256 bit range is valid.
- _[REJECT]_ The validator defined by `sample.builder` exists and is slashable.
- _[REJECT]_ The sample signature, `sample.signature`, is valid for the builder --
  i.e. `bls.Verify(builder_pubkey, sample_signing_root, samplev.signature)`.
- _[REJECT]_ The sample is proposed by the expected `builder` for the sample's `slot`.
  i.e., the beacon block at `sample.slot - 1` according to the node's fork choise contains an `IntermediateBlockBid`
  with `intermediate_block_bid.validator_index == sample.builder`

