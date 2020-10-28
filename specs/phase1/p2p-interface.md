# Phase 1 Ethereum 2.0 networking specification

This document contains the Phase 1 networking specification for Ethereum 2.0 clients.

It consists of four main sections:

1. A specification of the network fundamentals.
2. A specification of the three network interaction *domains* of Eth2:
  (a) the gossip domain, (b) the discovery domain, and (c) the Req/Resp domain.
3. The rationale and further explanation for the design choices made in the previous two sections.
4. An analysis of the maturity/state of the libp2p features required by This
  spec across the languages in which Eth2 clients are being developed.


## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


  - [Prerequisites](#prerequisites)
- [Network fundamentals](#network-fundamentals)
- [Eth2 network interaction domains](#eth2-network-interaction-domains)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Prerequisites

This document is an extension of the [Phase 0 networking specification](../phase0/p2p-interface.md).
All behaviors and definitions defined in the Phase 0 doc carry over unless explicitly noted or overridden.

# Network fundamentals

This section outlines the specification for the networking stack in Ethereum 2.0 clients.

[Transport](../phase0/p2p-interface.md#transport),
[encryption and identification](../phase0/p2p-interface.md#encryption-and-identification),
[protocol negotation](../phase0/p2p-interface.md#protocol-negotation),
and [multiplexing](../phase0/p2p-interface.md#multiplexing)
are unchanged from Phase 0.

# Eth2 network interaction domains

[Configuration](../phase0/p2p-interface.md#configuration)
and [MetaData](../phase0/p2p-interface.md#metadata)
are unchanged from Phase 0.

## The gossip domain: gossipsub

The gossipsub protocol (v1.1) and [parameters](../phase0/p2p-interface.md#gossipsub-parameters)
specified (e.g. `D`, `fanout_ttl`, etc) are unchanged from Phase 0.

## Topics and messages

[Topic string structure, maximum gossip size, and `message-id`](../phase0/p2p-interface.md#topics-and-messages)
are unchanged from Phase 0.

_Note:_ `ForkDigestValue` changes due to the `current_fork_version` changing.
Nodes and validators must prepare topic subscriptions in advance of the fork to
retain gossip connectivity.

In addition to topics and message types defined in Phase 0, the following are added:

| Name                             | Message Type              |
|----------------------------------|---------------------------|
| `shard_block_{subnet_id}`        | `SignedShardBlock`        |
| `shard_transition_{subnet_id}`   | `ShardTransition`         |

_Note_: Previously defined topic `Name`s and message types from Phase 0 still exist,
but messages on the updated topic `ForkDigestValue` MUST be the correct _Phase 1_ types.

Clients MUST reject (fail validation) messages containing an incorrect type, or invalid payload.

