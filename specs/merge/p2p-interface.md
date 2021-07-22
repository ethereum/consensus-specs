# Ethereum Merge networking specification

This document contains the networking specification for Ethereum 2.0 clients added during the Merge deployment.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite. This document should be viewed as additive to the documents from [Phase 0](../phase0/p2p-interface.md) and from [Altair](../altair/p2p-interface.md)
and will be referred to as the "Phase 0 document" and "Altair document" respectively, hereafter.
Readers should understand the Phase 0 and Altair documents and use them as a basis to understand the changes outlined in this document.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

  - [Warning](#warning)
- [Modifications in the Merge](#modifications-in-the-merge)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
    - [Transitioning the gossip](#transitioning-the-gossip)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Warning

This document is currently illustrative for early Merge testnets and some parts are subject to change.
Refer to the note in the [validator guide](./validator.md) for further details.

# Modifications in the Merge

## The gossip domain: gossipsub

Some gossip meshes are upgraded in the Merge to support upgraded types.

### Topics and messages

Topics follow the same specification as in prior upgrades.
All topics remain stable except the beacon block topic which is updated with the modified type.

The specification around the creation, validation, and dissemination of messages has not changed from the Phase 0 and Altair documents.

The derivation of the `message-id` remains stable.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `beacon_block` | `SignedBeaconBlock` (modified) |

Note that the `ForkDigestValue` path segment of the topic separates the old and the new `beacon_block` topics.

#### Global topics

The Merge changes the type of the global beacon block topic.

##### `beacon_block`

The existing specification for this topic does not change from prior upgrades,
but the type of the payload does change to the (modified) `SignedBeaconBlock` found in the Merge.
This type changes due to the addition of `execution_payload` to the inner `BeaconBlockBody`.

See the Merge [state transition document](./beacon-chain.md#beaconblockbody) for further details.

### Transitioning the gossip

See gossip transition details found in the [Altair document](../altair/p2p) for
details on how to handle transitioning gossip topics for the Merge.

## The Req/Resp domain

### Messages

#### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

Request and Response remain unchanged.
`MERGE_FORK_VERSION` is used as an additional `context` to specify the Merge block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[0]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type             |
| ------------------------ | -------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock` |
| `MERGE_FORK_VERSION`     | `merge.SignedBeaconBlock`  |

#### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

Request and Response remain unchanged.
`MERGE_FORK_VERSION` is used as an additional `context` to specify the Merge block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type             |
| ------------------------ | -------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock` |
| `MERGE_FORK_VERSION`     | `merge.SignedBeaconBlock`  |
