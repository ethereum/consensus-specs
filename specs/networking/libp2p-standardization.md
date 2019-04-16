ETH 2.0 Networking Spec - Libp2p standard protocols
===

# Abstract

Ethereum 2.0 clients plan to use the libp2p protocol networking stack for
mainnet release. This document aims to standardize the libp2p client protocols,
configuration and messaging formats.

# Libp2p Protocols

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

There is one dedicated topic for propagating beacon blocks and aggregated
attestations across the network. This topic will have the string
`beacon_chain`. Each shard will have it's own topic allowing relevant parties
to subscribe to in order to receive local shard attestations. The shard topics are
prefixed with `shard` followed by the number of the shard. For example,
messages relating to shard 10, will have the topic string `shard10`.

### Messages

Messages sent across gossipsub are fixed-size length-prefixed byte arrays.
Each message has a maximum size of 512KB (estimated from expected largest uncompressed
block size).

The byte array is prefixed with a unsigned 64 bit length number encoded as an
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

The body of the message is an SSZ-encoded object representing either a
beacon block or attestation. The type of objected is determined via a prefixed
nibble. Currently there are two objects that are sent across the gossip
network. They are (with their corresponding nibble specification):

- `0x1`: Beacon block
- `0x2`: Attestation

The body therefore takes the form:
```
+--------------------------+
|       type nibble        |
+--------------------------+
|                          |
|    SSZ-encoded object    |
|                          |
+--------------------------+
```

## Eth-2 RPC

#### Protocol Id: `/eth/serenity/beacon/rpc/1`

The [RPC Interface](./rpc-interface.md) is specified in this repository.


## Identify

#### Protocol Id: `/ipfs/id/1.0.0` (to be updated to `/p2p/id/1.0.0`)

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

The discovery protocol to be determined.
