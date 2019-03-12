ETH 2.0 Networking Spec - Node Identification
===

# Abstract

This specification describes how Ethereum 2.0 nodes identify and address each other on the network.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL", NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED",  "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

# Specification

Clients use Ethereum Node Records (as described in [EIP-778](http://eips.ethereum.org/EIPS/eip-778)) to discover one another. Each ENR includes, among other things, the following keys:

- The node's IP.
- The node's TCP port.
- The node's public key.

For clients to be addressable, their ENR responses MUST contain all of the above keys. Client MUST verify the signature of any received ENRs, and disconnect from peers whose ENR signatures are invalid. Each node's public key MUST be unique.

The keys above are enough to construct a [multiaddr](https://github.com/multiformats/multiaddr) for use with the rest of the `libp2p` stack.

It is RECOMMENDED that clients set their TCP port to the default of `9000`.

## Peer ID Generation

The `libp2p` networking stack identifies peers via a "peer ID." Simply put, a node's Peer ID is the SHA2-256 `multihash` of the node's public key. `go-libp2p-crypto` contains the canonical implementation of how to hash `secp256k1` keys for use as a peer ID.

# See Also

- [multiaddr](https://github.com/multiformats/multiaddr)
- [multihash](https://multiformats.io/multihash/)
- [go-libp2p-crypto](https://github.com/libp2p/go-libp2p-crypto)
