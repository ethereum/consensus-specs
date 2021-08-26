# The Merge -- Networking

This document contains the networking specification for the Merge.

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

The *type* of the payload of this topic changes to the (modified) `SignedBeaconBlock` found in the Merge.
Specifically, this type changes with the addition of `execution_payload` to the inner `BeaconBlockBody`.
See the Merge [state transition document](./beacon-chain.md#beaconblockbody) for further details.

In addition to the gossip validations for this topic from prior specifications,
the following validations MUST pass before forwarding the `signed_beacon_block` on the network.
Alias `block = signed_beacon_block.message`, `execution_payload = block.body.execution_payload`.
- If the merge is complete with respect to the head state -- i.e. `is_merge_complete(state)` --
  then validate the following:
  - _[REJECT]_ The block's execution payload must be non-empty --
    i.e. `execution_payload != ExecutionPayload()`
- If the execution is enabled for the block -- i.e. `is_execution_enabled(state, block.body)`
  then validate the following:
  - _[REJECT]_ The block's execution payload timestamp is correct with respect to the slot
    -- i.e. `execution_payload.timestamp == compute_time_at_slot(state, block.slot)`.
  - _[REJECT]_ Gas used is less than the gas limit --
    i.e. `execution_payload.gas_used <= execution_payload.gas_limit`.
  - _[REJECT]_ The execution payload block hash is not equal to the parent hash --
    i.e. `execution_payload.block_hash != execution_payload.parent_hash`.
  - _[REJECT]_ The execution payload transaction list data is within expected size limits,
    the data MUST NOT be larger than the SSZ list-limit,
    and a client MAY be more strict.

*Note*: Additional [gossip validations](https://github.com/ethereum/devp2p/blob/master/caps/eth.md#block-encoding-and-validity)
(see block "data validity" conditions) that rely more heavily on execution-layer state and logic are currently under consideration.

### Transitioning the gossip

See gossip transition details found in the [Altair document](../altair/p2p) for
details on how to handle transitioning gossip topics for the Merge.

## The Req/Resp domain

### Messages

#### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

Request and Response remain unchanged.
The Merge fork-digest is introduced to the `context` enum to specify the Merge block type.

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
The Merge fork-digest is introduced to the `context` enum to specify the Merge block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type             |
| ------------------------ | -------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock` |
| `MERGE_FORK_VERSION`     | `merge.SignedBeaconBlock`  |
