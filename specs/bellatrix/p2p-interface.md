# Bellatrix -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Bellatrix](#modifications-in-bellatrix)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
    - [Transitioning the gossip](#transitioning-the-gossip)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
  - [Gossipsub](#gossipsub)
    - [Why was the max gossip message size increased at Bellatrix?](#why-was-the-max-gossip-message-size-increased-at-bellatrix)
  - [Req/Resp](#reqresp)
    - [Why was the max chunk response size increased at Bellatrix?](#why-was-the-max-chunk-response-size-increased-at-bellatrix)
    - [Why allow invalid payloads on the P2P network?](#why-allow-invalid-payloads-on-the-p2p-network)

<!-- mdformat-toc end -->

## Introduction

This document contains the networking specification for Bellatrix.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite. This document should be viewed as additive to the documents from [Phase 0](../phase0/p2p-interface.md) and from [Altair](../altair/p2p-interface.md)
and will be referred to as the "Phase 0 document" and "Altair document" respectively, hereafter.
Readers should understand the Phase 0 and Altair documents and use them as a basis to understand the changes outlined in this document.

## Modifications in Bellatrix

### The gossip domain: gossipsub

Some gossip meshes are upgraded in Bellatrix to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.
All topics remain stable except the beacon block topic which is updated with the modified type.

The specification around the creation, validation, and dissemination of messages has not changed from the Phase 0 and Altair documents unless explicitly noted here.

The derivation of the `message-id` remains stable.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name           | Message Type                   |
| -------------- | ------------------------------ |
| `beacon_block` | `SignedBeaconBlock` (modified) |

Note that the `ForkDigestValue` path segment of the topic separates the old and the new `beacon_block` topics.

##### Global topics

Bellatrix changes the type of the global beacon block topic.

###### `beacon_block`

The *type* of the payload of this topic changes to the (modified) `SignedBeaconBlock` found in Bellatrix.
Specifically, this type changes with the addition of `execution_payload` to the inner `BeaconBlockBody`.
See Bellatrix [state transition document](./beacon-chain.md#beaconblockbody) for further details.

Blocks with execution enabled will be permitted to propagate regardless of the
validity of the execution payload. This prevents network segregation between
[optimistic](/sync/optimistic.md) and non-optimistic nodes.

In addition to the gossip validations for this topic from prior specifications,
the following validations MUST pass before forwarding the `signed_beacon_block` on the network.
Alias `block = signed_beacon_block.message`, `execution_payload = block.body.execution_payload`.

If the execution is enabled for the block -- i.e. `is_execution_enabled(state, block.body)`
then validate the following:

- _[REJECT]_ The block's execution payload timestamp is correct with respect to the slot
  -- i.e. `execution_payload.timestamp == compute_timestamp_at_slot(state, block.slot)`.
- If `execution_payload` verification of block's parent by an execution node is *not* complete:
  - _[REJECT]_ The block's parent (defined by `block.parent_root`) passes all
    validation (excluding execution node verification of the `block.body.execution_payload`).
- Otherwise:
  - _[IGNORE]_ The block's parent (defined by `block.parent_root`) passes all
    validation (including execution node verification of the `block.body.execution_payload`).

The following gossip validation from prior specifications MUST NOT be applied if the execution is
enabled for the block -- i.e. `is_execution_enabled(state, block.body)`:

- _[REJECT]_ The block's parent (defined by `block.parent_root`) passes validation.

#### Transitioning the gossip

See gossip transition details found in the [Altair document](../altair/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics.

### The Req/Resp domain

Non-faulty, [optimistic](/sync/optimistic.md) nodes may send blocks which
result in an INVALID response from an execution engine. To prevent network
segregation between optimistic and non-optimistic nodes, transmission of an
INVALID execution payload via the Req/Resp domain SHOULD NOT cause a node to be
down-scored or disconnected. Transmission of a block which is invalid due to
any consensus layer rules (i.e., *not* execution layer rules) MAY result in
down-scoring or disconnection.

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

Request and Response remain unchanged unless explicitly noted here.

Bellatrix fork-digest is introduced to the `context` enum to specify Bellatrix block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |

##### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

Request and Response remain unchanged.
Bellatrix fork-digest is introduced to the `context` enum to specify Bellatrix block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |

# Design decision rationale

### Gossipsub

#### Why was the max gossip message size increased at Bellatrix?

With the addition of `ExecutionPayload` to `BeaconBlock`s, there is a dynamic
field -- `transactions` -- which can validly exceed the `MAX_PAYLOAD_SIZE` limit (1 MiB) put in
place at Phase 0, so MAX_PAYLOAD_SIZE has increased to 10 MiB on the network.
At the `GAS_LIMIT` (~30M) currently seen on mainnet in 2021, a single transaction
filled entirely with data at a cost of 16 gas per byte can create a valid
`ExecutionPayload` of ~2 MiB. Thus we need a size limit to at least account for
current mainnet conditions.

Note, that due to additional size induced by the `BeaconBlock` contents (e.g.
proposer signature, operations lists, etc) this does reduce the
theoretical max valid `ExecutionPayload` (and `transactions` list) size as
slightly lower than 10 MiB. Considering that `BeaconBlock` max size is on the
order of 128 KiB in the worst case and the current gas limit (~30M) bounds max blocksize to less
than 2 MiB today, this marginal difference in theoretical bounds will have zero
impact on network functionality and security.

### Req/Resp

#### Why was the max chunk response size increased at Bellatrix?

Similar to the discussion about the maximum gossip size increase, the
`ExecutionPayload` type can cause `BeaconBlock`s to exceed the 1 MiB bounds put
in place during Phase 0.

As with the gossip limit, 10 MiB is selected because this is firmly above any
valid block sizes in the range of gas limits expected in the medium term.

As with both gossip and req/rsp maximum values, type-specific limits should
always by simultaneously respected.

#### Why allow invalid payloads on the P2P network?

The specification allows blocks with invalid execution payloads to propagate across
gossip and via RPC calls. The reasoning for this is as follows:

1. Optimistic nodes must listen to block gossip to obtain a view of the head of
   the chain.
2. Therefore, optimistic nodes must propagate gossip blocks. Otherwise, they'd
   be censoring.
3. If optimistic nodes will propagate blocks via gossip, then they must respond
   to requests for the parent via RPC.
4. Therefore, optimistic nodes must send optimistic blocks via RPC.

So, to prevent network segregation from optimistic nodes inadvertently sending
invalid execution payloads, nodes should never downscore/disconnect nodes due to such invalid
payloads. This does open the network to some DoS attacks from invalid execution
payloads, but the scope of actors is limited to validators who can put those
payloads in valid (and slashable) beacon blocks. Therefore, it is argued that
the DoS risk introduced in tolerable.

More complicated schemes are possible that could restrict invalid payloads from
RPC. However, it's not clear that complexity is warranted.
