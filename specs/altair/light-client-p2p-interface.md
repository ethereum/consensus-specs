# Ethereum Altair Light Client P2P Interface

**Notice**: This document is a work-in-progress for researchers and implementers.

This document contains the networking specification for [minimal light client](./sync-protocol.md).
This document should be viewed as a patch to the [Altair networking specification](./p2p-interface.md).

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [LightClientUpdate](#lightclientupdate)
- [Server discovery](#server-discovery)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## The gossip domain: gossipsub

The `light_client_update` gossip topic is added to support a light client searching for latest block header information.

### Topics and messages

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `light_client_update` | `LightClientUpdate` |

Definitions of these new types can be found in the [sync-protocol](./sync-protocol.md#LightClientUpdate).


## The Req/Resp domain

### Messages

#### LightClientUpdate

**Protocol ID:** `/eth2/beacon_chain/req/skip-sync/1/`

Request Content:
```
(
  key: bytes32
)
```

Response Content:
```
(
  LightClientUpdate
)
```

The request key is the hash root of a SyncCommittee. This allows a light client to start with any trusted sync-committee root to skip sync to the latest sync-committee.


## Server discovery

[TODO]
- Note that if we simply use the same set of bootnodes as the set configured in BeaconChain, the majority of the discovered peers are not likely to support the gossip topic of the req/resp protocol defined in this document.
- If disv5 supports [topic advertisement](https://github.com/ethereum/devp2p/blob/master/discv5/discv5-theory.md#topic-advertisement), this could be used to discover a subnet of nodes that supports the light client protocol. 

