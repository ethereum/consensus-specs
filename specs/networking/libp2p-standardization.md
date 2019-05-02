ETH 2.0 Networking Spec - Libp2p standard protocols
===

# Abstract

Ethereum 2.0 clients plan to use the libp2p protocol networking stack for
mainnet release. This document aims to standardize the libp2p client protocols,
configuration and messaging formats.

# Libp2p Protocols

## Transport

This section details the libp2p transport layer that underlies the
[protocols](#protocols) that are listed in this document.

Libp2p allows composition of multiple transports. Eth2.0 clients should support
TCP/IP and optionally websockets. Websockets are useful for implementations
running in the browser and therefore native clients would ideally support these implementations 
by supporting websockets.

An ideal libp2p transport would therefore be TCP/IP with a fallback to
websockets.

### Encryption

Libp2p currently offers [Secio](https://github.com/libp2p/specs/pull/106) which
can upgrade a transport which will then encrypt all future communication. Secio
generates a symmetric ephemeral key which peers use to encrypt their
communication. It can support a range of ciphers and currently supports key
derivation for elliptic curve-based public keys.

Current defaults are:
- Key agreement: `ECDH-P256` (also supports `ECDH-P384`)
- Cipher: `AES-128` (also supports `AES-256`, `TwofishCTR`)
- Digests: `SHA256` (also supports `SHA512`)


## Protocols

This section lists the necessary libp2p protocols required by Ethereum 2.0
running a libp2p network stack.

## Multistream-select

#### Protocol id: `/multistream/1.0.0`

Clients running libp2p should support the [multistream-select](https://github.com/multiformats/multistream-select/)
protocol which allows clients to negotiate libp2p protocols establish streams
per protocol.

## Multiplexing

Libp2p allows clients to compose multiple multiplexing methods. Clients should
support [mplex](https://github.com/libp2p/specs/tree/master/mplex) and
optionally [yamux](https://github.com/hashicorp/yamux/blob/master/spec.md)
(these can be composed).

**Mplex protocol id: `/mplex/6.7.0`**

**Yamux protocol id: `/yamux/1.0.0`**

## Gossipsub

#### Protocol id: `/meshsub/1.0.0`

*Note: Parameters listed here are subject to a large-scale network feasibility
study*

The [Gossipsub](https://github.com/libp2p/specs/tree/master/pubsub/gossipsub)
protocol will be used for block and attestation propagation across the
network.

### Configuration Parameters

Gossipsub has a number of internal configuration parameters which directly
effect the network performance.  Clients can implement independently, however
we aim to standardize these across clients to optimize the gossip network for
propagation times and message duplication. Current network-related defaults are:

```
(
	// The target number of peers in the overlay mesh network (D in the libp2p specs).
	mesh_size: 6
	// The minimum number of peers in the mesh network before adding more (D_lo in the libp2p specs).
	mesh_lo: 4
	// The maximum number of peers in the mesh network before removing some (D_high in the libp2p sepcs).
	mesh_high: 12
	// The number of peers to gossip to during a heartbeat (D_lazy in the libp2p sepcs).
	gossip_lazy: 6 // defaults to `mesh_size`
	// Time to live for fanout peers (seconds).
	fanout_ttl: 60
	// The number of heartbeats to gossip about.
	gossip_history: 3
	// Time between each heartbeat (seconds).
	heartbeat_interval: 1
)
```

### Topics

*The Go and Js implementations use string topics - This is likely to be
updated to topic hashes in later versions - https://github.com/libp2p/rust-libp2p/issues/473*

For Eth2.0 clients, topics will be sent as `SHA2-256` hashes of the topic string.

There are two main topics used to propagate attestations and beacon blocks to
all nodes on the network.

- The `beacon_block` topic - This topic is used solely for propagating new
	beacon blocks to all nodes on the networks.
- The `beacon_attestation` topic - This topic is used to propagate
	aggregated attestations to subscribing nodes (typically block proposers) to
	be included into future blocks. Attestations will be aggregated in their
	respective subnets before publishing on this topic.

Shards will be grouped into their own subnets (defined by a shard topic). The
number of shard subnets will be defined via `SHARD_SUBNET_COUNT` and the shard
`shard_number % SHARD_SUBNET_COUNT` will be assigned to the topic:
`shard{shard_number % SHARD_SUBNET_COUNT}`.

### Messages

#### Libp2p Specification

*This section simply outlines the data sent across the wire as specified by
libp2p - this section is aimed at gossipsub implementers to standardize their implementation of this protocol*

Libp2p raw gossipsub messages are sent across the wire as fixed-size length-prefixed byte arrays.

The byte array is prefixed with an unsigned 64 bit length number encoded as an
`unsigned varint` (https://github.com/multiformats/unsigned-varint). Gossipsub messages therefore take the form:
```
+--------------------------+
|     message length       |
+--------------------------+
|                          |
|       body (<1M)         |
|                          |
+--------------------------+
```

The body represents a protobuf-encoded [Message](https://github.com/libp2p/go-libp2p-pubsub/blob/master/pb/rpc.proto#L17-L24). 

In the following section we discuss the data being sent in the `data` field of
the protobuf gossipsub `Message`.

#### Eth2.0 Specifics

Each message has a maximum size of 512KB (estimated from expected largest uncompressed
block size).

The `data` that is sent in a Gossipsub message is an SSZ-encoded object. For the `beacon_block` topic,
this will be a `beacon_block`. For the `beacon_attestation` topic, this will be
an `attestation`.

## Eth-2 RPC

#### Protocol Id: `/eth/serenity/beacon/rpc/1`

The [RPC Interface](./rpc-interface.md) is specified in this repository.

## Identify

#### Protocol Id: `/ipfs/id/1.0.0` (to be updated to `/p2p/id/1.0.0`)

*To be updated to incorporate discv5*


The Identify protocol (defined in go - [identify-go](https://github.com/ipfs/go-ipfs/blob/master/core/commands/id.go) and rust [rust-identify](https://github.com/libp2p/rust-libp2p/blob/master/protocols/identify/src/lib.rs))
allows a node A to query another node B which information B knows about A. This also includes the addresses B is listening on.

This protocol allows nodes to discover addresses of other nodes to be added to
peer discovery. It further allows nodes to determine the capabilities of all it's connected
peers.

### Configuration Parameters

The protocol has two configurable parameters, which can be used to identify the
type of connecting node. Suggested format:
```
	version: `/eth/serenity/1.0.0`
	user_agent: <client name and version>
```

## Discovery

#### Protocol Id: `/eth/serenity/disc/1.0.0`

*To be updated to incorporate discv5*

The discovery protocol to be determined.
