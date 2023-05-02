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
    - [Builder block bid](#builder-block-bid)
      - [`builder_block_bid`](#builder_block_bid)
    - [Shard sample subnets](#shard-sample-subnets)
      - [`shard_row_{subnet_id}`](#shard_row_subnet_id)

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

Following the same scheme as the [Phase0 gossip topics](../../phase0/p2p-interface.md#topics-and-messages), names and payload types are:

| Name                            | Message Type             |
|---------------------------------|--------------------------|
| `shard_row_{subnet_id}`         | `SignedShardSample`      |
| `shard_column_{subnet_id}`      | `SignedShardSample`      |
| `builder_block_bid`             | `BuilderBlockBid`        |

The [DAS network specification](../das/das-core.md) defines additional topics.

#### Builder block bid

##### `builder_block_bid`

- _[IGNORE]_ The `bid` is published 1 slot early or later (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. validate that `bid.slot <= current_slot + 1`
  (a client MAY queue future samples for propagation at the appropriate slot).
- _[IGNORE]_ The `bid` is for the current or next block
  i.e. validate that `bid.slot >= current_slot`
- _[IGNORE]_ The `bid` is the first `bid` valid bid for `bid.slot`, or the bid is at least 1% higher than the previous known `bid`
- _[REJECT]_ The validator defined by `bid.validator_index` exists and is slashable.
- _[REJECT]_ The bid signature, which is an Eth1 signature, needs to be valid and the address needs to contain enough Ether to cover the bid and the data gas base fee.

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
- _[REJECT]_ The `sample.data` MUST NOT contain any point `x >= BLS_MODULUS`. Although it is a `uint256`, not the full 256 bit range is valid.
- _[REJECT]_ The validator defined by `sample.builder` exists and is slashable.
- _[REJECT]_ The sample is proposed by the expected `builder` for the sample's `slot`.
  i.e., the beacon block at `sample.slot - 1` according to the node's fork choice contains an `IntermediateBlockBid`
  with `intermediate_block_bid.validator_index == sample.builder`
- _[REJECT]_ The sample signature, `sample.signature`, is valid for the builder --
  i.e. `bls.Verify(builder_pubkey, sample_signing_root, sample.signature)` OR `sample.signature == Bytes96(b"\0" * 96)` AND
  the sample verification `verify_sample` passes

