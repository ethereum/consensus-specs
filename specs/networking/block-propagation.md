ETH 2.0 Networking Spec - Data Propagation
===

# Abstract

This specification describes how data will be propagated ("gossiped") on the network among Ethereum 2.0 nodes.

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL”, NOT", “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in RFC 2119.

# Dependencies

This specification assumes familiarity with the [RPC Interface](./rpc-interface.md) and [Beacon Chain](../core/0_beacon-chain.md) specifications.

# Specification

## Pubsub

Ethereum 2.0 uses a publish/subscribe ("pubsub") construction to propagate information throughout the network. In pubsub applications, nodes tag the messages they send with a topic. Only the nodes interested in that topic will process the message. This allows nodes to decide for themselves which information they are interested in.

There are a variety of network-based pubsub implementations available. `libp2p` includes three: `floodsub`, `gossipsub`, and most recently `EpiSub`. `gossipsub` is currently the most likely implementation to be adopted as the official standard, however this may change as a result of performance testing. Given these conditions, **this specification makes no assumptions about the underlying pubsub implementation.**

## Shard Subnets

Topics involving single shards are mapped to "subnets." A shard's subnet is calculating by calculating `shard_number % SHARD_SUBNET_COUNT`. Grouping shards into subnets as described confers the following benefits:

- Shards using smaller amounts network traffic are grouped with shards with more network traffic, thus increasing the stability of the network by reducing the likelihood that less-used shards will be eclipsed.
- The existence of the `SHARD_SUBNET_COUNT` creates a quality-of-service parameter that we can tweak to ensure the health over the network.

We expect that over time `SHARD_SUBNET_COUNT` will be increased to equal the total number of shards.

## Encoding

Messages are serialized using SSZ unless otherwise noted.


## Propagated Data

### Beacon Blocks

**Topic:** `beacon/blocks`

**Body:**

```
(
	block_root: HashTreeRoot
)
```

Notifies interested nodes that a new beacon block has been created. Nodes are expected to use one of the RPC APIs (Method ID `12`, for example) to fill out the block header and block body.

### Attestations

**Topic:** `attestations/${subnet}`

**Body:** SSZ-serialized `Attestation` object. Note that the `Attestation` is not included in a container, and is passed over the wire directly.

Notifies interested nodes that a new Attestation has been created.
