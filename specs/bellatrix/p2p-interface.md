# Bellatrix -- Networking

This document contains the networking specification for the Bellatrix.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite. This document should be viewed as additive to the documents from [Phase 0](../phase0/p2p-interface.md) and from [Altair](../altair/p2p-interface.md)
and will be referred to as the "Phase 0 document" and "Altair document" respectively, hereafter.
Readers should understand the Phase 0 and Altair documents and use them as a basis to understand the changes outlined in this document.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

  - [Warning](#warning)
- [Modifications in Bellatrix](#modifications-in-bellatrix)
  - [Configuration](#configuration)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
    - [Transitioning the gossip](#transitioning-the-gossip)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
- [Design decision rationale](#design-decision-rationale)
  - [Gossipsub](#gossipsub)
    - [Why was the max gossip message size increased at Bellatrix?](#why-was-the-max-gossip-message-size-increased-at-bellatrix)
  - [Req/Resp](#reqresp)
    - [Why was the max chunk response size increased at Bellatrix?](#why-was-the-max-chunk-response-size-increased-at-bellatrix)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Warning

This document is currently illustrative for early Bellatrix testnets and some parts are subject to change.
Refer to the note in the [validator guide](./validator.md) for further details.

# Modifications in Bellatrix

## Configuration

This section outlines modifications constants that are used in this spec.

| Name | Value | Description |
|---|---|---|
| `GOSSIP_MAX_SIZE_BELLATRIX` | `10 * 2**20` (= 10,485,760, 10 MiB) | The maximum allowed size of uncompressed gossip messages starting at Bellatrix upgrade. |
| `MAX_CHUNK_SIZE_BELLATRIX` | `10 * 2**20` (= 10,485,760, 10 MiB) | The maximum allowed size of uncompressed req/resp chunked responses starting at Bellatrix upgrade. |

## The gossip domain: gossipsub

Some gossip meshes are upgraded in Bellatrix to support upgraded types.

### Topics and messages

Topics follow the same specification as in prior upgrades.
All topics remain stable except the beacon block topic which is updated with the modified type.

The specification around the creation, validation, and dissemination of messages has not changed from the Phase 0 and Altair documents unless explicitly noted here.

Starting at Bellatrix upgrade, each gossipsub [message](https://github.com/libp2p/go-libp2p-pubsub/blob/master/pb/rpc.proto#L17-L24)
has a maximum size of `GOSSIP_MAX_SIZE_BELLATRIX`.
Clients MUST reject (fail validation) messages that are over this size limit.
Likewise, clients MUST NOT emit or propagate messages larger than this limit.

The derivation of the `message-id` remains stable.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `beacon_block` | `SignedBeaconBlock` (modified) |

Note that the `ForkDigestValue` path segment of the topic separates the old and the new `beacon_block` topics.

#### Global topics

Bellatrix changes the type of the global beacon block topic.

##### `beacon_block`

The *type* of the payload of this topic changes to the (modified) `SignedBeaconBlock` found in Bellatrix.
Specifically, this type changes with the addition of `execution_payload` to the inner `BeaconBlockBody`.
See Bellatrix [state transition document](./beacon-chain.md#beaconblockbody) for further details.

In addition to the gossip validations for this topic from prior specifications,
the following validations MUST pass before forwarding the `signed_beacon_block` on the network.
Alias `block = signed_beacon_block.message`, `execution_payload = block.body.execution_payload`.
- If the execution is enabled for the block -- i.e. `is_execution_enabled(state, block.body)`
  then validate the following:
  - _[REJECT]_ The block's execution payload timestamp is correct with respect to the slot
    -- i.e. `execution_payload.timestamp == compute_timestamp_at_slot(state, block.slot)`.

### Transitioning the gossip

See gossip transition details found in the [Altair document](../altair/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for Bellatrix.

## The Req/Resp domain

### Messages

#### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

Request and Response remain unchanged unless explicitly noted here.

Starting at Bellatrix upgrade,
a global maximum uncompressed byte size of `MAX_CHUNK_SIZE_BELLATRIX` MUST be applied to all method response chunks
regardless of type specific bounds that *MUST* also be respected.

Bellatrix fork-digest is introduced to the `context` enum to specify Bellatrix block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[0]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type             |
| ------------------------ | -------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock` |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |

#### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

Request and Response remain unchanged.
Bellatrix fork-digest is introduced to the `context` enum to specify Bellatrix block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type             |
| ------------------------ | -------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock` |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |

# Design decision rationale

## Gossipsub

### Why was the max gossip message size increased at Bellatrix?

With the addition of `ExecutionPayload` to `BeaconBlock`s, there is a dynamic
field -- `transactions` -- which can validly exceed the `GOSSIP_MAX_SIZE` limit (1 MiB) put in place in
place at Phase 0. At the `GAS_LIMIT` (~30M) currently seen on mainnet in 2021, a single transaction
filled entirely with data at a cost of 16 gas per byte can create a valid
`ExecutionPayload` of ~2 MiB. Thus we need a size limit to at least account for
current mainnet conditions.

Geth currently has a [max gossip message size](https://github.com/ethereum/go-ethereum/blob/3ce9f6d96f38712f5d6756e97b59ccc20cc403b3/eth/protocols/eth/protocol.go#L49) of 10 MiB.
To support backward compatibility with this previously defined network limit,
we adopt `GOSSIP_MAX_SIZE_BELLATRIX` of 10 MiB for maximum gossip sizes at the
point of Bellatrix and beyond. Note, that clients SHOULD still reject objects
that exceed their maximum theoretical bounds which in most cases is less than `GOSSIP_MAX_SIZE_BELLATRIX`.

Note, that due to additional size induced by the `BeaconBlock` contents (e.g.
proposer signature, operations lists, etc) this does reduce the
theoretical max valid `ExecutionPayload` (and `transactions` list) size as
slightly lower than 10 MiB. Considering that `BeaconBlock` max size is on the
order of 128 KiB in the worst case and the current gas limit (~30M) bounds max blocksize to less
than 2 MiB today, this marginal difference in theoretical bounds will have zero
impact on network functionality and security.

## Req/Resp

### Why was the max chunk response size increased at Bellatrix?

Similar to the discussion about the maximum gossip size increase, the
`ExecutionPayload` type can cause `BeaconBlock`s to exceed the 1 MiB bounds put
in place during Phase 0.

As with the gossip limit, 10 MiB is selected because this is firmly below any
valid block sizes in the range of gas limits expected in the medium term.

As with both gossip and req/rsp maximum values, type-specific limits should
always by simultaneously respected.
