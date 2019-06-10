ETH 2.0 Networking Spec - Libp2p standard protocols
===

# Abstract

Ethereum 2.0 clients plan to use the libp2p protocol networking stack for
mainnet release. This document aims to standardize the libp2p client protocols,
configuration and messaging formats.

# Libp2p Components 

## Transport

This section details the libp2p transport layer that underlies the
[protocols](#protocols) that are listed in this document.

Libp2p allows composition of multiple transports. Eth2.0 clients should support
TCP/IP and optionally websockets. Websockets are useful for implementations
running in the browser and therefore native clients would ideally support these implementations 
by supporting websockets.

An ideal libp2p transport would therefore support both TCP/IP and websockets.

*Note: There is active development in libp2p to facilitate the
[QUIC](https://github.com/libp2p/go-libp2p-quic-transport) transport, which may
be adopted in the future*

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

*Note: Secio is being deprecated in favour of [TLS
1.3](https://github.com/libp2p/specs/blob/master/tls/tls.md). It is our
intention to transition to use TLS 1.3 for encryption between nodes, rather
than Secio.*


## Protocols

This section lists the necessary libp2p protocols required by Ethereum 2.0
running a libp2p network stack.

## Multistream-select

#### Protocol id: `/multistream/1.0.0`

Clients running libp2p should support the
[multistream-select](https://github.com/multiformats/multistream-select/)
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

#### Protocol id: `/eth/serenity/gossipsub/1.0.0`

*Note: Parameters listed here are subject to a large-scale network feasibility
study*

The [Gossipsub](https://github.com/libp2p/specs/tree/master/pubsub/gossipsub)
protocol is used for block and attestation propagation across the
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

For Eth2.0 clients, topics are sent as `SHA2-256` hashes of the topic string.

There are two main topics used to propagate attestations and beacon blocks to
all nodes on the network.

- The `beacon_block` topic - This topic is used solely for propagating new
	beacon blocks to all nodes on the networks.
- The `beacon_attestation` topic - This topic is used to propagate
	aggregated attestations to subscribing nodes (typically block proposers) to
	be included into future blocks. Attestations are aggregated in their
	respective subnets before publishing on this topic.

Shards are grouped into their own subnets (defined by a shard topic). The
number of shard subnets is defined via `SHARD_SUBNET_COUNT` and the shard
`shard_number % SHARD_SUBNET_COUNT` is assigned to the topic:
`shard{shard_number % SHARD_SUBNET_COUNT}_attestation`.

### Messages

*Note: The message format here is Eth2.0-specific*

Each Gossipsub
[Message](https://github.com/libp2p/go-libp2p-pubsub/blob/master/pb/rpc.proto#L17-L24)
has a maximum size of 512KB (estimated from expected largest uncompressed block
size).

The `data` field of a Gossipsub `Message` is an SSZ-encoded object. For the `beacon_block` topic,
this is a `beacon_block`. For the `beacon_attestation` topic, this is
an `attestation`.

## Eth-2 RPC

#### Protocol Id: `/eth/serenity/beacon/rpc/1`

The [RPC Interface](./rpc-interface.md) is specified in this repository.

## Discovery

Discovery Version 5
([discv5](https://github.com/ethereum/devp2p/blob/master/discv5/discv5.md))
will be used for discovery. This protocol uses a UDP transport and specifies
its own encryption, ip-discovery and topic advertisement. Therefore, it has no
need to establish streams through `multistream-select`, rather, act
as a standalone implementation that feeds discovered peers/topics (ENR-records) as
`multiaddrs` into the libp2p service.
