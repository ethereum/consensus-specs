# Overview

This document contains the network specification for Ethereum 2.0 clients.

It consists of four main sections:

1. A specification of the network fundamentals detailing the two network configurations: interoperability test network, and mainnet launch.
2. A specification of the three network interaction _domains_ of ETH2.0: (a) the gossip domain, (b) the discovery domain, \(c\) the Req/Resp domain.
3. The rationale and further explanation for the design choices made in the previous two sections.
4. An analysis of the maturity/state of the libp2p features required by this spec across the languages in which ETH 2.0 clients are being developed.

## Table of Contents

<!-- cmd: doctoc --maxlevel=2 p2p-interface.md -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Network Fundamentals](#network-fundamentals)
  - [Transport](#transport)
  - [Encryption and identification](#encryption-and-identification)
  - [Protocol Negotiation](#protocol-negotiation)
  - [Multiplexing](#multiplexing)
- [ETH2 network interaction domains](#eth2-network-interaction-domains)
  - [Constants](#constants)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [The discovery domain: discv5](#the-discovery-domain-discv5)
  - [The Req/Resp domain](#the-reqresp-domain)
- [Design Decision Rationale](#design-decision-rationale)
  - [Transport](#transport-1)
  - [Multiplexing](#multiplexing-1)
  - [Protocol Negotiation](#protocol-negotiation-1)
  - [Encryption](#encryption)
  - [Gossipsub](#gossipsub)
  - [Req/Resp](#reqresp)
  - [Discovery](#discovery)
  - [Compression/Encoding](#compressionencoding)
- [libp2p Implementations Matrix](#libp2p-implementations-matrix)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Network Fundamentals

This section outlines the specification for the networking stack in Ethereum 2.0 clients.

Sections that have differing parameters for mainnet launch and interoperability testing are split into subsections. Sections that are not split have the same parameters for interoperability testing as mainnet launch.

## Transport

Even though libp2p is a multi-transport stack (designed to listen on multiple simultaneous transports and endpoints transparently), we hereby define a profile for basic interoperability.

#### Interop

All implementations MUST support the TCP libp2p transport, and it MUST be enabled for both dialing and listening (i.e. outbound and inbound connections).

The libp2p TCP transport supports listening on IPv4 and IPv6 addresses (and on multiple simultaneously). Clients SHOULD allow the operator to configure the listen IP addresses and ports, including the addressing schemes (IPv4, IPv6).

To facilitate connectivity, and avert possible IPv6 routability/support issues, clients participating in the interoperability testnet MUST expose at least ONE IPv4 endpoint.

All listening endpoints must be publicly dialable, and thus not rely on libp2p circuit relay, AutoNAT or AutoRelay facilities.

Nodes operating behind a NAT, or otherwise undialable by default (e.g. container runtime, firewall, etc.), MUST have their infrastructure configured to enable inbound traffic on the announced public listening endpoint.

#### Mainnet

All requirements from the interoperability testnet apply, except for the IPv4 addressing scheme requirement.

At this stage, clients are licensed to drop IPv4 support if they wish to do so, cognizant of the potential disadvantages in terms of Internet-wide routability/support. Clients MAY choose to listen only on IPv6, but MUST retain capability to dial both IPv4 and IPv6 addresses.

Usage of circuit relay, AutoNAT or AutoRelay will be specifically re-examined closer to the time.

## Encryption and identification

#### Interop

[SecIO](https://github.com/libp2p/specs/tree/master/secio) with `secp256k1` identities will be used for initial interoperability testing.

The following SecIO parameters MUST be supported by all stacks:

-  Key agreement: ECDH-P256.
-  Cipher: AES-128.
-  Digest: SHA-256.

#### Mainnet

[Noise Framework](http://www.noiseprotocol.org/) handshakes will be used for mainnet. libp2p Noise support [is in the process of being standardised](https://github.com/libp2p/specs/issues/195) in the libp2p project.

Noise support will presumably include IX, IK and XX handshake patterns, and may rely on Curve25519 keys, ChaCha20 and Poly1305 ciphers, and SHA-256 as a hash function. These aspects are being actively debated in the referenced issue [ETH 2.0 implementers are welcome to comment and contribute to the discussion.]

## Protocol Negotiation

#### Interop

Connection-level and stream-level (see the rationale section below for explanations) protocol negotiation MUST be conducted using [multistream-select v1.0](https://github.com/multiformats/multistream-select/). Its protocol ID is: `/multistream/1.0.0`.

#### Mainnet

Clients MUST support [multistream-select 1.0](https://github.com/multiformats/multistream-select/) and MAY support [multiselect 2.0](https://github.com/libp2p/specs/pull/95). Depending on the number of clients that have implementations for multiselect 2.0 by mainnet, [multistream-select 1.0](https://github.com/multiformats/multistream-select/) may be phased out.

## Multiplexing

During connection bootstrapping, libp2p dynamically negotiates a mutually supported multiplexing method to conduct parallel conversations. This applies to transports that are natively incapable of multiplexing (e.g. TCP, WebSockets, WebRTC), and is omitted for capable transports (e.g. QUIC).

Two multiplexers are commonplace in libp2p implementations: [mplex](https://github.com/libp2p/specs/tree/master/mplex) and [yamux](https://github.com/hashicorp/yamux/blob/master/spec.md). Their protocol IDs are, respectively: `/mplex/6.7.0` and `/yamux/1.0.0`.

Clients MUST support [mplex](https://github.com/libp2p/specs/tree/master/mplex) and MAY support [yamux](https://github.com/hashicorp/yamux/blob/master/spec.md). If both are supported by the client, yamux must take precedence during negotiation. See the Rationale section of this document for tradeoffs.

# ETH2 network interaction domains

## Constants

This section outlines constants that are used in this spec.

- `RQRP_MAX_SIZE`: The max size of uncompressed req/resp messages that clients will allow.
 Value: TBD
- `GOSSIP_MAX_SIZE`: The max size of uncompressed gossip messages
 Value: 1MB (estimated from expected largest uncompressed block size).
- `SHARD_SUBNET_COUNT`: The number of shard subnets used in the gossipsub protocol.
 Value: TBD

## The gossip domain: gossipsub

Clients MUST support the [gossipsub](https://github.com/libp2p/specs/tree/master/pubsub/gossipsub) libp2p protocol.

**Protocol ID:** `/meshsub/1.0.0`

**Gossipsub Parameters**

*Note: Parameters listed here are subject to a large-scale network feasibility study.*

The following gossipsub parameters will be used:

- `D` (topic stable mesh target count): 6
- `D_low` (topic stable mesh low watermark): 4
- `D_high` (topic stable mesh high watermark): 12
- `D_lazy` (gossip target): 6
- `fanout_ttl` (ttl for fanout maps for topics we are not subscribed to but have published to, seconds): 60
- `gossip_advertise` (number of windows to gossip about): 3
- `gossip_history` (number of heartbeat intervals to retain message IDs): 5
- `heartbeat_interval` (frequency of heartbeat, seconds): 1

### Topics

Topics are plain UTF-8 strings, and are encoded on the wire as determined by protobuf (gossipsub messages are enveloped in protobuf messages).

Topic strings have form: `/eth2/TopicName/TopicEncoding`. This defines both the type of data being sent on the topic and how the data field of the message is encoded. (Further details can be found in [Messages](#Messages)).

There are two main topics used to propagate attestations and beacon blocks to all nodes on the network. Their `TopicName`'s are:

- `beacon_block` - This topic is used solely for propagating new beacon blocks to all nodes on the networks. Blocks are sent in their entirety. Clients who receive a block on this topic MUST validate the block proposer signature before forwarding it across the network.
- `beacon_attestation` - This topic is used to propagate aggregated attestations (in their entirety) to subscribing nodes (typically block proposers) to be included in future blocks. Similarly to beacon blocks, clients will be expected to perform some sort of validation before forwarding, but the precise mechanism is still TBD.

Additional topics are used to propagate lower frequency validator messages. Their `TopicName`’s are:

- `voluntary_exit` - This topic is used solely for propagating voluntary validator exits to proposers on the network. Voluntary exits are sent in their entirety. Clients who receive a voluntary exit on this topic MUST validate the conditions within `process_voluntary_exit` before forwarding it across the network.
- `proposer_slashing` - This topic is used solely for propagating proposer slashings to proposers on the network. Proposer slashings are sent in their entirety. Clients who receive a proposer slashing on this topic MUST validate the conditions within `process_proposer_slashing` before forwarding it across the network.
- `attester_slashing` - This topic is used solely for propagating attester slashings to proposers on the network. Attester slashings are sent in their entirety. Clients who receive an attester slashing on this topic MUST validate the conditions within `process_attester_slashing` before forwarding it across the network.

#### Interop

Unaggregated attestations from all shards are sent to the `beacon_attestation` topic.

#### Mainnet

Shards are grouped into their own subnets (defined by a shard topic). The number of shard subnets is defined via `SHARD_SUBNET_COUNT` and the shard `shard_number % SHARD_SUBNET_COUNT` is assigned to the topic: `shard{shard_number % SHARD_SUBNET_COUNT}_beacon_attestation`. Unaggregated attestations are sent to the subnet topic. Aggregated attestations are sent to the `beacon_attestation` topic.

### Messages

Each gossipsub [message](https://github.com/libp2p/go-libp2p-pubsub/blob/master/pb/rpc.proto#L17-L24) has a maximum size of `GOSSIP_MAX_SIZE`.

Clients MUST reject (fail validation) messages that are over this size limit. Likewise, clients MUST NOT emit or propagate messages larger than this limit.

The payload is carried in the `data` field of a gossipsub message, and varies depending on the topic:


| Topic                        | Message Type      |
|------------------------------|-------------------|
| beacon_block                 | BeaconBlock       |
| beacon_attestation           | Attestation       |
| shard{N}\_beacon_attestation | Attestation       |
| voluntary_exit               | VoluntaryExit     |
| proposer_slashing            | ProposerSlashing  |
| attester_slashing            | AttesterSlashing  |

Clients MUST reject (fail validation) messages containing an incorrect type, or invalid payload.

When processing incoming gossip, clients MAY descore or disconnect peers who fail to observe these constraints.

### Encodings

Topics are post-fixed with an encoding. Encodings define how the payload of a gossipsub message is encoded.

#### Interop

- `ssz` - All objects are SSZ-encoded. Example: The beacon block topic string is: `/beacon_block/ssz` and the data field of a gossipsub message is an ssz-encoded `BeaconBlock`.

#### Mainnet

- `ssz_snappy` - All objects are ssz-encoded and then compressed with snappy. Example: The beacon attestation topic string is: `/beacon_attestation/ssz_snappy` and the data field of a gossipsub message is an `Attestation` that has been ssz-encoded then compressed with snappy.

Implementations MUST use a single encoding. Changing an encoding will require coordination between participating implementations.

## The discovery domain: discv5

Discovery Version 5 ([discv5](https://github.com/ethereum/devp2p/blob/master/discv5/discv5.md)) is used for peer discovery, both in the interoperability testnet and mainnet.

`discv5` is a standalone protocol, running on UDP on a dedicated port, meant for peer discovery only. `discv5` supports self-certified, flexible peer records (ENRs) and topic-based advertisement, both of which are (or will be) requirements in this context.

### Integration into libp2p stacks

`discv5` SHOULD be integrated into the client’s libp2p stack by implementing an adaptor to make it conform to the [service discovery](https://github.com/libp2p/go-libp2p-core/blob/master/discovery/discovery.go) and [peer routing](https://github.com/libp2p/go-libp2p-core/blob/master/routing/routing.go#L36-L44) abstractions and interfaces (go-libp2p links provided).

Inputs to operations include peer IDs (when locating a specific peer), or capabilities (when searching for peers with a specific capability), and the outputs will be multiaddrs converted from the ENR records returned by the discv5 backend.

This integration enables the libp2p stack to subsequently form connections and streams with discovered peers.

### ENR structure

The Ethereum Node Record (ENR) for an Ethereum 2.0 client MUST contain the following entries (exclusive of the sequence number and signature, which MUST be present in an ENR):

-  The compressed secp256k1 publickey, 33 bytes (`secp256k1` field).
-  An IPv4 address (`ip` field) and/or IPv6 address (`ip6` field).
-  A TCP port (`tcp` field) representing the local libp2p listening port.
-  A UDP port (`udp` field) representing the local discv5 listening port.

Specifications of these parameters can be found in the [ENR Specification](http://eips.ethereum.org/EIPS/eip-778).

#### Interop

In the interoperability testnet, all peers will support all capabilities defined in this document (gossip, full Req/Resp suite, discovery protocol), therefore the ENR record does not need to carry ETH2 capability information, as it would be superfluous.

Nonetheless, ENRs MUST carry a generic `eth2` key with nil value, denoting that the peer is indeed a ETH2 peer, in order to eschew connecting to ETH1 peers.

#### Mainnet

On mainnet, ENRs MUST include a structure enumerating the capabilities offered by the peer in an efficient manner. The concrete solution is currently undefined. Proposals include using namespaced bloom filters mapping capabilities to specific protocol IDs supported under that capability.

### Topic advertisement

#### Interop

This feature will not be used in the interoperability testnet.

#### Mainnet

In mainnet, we plan to use discv5’s topic advertisement feature as a rendezvous facility for peers on shards (thus subscribing to the relevant gossipsub topics).

## The Req/Resp domain

### Protocol identification

Each message type is segregated into its own libp2p protocol ID, which is a case-sensitive UTF-8 string of the form:

```
/ProtocolPrefix/MessageName/SchemaVersion/Encoding
```

With:

- `ProtocolPrefix` - messages are grouped into families identified by a shared libp2p protocol name prefix. In this case, we use `/eth2/beacon_chain/req`.
- `MessageName` - each request is identified by a name consisting of English alphabet, digits and underscores (`_`).
- `SchemaVersion` - an ordinal version number (e.g. 1, 2, 3…) Each schema is versioned to facilitate backward and forward-compatibility when possible.
- `Encoding` - while the schema defines the data types in more abstract terms, the encoding strategy describes a specific representation of bytes that will be transmitted over the wire. See the [Encodings](#Encoding-strategies) section, for further details.

This protocol segregation allows libp2p `multistream-select 1.0` / `multiselect 2.0` to handle the request type, version and encoding negotiation before establishing the underlying streams.

### Req/Resp interaction

We use ONE stream PER request/response interaction. Streams are closed when the interaction finishes, whether in success or in error.

Request/response messages MUST adhere to the encoding specified in the protocol name, and follow this structure (relaxed BNF grammar):

```
request   ::= <encoding-dependent-header> | <encoded-payload>
response  ::= <result> | <encoding-dependent-header> | <encoded-payload>
result    ::= “0” | “1” | “2” | [“128” ... ”255”]
```

The encoding-dependent header may carry metadata or assertions such as the encoded payload length, for integrity and attack proofing purposes. It is not strictly necessary to length-prefix payloads, because req/resp streams are single-use, and stream closures implicitly delimit the boundaries, but certain encodings like SSZ do, for added security.

`encoded-payload` has a maximum byte size of `RQRP_MAX_SIZE`.

Clients MUST ensure the payload size is less than or equal to `RQRP_MAX_SIZE`, if not, they SHOULD reset the stream immediately. Clients tracking peer reputation MAY decrement the score of the misbehaving peer under this circumstance.

#### Requesting side

Once a new stream with the protocol ID for the request type has been negotiated, the full request message should be sent immediately. It should be encoded according to the encoding strategy.

The requester MUST close the write side of the stream once it finishes writing the request message - at this point, the stream will be half-closed.

The requester MUST wait a maximum of **5 seconds** for the first response byte to arrive (time to first byte – or TTFB – timeout). On that happening, the requester will allow further **10 seconds** to receive the full response.

If any of these timeouts fire, the requester SHOULD reset the stream and deem the req/resp operation to have failed.

#### Responding side

Once a new stream with the protocol ID for the request type has been negotiated, the responder must process the incoming request message according to the encoding strategy, until EOF (denoting stream half-closure by the requester).

The responder MUST:

1. Use the encoding strategy to read the optional header.
2. If there are any length assertions for length `N`, it should read exactly `N` bytes from the stream, at which point an EOF should arise (no more bytes). Should this is not the case, it should be treated as a failure.
3. Deserialize the expected type, and process the request.
4. Write the response (result, optional header, payload).
5. Close their write side of the stream. At this point, the stream will be fully closed.

If steps (1), (2) or (3) fail due to invalid, malformed or inconsistent data, the responder MUST respond in error. Clients tracking peer reputation MAY record such failures, as well as unexpected events, e.g. early stream resets.

The entire request should be read in no more than **5 seconds**. Upon a timeout, the responder SHOULD reset the stream.

The responder SHOULD send a response promptly, starting with a **single-byte** response code which determines the contents of the response (`result` particle in the BNF grammar above).

It can have one of the following values:

-  0: **Success** -- a normal response follows, with contents matching the expected message schema and encoding specified in the request.
-  1: **InvalidRequest** -- the contents of the request are semantically invalid, or the payload is malformed, or could not be understood. The response payload adheres to the `ErrorMessage` schema (described below).
-  2: **ServerError** -- the responder encountered an error while processing the request. The response payload adheres to the `ErrorMessage` schema (described below).

Clients MAY use response codes above `128` to indicate alternative, erroneous request-specific responses.

The range `[3, 127]` is RESERVED for future usages, and should be treated as error if not recognised expressly.

The `ErrorMessage` schema is:

```
(
  error_message: String
)
```

*Note that the String type is encoded as UTF-8 bytes when SSZ-encoded.*

A response therefore has the form:
```
  +--------+--------+--------+--------+--------+--------+
  | result |   header (opt)  |     encoded_response     |
  +--------+--------+--------+--------+--------+--------+
```
Here `result` represents the 1-byte response code.

### Encoding strategies

The token of the negotiated protocol ID specifies the type of encoding to be used for the req/resp interaction. Two values are possible at this time:

-  `ssz`: the contents are [SSZ](https://github.com/ethereum/eth2.0-specs/blob/192442be51a8a6907d6401dffbf5c73cb220b760/specs/networking/libp2p-standardization.md#ssz-encoding) encoded. This encoding type MUST be supported by all clients.
-  `ssz_snappy`: the contents are SSZ encoded, and subsequently compressed with [Snappy](https://github.com/google/snappy). MAY be supported in the interoperability testnet; and MUST be supported in mainnet.

#### SSZ encoding strategy (with or without Snappy)

The [SimpleSerialize (SSZ) specification](https://github.com/ethereum/eth2.0-specs/blob/192442be51a8a6907d6401dffbf5c73cb220b760/specs/simple-serialize.md) outlines how objects are SSZ-encoded. If the Snappy variant is selected, we feed the serialised form to the Snappy compressor on encoding. The inverse happens on decoding.

**Encoding-dependent header:** Req/Resp protocols using the `ssz` or `ssz_snappy` encoding strategies MUST prefix all encoded and compressed (if applicable) payloads with an unsigned [protobuf varint](https://developers.google.com/protocol-buffers/docs/encoding#varints).

Note that parameters defined as `[]VariableName` are SSZ-encoded containerless vectors.

### Messages

#### Hello

**Protocol ID:** ``/eth2/beacon_chain/req/hello/1/``

**Content**:
```
(
  fork_version: bytes4
  finalized_root: bytes32
  finalized_epoch: uint64
  head_root: bytes32
  head_slot: uint64
)
```
The fields are:

- `fork_version`: The beacon_state `Fork` version
- `finalized_root`: The latest finalized root the node knows about
- `finalized_epoch`: The latest finalized epoch the node knows about
- `head_root`: The block hash tree root corresponding to the head of the chain as seen by the sending node
- `head_slot`: The slot corresponding to the `head_root`.

Clients exchange hello messages upon connection, forming a two-phase handshake. The first message the initiating client sends MUST be the hello message. In response, the receiving client MUST respond with its own hello message.

Clients SHOULD immediately disconnect from one another following the handshake above under the following conditions:

1. If `fork_version` doesn’t match the local fork version, since the client’s chain is on another fork. `fork_version` can also be used to segregate testnets.
2. If the (`finalized_root`, `finalized_epoch`) shared by the peer is not in the client's chain at the expected epoch. For example, if Peer 1 sends (root, epoch) of (A, 5) and Peer 2 sends (B, 3) but Peer 1 has root C at epoch 3, then Peer 1 would disconnect because it knows that their chains are irreparably disjoint.

Once the handshake completes, the client with the lower `finalized_epoch` or `head_slot` (if the clients have equal `finalized_epoch`s) SHOULD request beacon blocks from its counterparty via the `BeaconBlocks` request.

#### Goodbye

**Protocol ID:** ``/eth2/beacon_chain/req/goodbye/1/``

**Content:**
```
(
  reason: uint64
)
```
Client MAY send goodbye messages upon disconnection. The reason field MAY be one of the following values:

- 1: Client shut down.
- 2: Irrelevant network.
- 3: Fault/error.

Clients MAY use reason codes above `128` to indicate alternative, erroneous request-specific responses.

The range `[4, 127]` is RESERVED for future usage.

#### BeaconBlocks

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks/1/`

Request Content
```
(
  head_block_root: HashTreeRoot
  start_slot: uint64
  count: uint64
  step: uint64
)
```

Response Content:
```
(
  blocks: []BeaconBlock
)
```

Requests count beacon blocks from the peer starting from `start_slot` on the chain defined by `head_block_root`. The response MUST contain no more than count blocks. `step` defines the slot increment between blocks. For example, requesting blocks starting at `start_slot` 2 with a step value of 2 would return the blocks at [2, 4, 6, …]. In cases where a slot is empty for a given slot number, no block is returned. For example, if slot 4 were empty in the previous example, the returned array would contain [2, 6, …]. A step value of 1 returns all blocks on the range `[start_slot, start_slot + count)`.

`BeaconBlocks` is primarily used to sync historical blocks.

Clients MUST support requesting blocks since the start of the weak subjectivity period and up to the given `head_block_root`.

Clients MUST support `head_block_root` values since the latest finalized epoch.

#### RecentBeaconBlocks

**Protocol ID:** `/eth2/beacon_chain/req/recent_beacon_blocks/1/`

Request Content:

```
(
  block_roots: []HashTreeRoot
)
```

Response Content:

```
(
  blocks: []BeaconBlock
)
```

Requests blocks by their block roots. The response is a list of `BeaconBlock` with the same length as the request. Blocks are returned in order of the request and any missing/unknown blocks are left empty (SSZ null `BeaconBlock`).

`RecentBeaconBlocks` is primarily used to recover recent blocks, for example when receiving a block or attestation whose parent is unknown.

Clients MUST support requesting blocks since the latest finalized epoch.

# Design Decision Rationale

## Transport

### Why are we defining specific transports?

libp2p peers can listen on multiple transports concurrently, and these can change over time. multiaddrs not only encode the address, but also the transport to be used to dial.

Due to this dynamic nature, agreeing on specific transports like TCP, QUIC or WebSockets on paper becomes irrelevant.

However, it is useful to define a minimum baseline for interoperability purposes.

### Can clients support other transports/handshakes than the ones mandated by the spec?

Clients may support other transports such as libp2p QUIC, WebSockets, and WebRTC transports, if available in the language of choice. While interoperability shall not be harmed by lack of such support, the advantages are desirable:

-  better latency, performance and other QoS characteristics (QUIC).
-  paving the way for interfacing with future light clients (WebSockets, WebRTC).

The libp2p QUIC transport inherently relies on TLS 1.3 per requirement in section 7 of the [QUIC protocol specification](https://tools.ietf.org/html/draft-ietf-quic-transport-22#section-7), and the accompanying [QUIC-TLS document](https://tools.ietf.org/html/draft-ietf-quic-tls-22).

The usage of one handshake procedure or the other shall be transparent to the ETH 2.0 application layer, once the libp2p Host/Node object has been configured appropriately.

### What are advantages of using TCP/QUIC/Websockets?

TCP is a reliable, ordered, full-duplex, congestion controlled network protocol that powers much of the Internet as we know it today. HTTP/1.1 and HTTP/2 run atop TCP.

QUIC is a new protocol that’s in the final stages of specification by the IETF QUIC WG. It emerged from Google’s SPDY experiment. The QUIC transport is undoubtedly promising. It’s UDP based yet reliable, ordered, reduces latency vs. TCP, is multiplexed, natively secure (TLS 1.3), offers stream-level and connection-level congestion control (thus removing head-of-line blocking), 0-RTT connection establishment, and endpoint migration, amongst other features. UDP also has better NAT traversal properties than TCP -- something we desperately pursue in peer-to-peer networks.

QUIC is being adopted as the underlying protocol for HTTP/3. This has the potential to award us censorship resistance via deep packet inspection for free. Provided that we use the same port numbers and encryption mechanisms as HTTP/3, our traffic may be indistinguishable from standard web traffic, and we may only become subject to standard IP-based firewall filtering -- something we can counteract via other mechanisms.

WebSockets and/or WebRTC transports are necessary for interaction with browsers, and will become increasingly important as we incorporate browser-based light clients to the ETH2 network.

### Why do we not just support a single transport?

Networks evolve. Hardcoding design decisions leads to ossification, preventing the evolution of networks alongside the state of the art. Introducing changes on an ossified protocol is very costly, and sometimes, downright impracticable without causing undesirable breakage.

Modelling for upgradeability and dynamic transport selection from the get-go lays the foundation for a future-proof stack.

Clients can adopt new transports without breaking old ones; and the multi-transport ability enables constrained and sandboxed environments (e.g. browsers, embedded devices) to interact with the network as first-class citizens via suitable/native transports (e.g. WSS), without the need for proxying or trust delegation to servers.

### Why are we not using QUIC for mainnet from the start?

The QUIC standard is still not finalised (at working draft 22 at the time of writing), and not all mainstream runtimes/languages have mature, standard, and/or fully-interoperable [QUIC support](https://github.com/quicwg/base-drafts/wiki/Implementations). One remarkable example is node.js, where the QUIC implementation is [in early development](https://github.com/nodejs/quic).

## Multiplexing

### Why are we using mplex/yamux?

[Yamux](https://github.com/hashicorp/yamux/blob/master/spec.md) is a multiplexer invented by Hashicorp that supports stream-level congestion control. Implementations exist in a limited set of languages, and it’s not a trivial piece to develop.

Conscious of that, the libp2p community conceptualised [mplex](https://github.com/libp2p/specs/blob/master/mplex/README.md) as a simple, minimal multiplexer for usage with libp2p. It does not support stream-level congestion control, and is subject to head-of-line blocking.

Overlay multiplexers are not necessary with QUIC, as the protocol provides native multiplexing, but they need to be layered atop TCP, WebSockets, and other transports that lack such support.

## Protocol Negotiation

### When is multiselect 2.0 due and why are we using it for mainnet?

multiselect 2.0 is currently being conceptualised. Debate started [on this issue](https://github.com/libp2p/specs/pull/95), but it got overloaded – as it tends to happen with large conceptual OSS discussions that touch the heart and core of a system.

In the following weeks (August 2019), there will be a renewed initiative to first define the requirements, constraints, assumptions and features, in order to lock in basic consensus upfront, to subsequently build on that consensus by submitting a specification for implementation.

We plan to use multiselect 2.0 for mainnet because it will:

1. Reduce round trips during connection bootstrapping and stream protocol negotiation.
2. Enable efficient one-stream-per-request interaction patterns.
3. Leverage *push data* mechanisms of underlying protocols to expedite negotiation.
4. Provide the building blocks for enhanced censorship resistance.

### What is the difference between connection-level and stream-level protocol negotiation?

All libp2p connections must be authenticated, encrypted, and multiplexed. Connections using network transports unsupportive of native authentication/encryption and multiplexing (e.g. TCP) need to undergo protocol negotiation to agree on a mutually supported:

1. authentication/encryption mechanism (such as SecIO, TLS 1.3, Noise).
2. overlay multiplexer (such as mplex, Yamux, spdystream).

In this specification, we refer to these two as *connection-level negotiations*. Transports supporting those features natively (such as QUIC) omit those negotiations.

After successfully selecting a multiplexer, all subsequent I/O happens over *streams*. When opening streams, peers pin a protocol to that stream, by conducting *stream-level protocol negotiation*.

At present, multistream-select 1.0 is used for both types of negotiation, but multiselect 2.0 will use dedicated mechanisms for connection bootstrapping process and stream protocol negotiation.

## Encryption

### Why are we using SecIO for interop? Why not for mainnet?

SecIO has been the default encryption layer for libp2p for years. It is used in IPFS and Filecoin. And although it will be superseded shortly, it is proven to work at scale.

SecIO is the common denominator across the various language libraries at this stage. It is widely implemented. That’s why we have chosen to use it for initial interop to minimize overhead in getting to a basic interoperability testnet.

We won’t be using it for mainnet because, amongst other things, it requires several round trips to be sound, and doesn’t support early data (0-RTT data), a mechanism that multiselect 2.0 will leverage to reduce round trips during connection bootstrapping.

SecIO is not considered secure for the purposes of this spec.

### Why are we using Noise/TLS 1.3 for mainnet?

Copied from the Noise Protocol Framework website:

> Noise is a framework for building crypto protocols. Noise protocols support mutual and optional authentication, identity hiding, forward secrecy, zero round-trip encryption, and other advanced features.

Noise in itself does not specify a single handshake procedure, but provides a framework to build secure handshakes based on Diffie-Hellman key agreement with a variety of tradeoffs and guarantees.

Noise handshakes are lightweight and simple to understand, and are used in major cryptographic-centric projects like WireGuard, I2P, Lightning. [Various](https://www.wireguard.com/papers/kobeissi-bhargavan-noise-explorer-2018.pdf) [studies](https://eprint.iacr.org/2019/436.pdf) have assessed the stated security goals of several Noise handshakes with positive results.

On the other hand, TLS 1.3 is the newest, simplified iteration of TLS. Old, insecure, obsolete ciphers and algorithms have been removed, adopting Ed25519 as the sole ECDH key agreement function. Handshakes are faster, 1-RTT data is supported, and session resumption is a reality, amongst other features.

Note that [TLS 1.3 is a prerequisite of the QUIC transport](https://tools.ietf.org/html/draft-ietf-quic-transport-22#section-7), although an experiment exists to integrate Noise as the QUIC crypto layer: [nQUIC](https://eprint.iacr.org/2019/028).

### Why are we using encryption at all?

Transport level encryption secures message exchange and provides properties that are useful for privacy, safety, and censorship resistance. These properties are derived from the following security guarantees that apply to the entire communication between two peers:

-  Peer authentication: the peer I’m talking to is really who they claim to be, and who I expect them to be.
-  Confidentiality: no observer can eavesdrop on the content of our messages.
-  Integrity: the data has not been tampered with by a third-party while in transit.
-  Non-repudiation: the originating peer cannot dispute that they sent the message.
-  Depending on the chosen algorithms and mechanisms (e.g. continuous HMAC), we may obtain additional guarantees, such as non-replayability (this byte could’ve only been sent *now;* e.g. by using continuous HMACs), or perfect forward secrecy (in the case that a peer key is compromised, the content of a past conversation will not be compromised).

Note that transport-level encryption is not exclusive of application-level encryption or cryptography. Transport-level encryption secures the communication itself, while application-level cryptography is necessary for the application’s use cases (e.g. signatures, randomness, etc.)

### Will mainnnet networking be untested when it launches?

Before launching mainnet, the testnet will be switched over to mainnet networking parameters, including Noise handshakes, and other new protocols. This gives us an opportunity to drill coordinated network upgrades and verifying that there are no significant upgradeability gaps.


## Gossipsub

### Why are we using a pub/sub algorithm for block and attestation propagation?

Pubsub is a technique to broadcast/disseminate data across a network rapidly. Such data is packaged in fire-and-forget messages that do not require a response from every recipient. Peers subscribed to a topic participate in the propagation of messages in that topic.

The alternative is to maintain a fully connected mesh (all peers connected to each other 1:1), which scales poorly (O(n^2)).

### Why are we using topics to segregate encodings, yet only support one encoding?

For future extensibility with almost zero overhead now (besides the extra bytes in the topic name).

### How do we upgrade gossip channels (e.g. changes in encoding, compression)?

Such upgrades lead to fragmentation, so they’ll need to be carried out in a coordinated manner most likely during a hard fork.

### Why are the topics strings and not hashes?

Topics names have a hierarchical structure. In the future, gossipsub may support wildcard subscriptions (e.g. subscribe to all children topics under a root prefix) by way of prefix matching. Enforcing hashes for topic names would preclude us from leveraging such features going forward.

No security or privacy guarantees are lost as a result of choosing plaintext topic names, since the domain is finite anyway, and calculating a digest's preimage would be trivial.

Furthermore, the ETH2 topic names are shorter their digest equivalents (assuming SHA-256 hash), so hashing topics would bloat messages unnecessarily.

### Why are there `SHARD_SUBNET_COUNT` subnets, and why is this not defined?

Depending on the number of validators, it may be more efficient to group shard subnets and might provide better stability for the gossipsub channel. The exact grouping will be dependent on more involved network tests. This constant allows for more flexibility in setting up the network topology for attestation aggregation (as aggregation should happen on each subnet).

### Why are we sending entire objects in the pubsub and not just hashes?

Entire objects should be sent to get the greatest propagation speeds. If only hashes are sent, then block and attestation propagation is dependent on recursive requests from each peer. In a hash-only scenario, peers could receive hashes without knowing who to download the actual contents from. Sending entire objects ensures that they get propagated through the entire network.

### Should clients gossip blocks if they *cannot* validate the proposer signature due to not yet being synced, not knowing the head block, etc?

The prohibition of unverified-block-gossiping extends to nodes that cannot verify a signature due to not being fully synced to ensure that such (amplified) DOS attacks are not possible.

### How are we going to discover peers in a gossipsub topic?

Via discv5 topics. ENRs should not be used for this purpose, as they store identity, location and capability info, not volatile advertisements.

In the interoperability testnet, all peers will be subscribed to all global beacon chain topics, so discovering peers in specific shard topics will be unnecessary.

## Req/Resp

### Why segregate requests into dedicated protocol IDs?

Requests are segregated by protocol ID to:

1. Leverage protocol routing in libp2p, such that the libp2p stack will route the incoming stream to the appropriate handler. This allows each the handler function for each request type to be self-contained. For an analogy, think about how you attach HTTP handlers to a REST API server.
2. Version requests independently. In a coarser-grained umbrella protocol, the entire protocol would have to be versioned even if just one field in a single message changed.
3. Enable clients to select the individual requests/versions they support. It would no longer be a strict requirement to support all requests, and clients, in principle, could support a subset of equests and variety of versions.
4. Enable flexibility and agility for clients adopting spec changes that impact the request, by signalling to peers exactly which subset of new/old requests they support.
5. Enable clients to explicitly choose backwards compatibility at the request granularity. Without this, clients would be forced to support entire versions of the coarser request protocol.
6. Parallelise RFCs (or ETH2 EIPs). By decoupling requests from one another, each RFC that affects the request protocol can be deployed/tested/debated independently without relying on a synchronisation point to version the general top-level protocol.
  1. This has the benefit that clients can explicitly choose which RFCs to deploy without buying into all other RFCs that may be included in that top-level version.
  2. Affording this level of granularity with a top-level protocol would imply creating as many variants (e.g. /protocol/43-{a,b,c,d,...}) as the cartesian product of RFCs inflight, O(n^2).
7. Allow us to simplify the payload of requests. Request-id’s and method-ids no longer need to be sent. The encoding/request type and version can all be handled by the framework.

CAVEAT: the protocol negotiation component in the current version of libp2p is called multistream-select 1.0. It is somewhat naïve and introduces overhead on every request when negotiating streams, although implementation-specific optimizations are possible to save this cost. Multiselect 2.0 will remove this overhead by memoizing previously selected protocols, and modelling shared protocol tables. Fortunately this req/resp protocol is not the expected network bottleneck in the protocol so the additional overhead is not expected to hinder interop testing. More info is to be released from the libp2p community in the coming weeks.

### Why are messages length-prefixed with a protobuf varint in the SSZ encoding?

In stream-oriented protocols, we need to delimit messages from one another, so that the reader knows where one message ends and the next one starts. Length-prefixing is an effective solution. Alternatively, one could set a delimiter char/string, but this can readily cause ambiguity if the message itself may contain the delimiter. It also introduces another set of edge cases to model for, thus causing unnecessary complexity, especially if messages are to be compressed (and thus mutated beyond our control).

That said, in our case, streams are single-use. libp2p streams are full-duplex, and each party is responsible for closing their write side (like in TCP). We therefore use stream closure to mark the end of a request.

Nevertheless, messages are still length-prefixed to prevent DOS attacks where malicious actors send large amounts of data disguised as a request. A length prefix allows clients to set a maximum limit, and once that limit is read, the client can cease reading and disconnect the stream. This allows a client to determine the exact length of the packet being sent, and it capacitates it to reset the stream early if the other party expresses they intend to send too much data.

[Protobuf varint](https://developers.google.com/protocol-buffers/docs/encoding#varints) is an efficient technique to encode variable-length ints. Instead of reserving a fixed-size field of as many bytes as necessary to convey the maximum possible value, this field is elastic in exchange for 1-bit overhead per byte.

### Why do we version protocol strings with ordinals instead of semver?

Using semver for network protocols is confusing. It is never clear what a change in a field, even if backwards compatible on deserialisation, actually implies. Network protocol agreement should be explicit. Imagine two peers:

-  Peer A supporting v1.1.1 of protocol X.
-  Peer B supporting v1.1.2 of protocol X.

These two peers should never speak to each other because the results can be unpredictable. This is an oversimplification: imagine the same problem with a set of 10 possible versions. We now have 10^2 (100) possible outcomes that peers need to model for. The resulting complexity is unwieldy.

For this reason, we rely on negotiation of explicit, verbatim protocols. In the above case, peer B would provide backwards compatibility by supporting and advertising both v1.1.1 and v1.1.2 of the protocol.

Therefore, semver would be relegated to convey expectations at the human level, and it wouldn't do a good job there either, because it's unclear if "backwards-compatibility" and "breaking change" apply only to wire schema level, to behaviour, etc.

For this reason, we remove semver out of the picture and replace it with ordinals that require explicit agreement and do not mandate a specific policy for changes.

### Why is it called Req/Resp and not RPC?

Req/Resp is used to avoid confusion with JSON-RPC and similar user-client interaction mechanisms.

## Discovery

### Why are we using discv5 and not libp2p Kademlia DHT?

discv5 is a standalone protocol, running on UDP on a dedicated port, meant for peer and service discovery only. discv5 supports self-certified, flexible peer records (ENRs) and topic-based advertisement, both of which are, or will be, requirements in this context.

On the other hand, libp2p Kademlia DHT is a fully-fledged DHT protocol/implementation with content routing and storage capabilities, both of which are irrelevant in this context.

We assume that ETH1 nodes will evolve to support discv5. By sharing the discovery network between ETH1 and ETH2, we benefit from the additive effect on network size that enhances resilience and resistance against certain attacks, to which smaller networks are more vulnerable. It should also assist light clients of both networks find nodes with specific capabilities.

discv5 is in the process of being audited.

### What is the difference between an ENR and a multiaddr, and why are we using ENRs?

Ethereum Node Records are self-certified node records. Nodes craft and disseminate ENRs for themselves, proving authorship via a cryptographic signature. ENRs are sequentially indexed, enabling conflicts to be resolved.

ENRs are key-value records with string-indexed ASCII keys. They can store arbitrary information, but EIP-778 specifies a pre-defined dictionary, including IPv4 and IPv6 addresses, secp256k1 public keys, etc.

Comparing ENRs and multiaddrs is like comparing apples and bananas. ENRs are self-certified containers of identity, addresses, and metadata about a node. Multiaddrs are address strings with the peculiarity that they’re self-describing, composable and future-proof. An ENR can contain multiaddrs, and multiaddrs can be derived securely from the fields of an authenticated ENR.

discv5 uses ENRs and we will presumably need to:

1. Add `multiaddr` to the dictionary, so that nodes can advertise their multiaddr under a reserved namespace in ENRs. – and/or –
2. Define a bi-directional conversion function between multiaddrs and the corresponding denormalized fields in an ENR (ip, ip6, tcp, tcp6, etc.), for compatibility with nodes that do not support multiaddr natively (e.g. ETH1 nodes).

## Compression/Encoding

### Why are we using SSZ for encoding?

SSZ is used at the consensus layer and all implementations should have support for ssz encoding/decoding requiring no further dependencies to be added to client implementations. This is a natural choice for serializing objects to be sent across the wire. The actual data in most protocols will be further compressed for efficiency.

SSZ has well defined schema’s for consensus objects (typically sent across the wire) reducing any serialization schema data that needs to be sent. It also has defined all required types that are required for this network specification.

### Why are we compressing, and at which layers?

We compress on the wire to achieve smaller payloads per-message, which, in aggregate, result in higher efficiency, better utilisation of available bandwidth, and overall reduction in network-wide traffic overhead.

At this time, libp2p does not have an out-of-the-box compression feature that can be dynamically negotiated and layered atop connections and streams, but this will be raised in the libp2p community for consideration.

This is a non-trivial feature because the behaviour of network IO loops, kernel buffers, chunking, packet fragmentation, amongst others, need to be taken into account. libp2p streams are unbounded streams, whereas compression algorithms work best on bounded byte streams of which we have some prior knowledge.

Compression tends not to be a one-size-fits-all problem. Lots of variables need careful evaluation, and generic approaches/choices lead to poor size shavings, which may even be counterproductive when factoring in the CPU and memory tradeoff.

For all these reasons, generically negotiating compression algorithms may be treated as a research problem at the libp2p community, one we’re happy to tackle in the medium-term.

At this stage, the wisest choice is to consider libp2p a messenger of bytes, and to make application layer participate in compressing those bytes. This looks different depending on the interaction layer:

-  Gossip domain: since gossipsub has a framing protocol and exposes an API, we compress the payload (when dictated by the encoding token in the topic name) prior to publishing the message via the API. No length prefixing is necessary because protobuf takes care of bounding the field in the serialised form.
-  Req/Resp domain: since we define custom protocols that operate on byte streams, implementers are encouraged to encapsulate the encoding and compression logic behind MessageReader and MessageWriter components/strategies that can be layered on top of the raw byte streams.

### Why are using Snappy for compression?

Snappy is used in Ethereum 1.0. It is well maintained by Google, has good benchmarks and can calculate the size of the uncompressed object without inflating it in memory. This prevents DOS vectors where large uncompressed data is sent.

### Can I get access to unencrypted bytes on the wire for debugging purposes?

Yes, you can add loggers in your libp2p protocol handlers to log incoming and outgoing messages. It is recommended to use programming design patterns to encapsulate the logging logic cleanly.

If your libp2p library relies on frameworks/runtimes such as Netty (jvm) or Node.js (javascript), you can use logging facilities in those frameworks/runtimes to enable message tracing.

For specific ad-hoc testing scenarios, you can use the [plaintext/2.0.0 secure channel](https://github.com/libp2p/specs/blob/master/plaintext/README.md) (which is essentially no-op encryption or message authentication), in combination with tcpdump or Wireshark to inspect the wire.

# libp2p Implementations Matrix

This section will soon contain a matrix showing the maturity/state of the libp2p features required by this spec across the languages in which ETH 2.0 clients are being developed.
