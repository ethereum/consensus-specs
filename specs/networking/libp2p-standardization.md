# ETH 2.0 Networking Spec - Libp2p protocol standardization

# Abstract

Ethereum 2.0 clients use the libp2p protocol networking stack. This document
provides specifications for use of the libp2p framework in the context of an
Ethereum 2.0 client. More specifically it details the libp2p client protocols,
configuration and messaging formats.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL", NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED",  "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://tools.ietf.org/html/rfc2119).

*Note: This is not designed to be a complete RFC publication, rather an iterative
approach to reach consensus on the design of the Ethereum 2.0 libp2p networking
stack.*

# Terminology

* **Stream** - A two-way connection to a peer that has optionally negotiated
	stream-multiplexing with either Mplex or Yamux.
* **SubStream** - A two-way connection to peer that is dedicated to a specific
	protocol.
* **Protocol Id** - A byte string used in the libp2p framework to negotiate
	substreams for specific protocols.
* ** Close a (sub)stream** - Close the local end of a stream. I.e `stream.close()`.
* **Reset a (sub)stream** - Close both ends of a stream. I.e `stream.reset()`.


# Libp2p Components

## Transport

This section details the libp2p transport layer that underlies the
[protocols](#protocols) that are listed in this document.

Libp2p allows composition of multiple transports. Eth2.0 clients MUST support
TCP/IP and MAY support websockets and/or QUIC. Websockets are useful for implementations
running in the browser and therefore native clients would ideally support these
implementations by supporting websockets.

An ideal libp2p transport would therefore support both TCP/IP and websockets.

*Note: There is active development in libp2p to facilitate the
[QUIC](https://github.com/libp2p/go-libp2p-quic-transport) transport, which may
be adopted in the future.*

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

Secio is being deprecated. [Noise](https://noiseprotocol.org/noise.html) is
currently the most likely candidate to be adopted for Ethereum 2.0 clients in
the short term.

*Note: Secio is being deprecated in favour of [TLS
1.3](https://github.com/libp2p/specs/blob/master/tls/tls.md) or
[Noise](https://noiseprotocol.org/noise.html). It is our intention to
transition to use TLS 1.3 + QUIC in the long term.*


## Protocols

This section lists the necessary libp2p protocols required by Ethereum 2.0
running a libp2p network stack.

## Multistream-select

#### Protocol id: `/multistream/1.0.0`

Clients running libp2p MUST support the
[multistream-select](https://github.com/multiformats/multistream-select/)
protocol which allows clients to negotiate libp2p protocols establish streams
per protocol.

*Note: [multistream-2](https://github.com/libp2p/specs/pull/95) has been
drafted and once complete and stable, clients SHOULD adopt this.*

## Multiplexing

Libp2p allows clients to compose multiple multiplexing methods. Clients MUST
support [mplex](https://github.com/libp2p/specs/tree/master/mplex) and
MAY support [yamux](https://github.com/hashicorp/yamux/blob/master/spec.md)
(these can be composed).

**Mplex protocol id: `/mplex/6.7.0`**

**Yamux protocol id: `/yamux/1.0.0`**

## Gossipsub

#### Protocol id: `/eth2/beacon_chain/gossipsub/1.0.0/`

*Note: Parameters listed here are subject to a large-scale network feasibility
study*

The [Gossipsub](https://github.com/libp2p/specs/tree/master/pubsub/gossipsub)
protocol is used for block and attestation propagation across the
network. Clients MUST support this protocol.

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
Topic strings have form: `<TopicName>/<TopicEncoding>`. The `<TopicName>`
defines the type of data being sent on the topic and the `<TopicEncoding>`
defines how the data field of the message is encoded. (Further details can be
found in [Messages](#Messages)).

There are two main topics used to propagate attestations and beacon blocks to
all nodes on the network. Their `<TopicName>`'s are:

- `beacon_block` - This topic is used solely for propagating new
	beacon blocks to all nodes on the networks. Blocks are sent in their
	entirety. Clients who receive blocks on a topic SHOULD validate the block
	proposer signature before forwarding it across the network.
- `beacon_attestation`  - This topic is used to propagate
	aggregated attestations (in their entirety) to subscribing nodes (typically
	block proposers) to be included into future blocks. Attestations are
	aggregated in their respective subnets before publishing on this topic.

Shards are grouped into their own subnets (defined by a shard topic). The
number of shard subnets is defined via `SHARD_SUBNET_COUNT` and the shard
`shard_number % SHARD_SUBNET_COUNT` is assigned to the topic:
`shard{shard_number % SHARD_SUBNET_COUNT}_beacon_attestation`.

### Messages

*Note: The message format here is Eth2.0-specific*

Each Gossipsub
[Message](https://github.com/libp2p/go-libp2p-pubsub/blob/master/pb/rpc.proto#L17-L24)
has a maximum size of 512KB (estimated from expected largest uncompressed block
size). Clients SHOULD reject and MUST NOT send messages that are over this size limit.

The `data` field of a Gossipsub `Message` is the encoded object being sent
between peers. For the `beacon_block` topic,
this is a `beacon_block`. For the `beacon_attestation` topic, this is
an `attestation`.

#### Encodings

Topics are post-fixed with an encoding. Encodings define how the `data` field
of a Gossipsub `Message` is encoded. Implementations SHOULD support the
following encodings:

- `ssz` -  This is a temporary encoding used only for initial interop and
	testing. All objects are SSZ-encoded. Example: The beacon block topic
	string is:
	`beacon_block/ssz` and the `data` field of a Gossipsub `Message` is an
	ssz-encoded `BeaconBlock`.
- `ssz_snappy` - All objects are ssz-encoded and then compressed with `snappy`.
	Example: The beacon attestation topic string is: `beacon_attestation/ssz_snappy` 
	and  the `data` field of a Gossipsub `Message` is an `Attestation` that has
	been ssz-encoded then compressed with `snappy`.


## Discovery

Discovery Version 5
([discv5](https://github.com/ethereum/devp2p/blob/master/discv5/discv5.md))
is used for discovery. This protocol uses a UDP transport and specifies
its own encryption, IP-discovery and topic advertisement. Therefore, it has no
need to establish streams through `multistream-select`, rather, act
as a standalone implementation that feeds discovered peers/topics (ENR-records) as
`multiaddrs` into the libp2p service. The libp2p service subsequently forms
connections and streams with discovered peers.

The ENR for an Ethereum 2.0 client SHOULD contain the following
entries (exclusive of the sequence number and signature, which MUST be present
in an ENR):
- `secp256k1`: compressed secp256k1 publickey, 33 bytes.
- An IP address (IPv4 (`ip`) and/or IPv6 (`ip6`)).
- A TCP port (`tcp`) representing the local libp2p listening port.
- A UDP port (`udp`) representing the local discv5 listening port.

Specifications of these parameters can be found in the [ENR
Specification](http://eips.ethereum.org/EIPS/eip-778).

## Eth-2 RPC

*There is a specification for the [RPC Interface](./rpc-interface.md) in this
repository which has implementations for libp2p and non-libp2p client. This
section focuses solely on the libp2p specification and provides significant
libp2p-specific modifications - as suggested by @Zah.*


### Specification

#### Protocol Segregation

Each RPC message is segregated into it's own libp2p protocol id, which is a string of the form:

```
<ProtocolPrefix>/<MessageName>/<SchemaVersion>/<Encoding>
```

With:
* **ProtocolPrefix** -- the RPC messages are grouped into families identified
  by a shared LibP2P protocol name prefix. A conforming implementation is
  expected to support either all messages appearing within a family or none of
  them. In this case, we use `/eth2/beacon_chain/rpc`.
* **MessageName** -- each RPC request is identified by a name consisting of
English letters, digits and underscores (_).
* **SchemaVersion** -- a semantic version consisting of one or more numbers
  separated by dots (.). Each schema is versioned to facilitate backward and
  forward-compatibility when possible.
* **Encoding** -- while the schema defines the data types in more abstract
  terms, the encoding describes a specific representation of bytes that will be
  transmitted over the wire. See the [Encodings](#encodings) section, for
  further details.


This protocol segregation allows libp2p `multistream-select` to handle the
RPC-type, version and encoding negotiation before establishing the underlying
substreams.


#### Requests and Responses

Each request/response has a maximum byte size of `RPC_MAX_SIZE`. This exact
value is TBD.

Requests/Responses MUST be encoded such that a prefixed length (defined by the
encoding used) is provided. Clients SHOULD ensure the request/response size is
less than or equal to `RPC_MAX_SIZE`, if not, SHOULD reset the substream.

A receiver SHOULD decode the length-prefix and wait for the exact number of
bytes to be sent. Once received the requester closes the substream.

##### Request

A request is formed by initiating a connection with the protocol id matching
the desired request type, encoding and version. Once a successful substream is
negotiated, the request is sent with the matching encoding (see the
[Encoding](#encoding) section for further details).

Once a stream is negotiated, the requester SHOULD send the request within **3
seconds**.

The requester SHOULD then wait for a response on the negotiated stream for at
most **10 seconds**, before resetting the stream.

*Note: If a request does not require a response, such as with a `Goodbye`
message, the stream is closed instantly.*

##### Response

After a request has been received on a negotiated stream, the responder SHOULD
send a response within **10 seconds**.  A response consists of a **single-byte**
response code which determines the contents of the response.

It can have one of the following values

* 0: **Success** -- a normal response with contents matching the expected
  message schema and encoding specified in the request.
* 1: **InvalidRequest** -- The contents of the request are semantically
  invalid. The response content is a message with the `ErrorMessage` schema
  (described below).
* 2: **ServerError** -- The receiver encountered an error while processing the
  request. The response content is a message with the `ErrorMessage` schema
  (described below).

Some requests MAY use response codes above 128 to indicate alternative
request-specific responses.

The `ErrorMessage` schema is:
```
(error_message: String)
```

*Note that the String type is encoded as UTF-8 bytes when SSZ-encoded.*

A response therefore has the form:

```
+--------+--------+--------+--------+
| r_code |     encoded_response     |
+--------+--------+--------+--------+
```

Here `r_code` represents the 1-byte response code.

### Encodings

The `<Encoding>` section of a protocol id specifies the type of encoding that
will be sent/received on the negotiated stream. There are currently two
encodings that MAY be supported by clients (although clients MUST support at
least `ssz`):

* `ssz` - The contents are `SSZ` encoded (see [SSZ](#ssz-encoding) for further details).
* `ssz_snappy` - The contents are `SSZ` encoded and compressed with `snappy`.

#### SSZ Encoding

The [SSZ-Specification](../simple-serialize.md) outlines how objects are
SSZ-encoded. An SSZ-encoded object does not provide a length-prefix which is
required by the RPC to determine how many bytes to read and whether to close
the stream if the payload is too large. Therefore, a length-prefix is added.

RPC Protocols using the `ssz` encoding MUST prefix all requests/responses with
an unsigned varint (as specified by the [protobuf
docs](https://developers.google.com/protocol-buffers/docs/encoding#varints)).
Therefore, an arbitrary ssz-encoded RPC request/response looks like:

```
+--------+--------+--------+--------+--------+--------+
| unsigned_varint |   ssz_encoded_request/response    |
+--------+--------+--------+--------+--------+--------+
```

## RPC Message Specification

*Note: The following is mostly borrowed from the [RPC Interface](./rpc-interface.md)
specification with libp2p-specific modifications.*

### Hello

**Protocol ID:** `/eth/serenity/rpc/hello/1.0.0/<Encoding>`

**Content**:

```
(
    network_id: uint8
    chain_id: uint64
    finalized_root: bytes32
    finalized_epoch: uint64
    best_root: bytes32
    best_slot: uint64
)
```

Clients exchange `hello` messages upon connection, forming a two-phase
handshake. The first message the initiating client sends MUST be the `hello`
message. In response, the receiving client MUST respond with its own `hello`
message.

Clients SHOULD immediately disconnect from one another following the handshake
above under the following conditions:

1. If `network_id` belongs to a different chain, since the client
   definitionally cannot sync with this client.
2. If the `finalized_root` shared by the peer is not in the client's chain at
   the expected epoch. For example, if Peer 1 in the diagram below has `(root,
   epoch)` of `(A, 5)` and Peer 2 has `(B, 3)`, Peer 1 would disconnect because
   it knows that `B` is not the root in their chain at epoch 3:

```
              Root A

              +---+
              |xxx|  +----+ Epoch 5
              +-+-+
                ^
                |
              +-+-+
              |   |  +----+ Epoch 4
              +-+-+
Root B          ^
                |
+---+         +-+-+
|xxx+<---+--->+   |  +----+ Epoch 3
+---+    |    +---+
         |
       +-+-+
       |   |  +-----------+ Epoch 2
       +-+-+
         ^
         |
       +-+-+
       |   |  +-----------+ Epoch 1
       +---+
```

Once the handshake completes, the client with the higher `finalized_epoch` or
`best_slot` (if the clients have equal `finalized_epoch`s) SHOULD request
beacon block roots from its counterparty via `beacon_block_roots` (i.e. RPC
method `10`).

### Goodbye

**Protocol ID:** `/eth/serenity/rpc/goodbye/1.0.0/<Encoding>`

**Content:**

```
(
    reason: uint64
)
```

Client MAY send `goodbye` messages upon disconnection. The reason field MAY be
one of the following values:

- `1`: Client shut down.
- `2`: Irrelevant network.
- `3`: Fault/error.

Clients MAY define custom goodbye reasons as long as the value is larger than `1000`.

### RequestBeaconBlockRoots

**Protocol ID:** `/eth/serenity/rpc/beacon_block_roots/1.0.0/<Encoding>`

**Request Content**

```
(
    start_slot: uint64
    count: uint64
)
```

**Response Content:**

```
# BlockRootSlot
(
    block_root: bytes32
    slot: uint64
)

(
    roots: []BlockRootSlot
)
```

Requests a list of block roots and slots from the peer. The `count` parameter
MUST be less than or equal to `32768`. The slots MUST be returned in ascending
slot order.

### BeaconBlockHeaders

**Protocol ID:** `/eth/serenity/rpc/beacon_block_headers/1.0.0/<Encoding>`

**Request Content**

```
(
    start_root: HashTreeRoot
    start_slot: uint64
    max_headers: uint64
    skip_slots: uint64
    backward: bool
)
```

**Response Content:**

```
(
    headers: []BeaconBlockHeader
)
```

Requests beacon block headers from the peer starting from `(start_root,
start_slot)`. The response MUST contain no more than `max_headers` headers.
`skip_slots` defines the maximum number of slots to skip between blocks. For
example, requesting blocks starting at slots `2` a `skip_slots` value of `1`
would return the blocks at `[2, 4, 6, 8, 10]`. In cases where a slot is empty
for a given slot number, the closest previous block MUST be returned. For
example, if slot `4` were empty in the previous example, the returned array
would contain `[2, 3, 6, 8, 10]`. If slot three were further empty, the array
would contain `[2, 6, 8, 10]`—i.e. duplicate blocks MUST be collapsed. A
`skip_slots` value of `0` returns all blocks.

The function of the `skip_slots` parameter helps facilitate light client sync -
for example, in [#459](https://github.com/ethereum/eth2.0-specs/issues/459) -
and allows clients to balance the peers from whom they request headers. Clients
could, for instance, request every 10th block from a set of peers where each
peer has a different starting block in order to populate block data.

If `backward` is `true`, the response returns the blocks preceding the
`start_slot` so that the requested slot is the last in the response. For
example, a request with `start_slot` of `10` should return, the blocks `[...,
8, 9, 10]`.

### BeaconBlockBodies

**Protocol ID:** `/eth/serenity/rpc/beacon_block_bodies/1.0.0/<Encoding>`

**Request Content:**

```
(
    block_roots: []HashTreeRoot
)
```

**Response Content:**

```
(
    block_bodies: []BeaconBlockBody
)
```

Requests the `block_bodies` associated with the provided `block_roots` from the
peer. Responses MUST return `block_roots` in the order provided in the request.
If the receiver does not have a particular `block_root`, it must return a
zero-value `block_body` (i.e. a `block_body` container with all zero fields).

### BeaconChainState

*Note*: This section is preliminary, pending the definition of the data
structures to be transferred over the wire during fast sync operations.

**Protocol ID:** `/eth/serenity/rpc/beacon_chain_state/1.0.0/<Encoding>`

**Request Content:**

```
(
    hashes: []HashTreeRoot
)
```

**Response Content:** TBD

Requests contain the hashes of Merkle tree nodes that when merkleized yield the
block's `state_root`.

The response will contain the values that, when hashed, yield the hashes inside
the request body.
