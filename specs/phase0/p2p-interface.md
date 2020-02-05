# Ethereum 2.0 networking specification

This document contains the networking specification for Ethereum 2.0 clients.

It consists of four main sections:

1. A specification of the network fundamentals detailing the two network configurations: interoperability test network and mainnet launch.
2. A specification of the three network interaction *domains* of Eth2: (a) the gossip domain, (b) the discovery domain, and (c) the Req/Resp domain.
3. The rationale and further explanation for the design choices made in the previous two sections.
4. An analysis of the maturity/state of the libp2p features required by this spec across the languages in which Eth2 clients are being developed.

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Network fundamentals](#network-fundamentals)
  - [Transport](#transport)
      - [Interop](#interop)
      - [Mainnet](#mainnet)
  - [Encryption and identification](#encryption-and-identification)
      - [Interop](#interop-1)
      - [Mainnet](#mainnet-1)
  - [Protocol Negotiation](#protocol-negotiation)
      - [Interop](#interop-2)
      - [Mainnet](#mainnet-2)
  - [Multiplexing](#multiplexing)
- [Eth2 network interaction domains](#eth2-network-interaction-domains)
  - [Configuration](#configuration)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
      - [Attestation subnets](#attestation-subnets)
      - [Interop](#interop-3)
      - [Mainnet](#mainnet-3)
    - [Encodings](#encodings)
      - [Interop](#interop-4)
      - [Mainnet](#mainnet-4)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Protocol identification](#protocol-identification)
    - [Req/Resp interaction](#reqresp-interaction)
      - [Requesting side](#requesting-side)
      - [Responding side](#responding-side)
    - [Encoding strategies](#encoding-strategies)
      - [SSZ-encoding strategy (with or without Snappy)](#ssz-encoding-strategy-with-or-without-snappy)
    - [Messages](#messages)
      - [Status](#status)
      - [Goodbye](#goodbye)
      - [BeaconBlocksByRange](#beaconblocksbyrange)
      - [BeaconBlocksByRoot](#beaconblocksbyroot)
  - [The discovery domain: discv5](#the-discovery-domain-discv5)
    - [Integration into libp2p stacks](#integration-into-libp2p-stacks)
    - [ENR structure](#enr-structure)
      - [Attestation subnet bitfield](#attestation-subnet-bitfield)
      - [Interop](#interop-5)
      - [Mainnet](#mainnet-5)
    - [Topic advertisement](#topic-advertisement)
      - [Mainnet](#mainnet-6)
- [Design decision rationale](#design-decision-rationale)
  - [Transport](#transport-1)
    - [Why are we defining specific transports?](#why-are-we-defining-specific-transports)
    - [Can clients support other transports/handshakes than the ones mandated by the spec?](#can-clients-support-other-transportshandshakes-than-the-ones-mandated-by-the-spec)
    - [What are the advantages of using TCP/QUIC/Websockets?](#what-are-the-advantages-of-using-tcpquicwebsockets)
    - [Why do we not just support a single transport?](#why-do-we-not-just-support-a-single-transport)
    - [Why are we not using QUIC for mainnet from the start?](#why-are-we-not-using-quic-for-mainnet-from-the-start)
  - [Multiplexing](#multiplexing-1)
    - [Why are we using mplex/yamux?](#why-are-we-using-mplexyamux)
  - [Protocol Negotiation](#protocol-negotiation-1)
    - [When is multiselect 2.0 due and why are we using it for mainnet?](#when-is-multiselect-20-due-and-why-are-we-using-it-for-mainnet)
    - [What is the difference between connection-level and stream-level protocol negotiation?](#what-is-the-difference-between-connection-level-and-stream-level-protocol-negotiation)
  - [Encryption](#encryption)
    - [Why are we using SecIO for interop? Why not for mainnet?](#why-are-we-using-secio-for-interop-why-not-for-mainnet)
    - [Why are we using Noise/TLS 1.3 for mainnet?](#why-are-we-using-noisetls-13-for-mainnet)
    - [Why are we using encryption at all?](#why-are-we-using-encryption-at-all)
    - [Will mainnnet networking be untested when it launches?](#will-mainnnet-networking-be-untested-when-it-launches)
  - [Gossipsub](#gossipsub)
    - [Why are we using a pub/sub algorithm for block and attestation propagation?](#why-are-we-using-a-pubsub-algorithm-for-block-and-attestation-propagation)
    - [Why are we using topics to segregate encodings, yet only support one encoding?](#why-are-we-using-topics-to-segregate-encodings-yet-only-support-one-encoding)
    - [How do we upgrade gossip channels (e.g. changes in encoding, compression)?](#how-do-we-upgrade-gossip-channels-eg-changes-in-encoding-compression)
    - [Why must all clients use the same gossip topic instead of one negotiated between each peer pair?](#why-must-all-clients-use-the-same-gossip-topic-instead-of-one-negotiated-between-each-peer-pair)
    - [Why are the topics strings and not hashes?](#why-are-the-topics-strings-and-not-hashes)
    - [Why are we overriding the default libp2p pubsub `message-id`?](#why-are-we-overriding-the-default-libp2p-pubsub-message-id)
    - [Why is there `MAXIMUM_GOSSIP_CLOCK_DISPARITY` when validating slot ranges of messages in gossip subnets?](#why-is-there-maximum_gossip_clock_disparity-when-validating-slot-ranges-of-messages-in-gossip-subnets)
    - [Why are there `ATTESTATION_SUBNET_COUNT` attestation subnets?](#why-are-there-attestation_subnet_count-attestation-subnets)
    - [Why are attestations limited to be broadcast on gossip channels within `SLOTS_PER_EPOCH` slots?](#why-are-attestations-limited-to-be-broadcast-on-gossip-channels-within-slots_per_epoch-slots)
    - [Why are aggregate attestations broadcast to the global topic as `AggregateAndProof`s rather than just as `Attestation`s?](#why-are-aggregate-attestations-broadcast-to-the-global-topic-as-aggregateandproofs-rather-than-just-as-attestations)
    - [Why are we sending entire objects in the pubsub and not just hashes?](#why-are-we-sending-entire-objects-in-the-pubsub-and-not-just-hashes)
    - [Should clients gossip blocks if they *cannot* validate the proposer signature due to not yet being synced, not knowing the head block, etc?](#should-clients-gossip-blocks-if-they-cannot-validate-the-proposer-signature-due-to-not-yet-being-synced-not-knowing-the-head-block-etc)
    - [How are we going to discover peers in a gossipsub topic?](#how-are-we-going-to-discover-peers-in-a-gossipsub-topic)
  - [Req/Resp](#reqresp)
    - [Why segregate requests into dedicated protocol IDs?](#why-segregate-requests-into-dedicated-protocol-ids)
    - [Why are messages length-prefixed with a protobuf varint in the SSZ-encoding?](#why-are-messages-length-prefixed-with-a-protobuf-varint-in-the-ssz-encoding)
    - [Why do we version protocol strings with ordinals instead of semver?](#why-do-we-version-protocol-strings-with-ordinals-instead-of-semver)
    - [Why is it called Req/Resp and not RPC?](#why-is-it-called-reqresp-and-not-rpc)
    - [Why do we allow empty responses in block requests?](#why-do-we-allow-empty-responses-in-block-requests)
  - [Discovery](#discovery)
    - [Why are we using discv5 and not libp2p Kademlia DHT?](#why-are-we-using-discv5-and-not-libp2p-kademlia-dht)
    - [What is the difference between an ENR and a multiaddr, and why are we using ENRs?](#what-is-the-difference-between-an-enr-and-a-multiaddr-and-why-are-we-using-enrs)
  - [Compression/Encoding](#compressionencoding)
    - [Why are we using SSZ for encoding?](#why-are-we-using-ssz-for-encoding)
    - [Why are we compressing, and at which layers?](#why-are-we-compressing-and-at-which-layers)
    - [Why are using Snappy for compression?](#why-are-using-snappy-for-compression)
    - [Can I get access to unencrypted bytes on the wire for debugging purposes?](#can-i-get-access-to-unencrypted-bytes-on-the-wire-for-debugging-purposes)
- [libp2p implementations matrix](#libp2p-implementations-matrix)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

# Network fundamentals

This section outlines the specification for the networking stack in Ethereum 2.0 clients.

Sections that have differing parameters for mainnet launch and interoperability testing are split into subsections. Sections that are not split have the same parameters for interoperability testing as mainnet launch.

## Transport

Even though libp2p is a multi-transport stack (designed to listen on multiple simultaneous transports and endpoints transparently), we hereby define a profile for basic interoperability.

#### Interop

All implementations MUST support the TCP libp2p transport, and it MUST be enabled for both dialing and listening (i.e. outbound and inbound connections). The libp2p TCP transport supports listening on IPv4 and IPv6 addresses (and on multiple simultaneously).

To facilitate connectivity and avert possible IPv6 routability/support issues, clients participating in the interoperability testnet MUST expose at least ONE IPv4 endpoint.

All listening endpoints must be publicly dialable, and thus not rely on libp2p circuit relay, AutoNAT, or AutoRelay facilities.

Nodes operating behind a NAT, or otherwise undialable by default (e.g. container runtime, firewall, etc.), MUST have their infrastructure configured to enable inbound traffic on the announced public listening endpoint.

#### Mainnet

All requirements from the interoperability testnet apply, except for the IPv4 addressing scheme requirement.

At this stage, clients are licensed to drop IPv4 support if they wish to do so, cognizant of the potential disadvantages in terms of Internet-wide routability/support. Clients MAY choose to listen only on IPv6, but MUST retain capability to dial both IPv4 and IPv6 addresses.

Usage of circuit relay, AutoNAT, or AutoRelay will be specifically re-examined closer to the time.

## Encryption and identification

#### Interop

[SecIO](https://github.com/libp2p/specs/tree/master/secio) with `secp256k1` identities will be used for initial interoperability testing.

The following SecIO parameters MUST be supported by all stacks:

-  Key agreement: ECDH-P256.
-  Cipher: AES-128.
-  Digest: SHA-256.

#### Mainnet

The [Libp2p-noise](https://github.com/libp2p/specs/tree/master/noise) secure
channel handshake with `secp256k1` identities will be used for mainnet.

As specified in the libp2p specification, clients MUST support the `XX` handshake pattern and
can optionally implement the `IK` and `XXfallback` patterns for optimistic 0-RTT.

## Protocol Negotiation

Clients MUST use exact equality when negotiating protocol versions to use and MAY use the version to give priority to higher version numbers.

#### Interop

Connection-level and stream-level (see the [Rationale](#design-decision-rationale) section below for explanations) protocol negotiation MUST be conducted using [multistream-select v1.0](https://github.com/multiformats/multistream-select/). Its protocol ID is: `/multistream/1.0.0`.

#### Mainnet

Clients MUST support [multistream-select 1.0](https://github.com/multiformats/multistream-select/) and MAY support [multiselect 2.0](https://github.com/libp2p/specs/pull/95). Depending on the number of clients that have implementations for multiselect 2.0 by mainnet, [multistream-select 1.0](https://github.com/multiformats/multistream-select/) may be phased out.

## Multiplexing

During connection bootstrapping, libp2p dynamically negotiates a mutually supported multiplexing method to conduct parallel conversations. This applies to transports that are natively incapable of multiplexing (e.g. TCP, WebSockets, WebRTC), and is omitted for capable transports (e.g. QUIC).

Two multiplexers are commonplace in libp2p implementations: [mplex](https://github.com/libp2p/specs/tree/master/mplex) and [yamux](https://github.com/hashicorp/yamux/blob/master/spec.md). Their protocol IDs are, respectively: `/mplex/6.7.0` and `/yamux/1.0.0`.

Clients MUST support [mplex](https://github.com/libp2p/specs/tree/master/mplex) and MAY support [yamux](https://github.com/hashicorp/yamux/blob/master/spec.md). If both are supported by the client, yamux must take precedence during negotiation. See the [Rationale](#design-decision-rationale) section below for tradeoffs.

# Eth2 network interaction domains

## Configuration

This section outlines constants that are used in this spec.

| Name | Value | Description |
|---|---|---|
| `GOSSIP_MAX_SIZE` | `2**20` (= 1048576, 1 MiB) | The maximum allowed size of uncompressed gossip messages. |
| `MAX_CHUNK_SIZE` | `2**20` (1048576, 1 MiB) | The maximum allowed size of uncompressed req/resp chunked responses. |
| `ATTESTATION_SUBNET_COUNT` | `64` | The number of attestation subnets used in the gossipsub protocol. |
| `TTFB_TIMEOUT` | `5s` | The maximum time to wait for first byte of request response (time-to-first-byte). |
| `RESP_TIMEOUT` | `10s` | The maximum time for complete response transfer. |
| `ATTESTATION_PROPAGATION_SLOT_RANGE` | `32` | The maximum number of slots during which an attestation can be propagated. |
| `MAXIMUM_GOSSIP_CLOCK_DISPARITY` | `500ms` | The maximum milliseconds of clock disparity assumed between honest nodes. |

## The gossip domain: gossipsub

Clients MUST support the [gossipsub](https://github.com/libp2p/specs/tree/master/pubsub/gossipsub) libp2p protocol.

**Protocol ID:** `/meshsub/1.0.0`

**Gossipsub Parameters**

*Note*: Parameters listed here are subject to a large-scale network feasibility study.

The following gossipsub [parameters](https://github.com/libp2p/specs/tree/master/pubsub/gossipsub#meshsub-an-overlay-mesh-router) will be used:

- `D` (topic stable mesh target count): 6
- `D_low` (topic stable mesh low watermark): 4
- `D_high` (topic stable mesh high watermark): 12
- `D_lazy` (gossip target): 6
- `fanout_ttl` (ttl for fanout maps for topics we are not subscribed to but have published to, seconds): 60
- `gossip_advertise` (number of windows to gossip about): 3
- `gossip_history` (number of heartbeat intervals to retain message IDs): 5
- `heartbeat_interval` (frequency of heartbeat, seconds): 1

### Topics and messages

Topics are plain UTF-8 strings and are encoded on the wire as determined by protobuf (gossipsub messages are enveloped in protobuf messages). Topic strings have form: `/eth2/TopicName/TopicEncoding`. This defines both the type of data being sent on the topic and how the data field of the message is encoded.

Each gossipsub [message](https://github.com/libp2p/go-libp2p-pubsub/blob/master/pb/rpc.proto#L17-L24) has a maximum size of `GOSSIP_MAX_SIZE`. Clients MUST reject (fail validation) messages that are over this size limit. Likewise, clients MUST NOT emit or propagate messages larger than this limit.

The `message-id` of a gossipsub message MUST be:

```python
   message-id: base64(SHA256(message.data))
```
where `base64` is the [URL-safe base64 alphabet](https://tools.ietf.org/html/rfc4648#section-3.2) with padding characters omitted.

The payload is carried in the `data` field of a gossipsub message, and varies depending on the topic:

| Topic                                          | Message Type         |
|------------------------------------------------|----------------------|
| beacon_block                                   | SignedBeaconBlock    |
| beacon_aggregate_and_proof                     | AggregateAndProof    |
| beacon_attestation\*                           | Attestation          |
| committee_index{subnet_id}\_beacon_attestation | Attestation          |
| voluntary_exit                                 | SignedVoluntaryExit  |
| proposer_slashing                              | ProposerSlashing     |
| attester_slashing                              | AttesterSlashing     |

Clients MUST reject (fail validation) messages containing an incorrect type, or invalid payload.

When processing incoming gossip, clients MAY descore or disconnect peers who fail to observe these constraints.

\* The `beacon_attestation` topic is only for interop and will be removed prior to mainnet.

#### Global topics

There are two primary global topics used to propagate beacon blocks and aggregate attestations to all nodes on the network. Their `TopicName`s are:

- `beacon_block` - This topic is used solely for propagating new signed beacon blocks to all nodes on the networks. Signed blocks are sent in their entirety. The following validations MUST pass before forwarding the `signed_beacon_block` on the network
    - The proposer signature, `signed_beacon_block.signature` is valid.
    - The block is not from a future slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. validate that `signed_beacon_block.message.slot <= current_slot` (a client MAY queue future blocks for processing at the appropriate slot).
- `beacon_aggregate_and_proof` - This topic is used to propagate aggregated attestations (as `AggregateAndProof`s) to subscribing nodes (typically validators) to be included in future blocks. The following validations MUST pass before forwarding the `aggregate_and_proof` on the network.
    - The aggregate attestation defined by `hash_tree_root(aggregate_and_proof.aggregate)` has _not_ already been seen (via aggregate gossip, within a block, or through the creation of an equivalent aggregate locally).
    - The block being voted for (`aggregate_and_proof.aggregate.data.beacon_block_root`) passes validation.
    - `aggregate_and_proof.aggregate.data.slot` is within the last `ATTESTATION_PROPAGATION_SLOT_RANGE` slots (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. `aggregate_and_proof.aggregate.data.slot + ATTESTATION_PROPAGATION_SLOT_RANGE >= current_slot >= aggregate_and_proof.aggregate.data.slot`.
    - The validator index is within the aggregate's committee -- i.e. `aggregate_and_proof.aggregator_index in get_attesting_indices(state, aggregate_and_proof.aggregate.data, aggregate_and_proof.aggregate.aggregation_bits)`.
    - `aggregate_and_proof.selection_proof` selects the validator as an aggregator for the slot -- i.e. `is_aggregator(state, aggregate_and_proof.aggregate.data.slot, aggregate_and_proof.aggregate.data.index, aggregate_and_proof.selection_proof)` returns `True`.
    - The `aggregate_and_proof.selection_proof` is a valid signature of the `aggregate_and_proof.aggregate.data.slot` by the validator with index `aggregate_and_proof.aggregator_index`.
    - The signature of `aggregate_and_proof.aggregate` is valid.

Additional global topics are used to propagate lower frequency validator messages. Their `TopicName`s are:

- `voluntary_exit` - This topic is used solely for propagating signed voluntary validator exits to proposers on the network. Signed voluntary exits are sent in their entirety. Clients who receive a signed voluntary exit on this topic MUST validate the conditions within `process_voluntary_exit` before forwarding it across the network.
- `proposer_slashing` - This topic is used solely for propagating proposer slashings to proposers on the network. Proposer slashings are sent in their entirety. Clients who receive a proposer slashing on this topic MUST validate the conditions within `process_proposer_slashing` before forwarding it across the network.
- `attester_slashing` - This topic is used solely for propagating attester slashings to proposers on the network. Attester slashings are sent in their entirety. Clients who receive an attester slashing on this topic MUST validate the conditions within `process_attester_slashing` before forwarding it across the network.

#### Attestation subnets

Attestation subnets are used to propagate unaggregated attestations to subsections of the network. Their `TopicName`s are:

- `committee_index{subnet_id}_beacon_attestation` - These topics are used to propagate unaggregated attestations to the subnet `subnet_id` (typically beacon and persistent committees) to be aggregated before being gossiped to `beacon_aggregate_and_proof`. The following validations MUST pass before forwarding the `attestation` on the subnet.
    - The attestation's committee index (`attestation.data.index`) is for the correct subnet.
    - The attestation is unaggregated -- that is, it has exactly one participating validator (`len([bit for bit in attestation.aggregation_bits if bit == 0b1]) == 1`).
    - The block being voted for (`attestation.data.beacon_block_root`) passes validation.
    - `attestation.data.slot` is within the last `ATTESTATION_PROPAGATION_SLOT_RANGE` slots (within a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. `attestation.data.slot + ATTESTATION_PROPAGATION_SLOT_RANGE >= current_slot >= attestation.data.slot`.
    - The signature of `attestation` is valid.

#### Interop

Unaggregated and aggregated attestations from all shards are sent as `Attestation`s to the `beacon_attestation` topic. Clients are not required to publish aggregate attestations but must be able to process them. All validating clients SHOULD try to perform local attestation aggregation to prepare for block proposing.

#### Mainnet

Attestation broadcasting is grouped into subnets defined by a topic. The number of subnets is defined via `ATTESTATION_SUBNET_COUNT`. For the `committee_index{subnet_id}_beacon_attestation` topics, `subnet_id` is set to `index % ATTESTATION_SUBNET_COUNT`, where `index` is the `CommitteeIndex` of the given committee.

Unaggregated attestations are sent to the subnet topic, `committee_index{attestation.data.index % ATTESTATION_SUBNET_COUNT}_beacon_attestation` as `Attestation`s.

Aggregated attestations are sent to the `beacon_aggregate_and_proof` topic as `AggregateAndProof`s.

### Encodings

Topics are post-fixed with an encoding. Encodings define how the payload of a gossipsub message is encoded.

#### Interop

- `ssz` - All objects are [SSZ-encoded](#ssz-encoding). Example: The beacon block topic string is `/eth2/beacon_block/ssz`, and the data field of a gossipsub message is an ssz-encoded `SignedBeaconBlock`.

#### Mainnet

- `ssz_snappy` - All objects are SSZ-encoded and then compressed with [Snappy](https://github.com/google/snappy). Example: The beacon aggregate attestation topic string is `/eth2/beacon_aggregate_and_proof/ssz_snappy`, and the data field of a gossipsub message is an `AggregateAndProof` that has been SSZ-encoded and then compressed with Snappy.

Implementations MUST use a single encoding. Changing an encoding will require coordination between participating implementations.

## The Req/Resp domain

### Protocol identification

Each message type is segregated into its own libp2p protocol ID, which is a case-sensitive UTF-8 string of the form:

```
/ProtocolPrefix/MessageName/SchemaVersion/Encoding
```

With:

- `ProtocolPrefix` - messages are grouped into families identified by a shared libp2p protocol name prefix. In this case, we use `/eth2/beacon_chain/req`.
- `MessageName` - each request is identified by a name consisting of English alphabet, digits and underscores (`_`).
- `SchemaVersion` - an ordinal version number (e.g. 1, 2, 3…). Each schema is versioned to facilitate backward and forward-compatibility when possible.
- `Encoding` - while the schema defines the data types in more abstract terms, the encoding strategy describes a specific representation of bytes that will be transmitted over the wire. See the [Encodings](#Encoding-strategies) section for further details.

This protocol segregation allows libp2p `multistream-select 1.0` / `multiselect 2.0` to handle the request type, version, and encoding negotiation before establishing the underlying streams.

### Req/Resp interaction

We use ONE stream PER request/response interaction. Streams are closed when the interaction finishes, whether in success or in error.

Request/response messages MUST adhere to the encoding specified in the protocol name and follow this structure (relaxed BNF grammar):

```
request   ::= <encoding-dependent-header> | <encoded-payload>
response  ::= <response_chunk>*
response_chunk  ::= <result> | <encoding-dependent-header> | <encoded-payload>
result    ::= “0” | “1” | “2” | [“128” ... ”255”]
```

The encoding-dependent header may carry metadata or assertions such as the encoded payload length, for integrity and attack proofing purposes. Because req/resp streams are single-use and stream closures implicitly delimit the boundaries, it is not strictly necessary to length-prefix payloads; however, certain encodings like SSZ do, for added security.

A `response` is formed by zero or more `response_chunk`s. Responses that consist of a single SSZ-list (such as `BlocksByRange` and `BlocksByRoot`) send each list item as a `response_chunk`. All other response types (non-Lists) send a single `response_chunk`. The encoded-payload of a `response_chunk` has a maximum uncompressed byte size of `MAX_CHUNK_SIZE`.

Clients MUST ensure the each encoded payload of a `response_chunk` is less than or equal to `MAX_CHUNK_SIZE`; if not, they SHOULD reset the stream immediately. Clients tracking peer reputation MAY decrement the score of the misbehaving peer under this circumstance.

#### Requesting side

Once a new stream with the protocol ID for the request type has been negotiated, the full request message SHOULD be sent immediately. The request MUST be encoded according to the encoding strategy.

The requester MUST close the write side of the stream once it finishes writing the request message. At this point, the stream will be half-closed.

The requester MUST wait a maximum of `TTFB_TIMEOUT` for the first response byte to arrive (time to first byte—or TTFB—timeout). On that happening, the requester allows a further `RESP_TIMEOUT` for each subsequent `response_chunk` received. For responses consisting of potentially many `response_chunk`s (an SSZ-list) the requester SHOULD read from the stream until either; a) An error result is received in one of the chunks, b) The responder closes the stream,  c) More than `MAX_CHUNK_SIZE` bytes have been read for a single `response_chunk` payload or d) More than the maximum number of requested chunks are read. For requests consisting of a single `response_chunk` and a length-prefix, the requester should read the exact number of bytes defined by the length-prefix before closing the stream.

If any of these timeouts fire, the requester SHOULD reset the stream and deem the req/resp operation to have failed.

#### Responding side

Once a new stream with the protocol ID for the request type has been negotiated, the responder must process the incoming request message according to the encoding strategy, until EOF (denoting stream half-closure by the requester).

The responder MUST:

1. Use the encoding strategy to read the optional header.
2. If there are any length assertions for length `N`, it should read exactly `N` bytes from the stream, at which point an EOF should arise (no more bytes). Should this not be the case, it should be treated as a failure.
3. Deserialize the expected type, and process the request.
4. Write the response which may consist of zero or more `response_chunk`s (result, optional header, payload).
5. Close their write side of the stream. At this point, the stream will be fully closed.

If steps (1), (2), or (3) fail due to invalid, malformed, or inconsistent data, the responder MUST respond in error. Clients tracking peer reputation MAY record such failures, as well as unexpected events, e.g. early stream resets.

The entire request should be read in no more than `RESP_TIMEOUT`. Upon a timeout, the responder SHOULD reset the stream.

The responder SHOULD send a `response_chunk` promptly. Chunks start with a **single-byte** response code which determines the contents of the `response_chunk` (`result` particle in the BNF grammar above). For multiple chunks, only the last chunk is allowed to have a non-zero error code (i.e. The chunk stream is terminated once an error occurs).

The response code can have one of the following values, encoded as a single unsigned byte:

-  0: **Success** -- a normal response follows, with contents matching the expected message schema and encoding specified in the request.
-  1: **InvalidRequest** -- the contents of the request are semantically invalid, or the payload is malformed, or could not be understood. The response payload adheres to the `ErrorMessage` schema (described below).
-  2: **ServerError** -- the responder encountered an error while processing the request. The response payload adheres to the `ErrorMessage` schema (described below).

Clients MAY use response codes above `128` to indicate alternative, erroneous request-specific responses.

The range `[3, 127]` is RESERVED for future usages, and should be treated as error if not recognized expressly.

The `ErrorMessage` schema is:

```
(
  error_message: String
)
```

*Note*: The String type is encoded as UTF-8 bytes without NULL terminator when SSZ-encoded. As the `ErrorMessage` is not an SSZ-container, only the UTF-8 bytes will be sent when SSZ-encoded.

A response therefore has the form of one or more `response_chunk`s, each structured as follows:
```
  +--------+--------+--------+--------+--------+--------+
  | result |   header (opt)  |     encoded_response     |
  +--------+--------+--------+--------+--------+--------+
```
Here, `result` represents the 1-byte response code.

### Encoding strategies

The token of the negotiated protocol ID specifies the type of encoding to be used for the req/resp interaction. Two values are possible at this time:

-  `ssz`: the contents are [SSZ-encoded](../../ssz/simple-serialize.md). This encoding type MUST be supported by all clients. For objects containing a single field, only the field is SSZ-encoded not a container with a single field. For example, the `BeaconBlocksByRoot` request is an SSZ-encoded list of `Bytes32`'s.
-  `ssz_snappy`: The contents are SSZ-encoded and then compressed with [Snappy](https://github.com/google/snappy). MAY be supported in the interoperability testnet; MUST be supported in mainnet.

#### SSZ-encoding strategy (with or without Snappy)

The [SimpleSerialize (SSZ) specification](../../ssz/simple-serialize.md) outlines how objects are SSZ-encoded. If the Snappy variant is selected, we feed the serialized form to the Snappy compressor on encoding. The inverse happens on decoding.

**Encoding-dependent header:** Req/Resp protocols using the `ssz` or `ssz_snappy` encoding strategies MUST prefix all encoded and compressed (if applicable) payloads with an unsigned [protobuf varint](https://developers.google.com/protocol-buffers/docs/encoding#varints).

All messages that contain only a single field MUST be encoded directly as the type of that field and MUST NOT be encoded as an SSZ container.

Responses that are SSZ-lists (for example `[]SignedBeaconBlock`) send their
constituents individually as `response_chunk`s. For example, the
`[]SignedBeaconBlock` response type sends zero or more `response_chunk`s. Each _successful_ `response_chunk` contains a single `SignedBeaconBlock` payload.

### Messages

#### Status

**Protocol ID:** ``/eth2/beacon_chain/req/status/1/``

Request, Response Content:
```
(
  head_fork_version: Bytes4
  finalized_root: Bytes32
  finalized_epoch: uint64
  head_root: Bytes32
  head_slot: uint64
)
```
The fields are, as seen by the client at the time of sending the message:

- `head_fork_version`: The beacon_state `Fork` version.
- `finalized_root`: `state.finalized_checkpoint.root` for the state corresponding to the head block.
- `finalized_epoch`: `state.finalized_checkpoint.epoch` for the state corresponding to the head block.
- `head_root`: The hash_tree_root root of the current head block.
- `head_slot`: The slot of the block corresponding to the `head_root`.

The dialing client MUST send a `Status` request upon connection.

The request/response MUST be encoded as an SSZ-container.

The response MUST consist of a single `response_chunk`.

Clients SHOULD immediately disconnect from one another following the handshake above under the following conditions:

1. If `head_fork_version` does not match the expected fork version at the epoch of the `head_slot`, since the client’s chain is on another fork. `head_fork_version` can also be used to segregate testnets.
2. If the (`finalized_root`, `finalized_epoch`) shared by the peer is not in the client's chain at the expected epoch. For example, if Peer 1 sends (root, epoch) of (A, 5) and Peer 2 sends (B, 3) but Peer 1 has root C at epoch 3, then Peer 1 would disconnect because it knows that their chains are irreparably disjoint.

Once the handshake completes, the client with the lower `finalized_epoch` or `head_slot` (if the clients have equal `finalized_epoch`s) SHOULD request beacon blocks from its counterparty via the `BeaconBlocksByRange` request.

*Note*: Under abnormal network condition or after some rounds of `BeaconBlocksByRange` requests, the client might need to send `Status` request again to learn if the peer has a higher head. Implementers are free to implement such behavior in their own way.

#### Goodbye

**Protocol ID:** ``/eth2/beacon_chain/req/goodbye/1/``

Request, Response Content:
```
(
  uint64
)
```
Client MAY send goodbye messages upon disconnection. The reason field MAY be one of the following values:

- 1: Client shut down.
- 2: Irrelevant network.
- 3: Fault/error.

Clients MAY use reason codes above `128` to indicate alternative, erroneous request-specific responses.

The range `[4, 127]` is RESERVED for future usage.

The request/response MUST be encoded as a single SSZ-field.

The response MUST consist of a single `response_chunk`.

#### BeaconBlocksByRange

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/1/`

Request Content:
```
(
  head_block_root: Bytes32
  start_slot: uint64
  count: uint64
  step: uint64
)
```

Response Content:
```
(
  []SignedBeaconBlock
)
```

Requests count beacon blocks from the peer starting from `start_slot` on the chain defined by `head_block_root` (= `hash_tree_root(SignedBeaconBlock.message)`). The response MUST contain no more than count blocks. `step` defines the slot increment between blocks. For example, requesting blocks starting at `start_slot` 2 with a step value of 2 would return the blocks at [2, 4, 6, …]. In cases where a slot is empty for a given slot number, no block is returned. For example, if slot 4 were empty in the previous example, the returned array would contain [2, 6, …]. A step value of 1 returns all blocks on the range `[start_slot, start_slot + count)`.

The request MUST be encoded as an SSZ-container.

The response MUST consist of zero or more `response_chunk`. Each _successful_ `response_chunk` MUST contain a single `SignedBeaconBlock` payload.

`BeaconBlocksByRange` is primarily used to sync historical blocks.

Clients MUST support requesting blocks since the start of the weak subjectivity period and up to the given `head_block_root`.

Clients MUST support `head_block_root` values since the latest finalized epoch.

Clients MUST respond with at least one block, if they have it and it exists in the range. Clients MAY limit the number of blocks in the response.

Clients MUST order blocks by increasing slot number.

#### BeaconBlocksByRoot

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/1/`

Request Content:

```
(
  []Bytes32
)
```

Response Content:

```
(
  []SignedBeaconBlock
)
```

Requests blocks by block root (= `hash_tree_root(SignedBeaconBlock.message)`). The response is a list of `SignedBeaconBlock` whose length is less than or equal to the number of requested blocks. It may be less in the case that the responding peer is missing blocks.

`BeaconBlocksByRoot` is primarily used to recover recent blocks (e.g. when receiving a block or attestation whose parent is unknown).

The request MUST be encoded as an SSZ-field.

The response MUST consist of zero or more `response_chunk`. Each _successful_ `response_chunk` MUST contain a single `SignedBeaconBlock` payload.

Clients MUST support requesting blocks since the latest finalized epoch.

Clients MUST respond with at least one block, if they have it. Clients MAY limit the number of blocks in the response.

## The discovery domain: discv5

Discovery Version 5 ([discv5](https://github.com/ethereum/devp2p/blob/master/discv5/discv5.md)) is used for peer discovery, both in the interoperability testnet and mainnet.

`discv5` is a standalone protocol, running on UDP on a dedicated port, meant for peer discovery only. `discv5` supports self-certified, flexible peer records (ENRs) and topic-based advertisement, both of which are (or will be) requirements in this context.

:warning: Under construction. :warning:

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

#### Attestation subnet bitfield

The ENR MAY contain an entry (`attnets`) signifying the attestation subnet bitfield with the following form to more easily discover peers participating in particular attestation gossip subnets.

| Key          | Value                                            |
|:-------------|:-------------------------------------------------|
| `attnets`    | SSZ `Bitvector[ATTESTATION_SUBNET_COUNT]`        |

#### Interop

In the interoperability testnet, all peers will support all capabilities defined in this document (gossip, full Req/Resp suite, discovery protocol), therefore the ENR record does not need to carry Eth2 capability information, as it would be superfluous.

Nonetheless, ENRs MUST carry a generic `eth2` key with nil value, denoting that the peer is indeed an Eth2 peer, in order to eschew connecting to Eth 1.0 peers.

#### Mainnet

On mainnet, ENRs MUST include a structure enumerating the capabilities offered by the peer in an efficient manner. The concrete solution is currently undefined. Proposals include using namespaced bloom filters mapping capabilities to specific protocol IDs supported under that capability.

### Topic advertisement

#### Mainnet

discv5's topic advertisement feature is not expected to be ready for mainnet launch of Phase 0.

Once this feature is built out and stable, we expect to use topic advertisement as a rendezvous facility for peers on shards. Until then, the ENR [attestation subnet bitfield](#attestation-subnet-bitfield) will be used for discovery of peers on particular subnets.

# Design decision rationale

## Transport

### Why are we defining specific transports?

libp2p peers can listen on multiple transports concurrently, and these can change over time. Multiaddrs encode not only the address but also the transport to be used to dial.

Due to this dynamic nature, agreeing on specific transports like TCP, QUIC, or WebSockets on paper becomes irrelevant.

However, it is useful to define a minimum baseline for interoperability purposes.

### Can clients support other transports/handshakes than the ones mandated by the spec?

Clients may support other transports such as libp2p QUIC, WebSockets, and WebRTC transports, if available in the language of choice. While interoperability shall not be harmed by lack of such support, the advantages are desirable:

-  Better latency, performance, and other QoS characteristics (QUIC).
-  Paving the way for interfacing with future light clients (WebSockets, WebRTC).

The libp2p QUIC transport inherently relies on TLS 1.3 per requirement in section 7 of the [QUIC protocol specification](https://tools.ietf.org/html/draft-ietf-quic-transport-22#section-7) and the accompanying [QUIC-TLS document](https://tools.ietf.org/html/draft-ietf-quic-tls-22).

The usage of one handshake procedure or the other shall be transparent to the Eth2 application layer, once the libp2p Host/Node object has been configured appropriately.

### What are the advantages of using TCP/QUIC/Websockets?

TCP is a reliable, ordered, full-duplex, congestion-controlled network protocol that powers much of the Internet as we know it today. HTTP/1.1 and HTTP/2 run atop TCP.

QUIC is a new protocol that’s in the final stages of specification by the IETF QUIC WG. It emerged from Google’s SPDY experiment. The QUIC transport is undoubtedly promising. It’s UDP-based yet reliable, ordered, multiplexed, natively secure (TLS 1.3), reduces latency vs. TCP, and offers stream-level and connection-level congestion control (thus removing head-of-line blocking), 0-RTT connection establishment, and endpoint migration, amongst other features. UDP also has better NAT traversal properties than TCP—something we desperately pursue in peer-to-peer networks.

QUIC is being adopted as the underlying protocol for HTTP/3. This has the potential to award us censorship resistance via deep packet inspection for free. Provided that we use the same port numbers and encryption mechanisms as HTTP/3, our traffic may be indistinguishable from standard web traffic, and we may only become subject to standard IP-based firewall filtering—something we can counteract via other mechanisms.

WebSockets and/or WebRTC transports are necessary for interaction with browsers, and will become increasingly important as we incorporate browser-based light clients to the Eth2 network.

### Why do we not just support a single transport?

Networks evolve. Hardcoding design decisions leads to ossification, preventing the evolution of networks alongside the state of the art. Introducing changes on an ossified protocol is very costly, and sometimes, downright impracticable without causing undesirable breakage.

Modeling for upgradeability and dynamic transport selection from the get-go lays the foundation for a future-proof stack.

Clients can adopt new transports without breaking old ones, and the multi-transport ability enables constrained and sandboxed environments (e.g. browsers, embedded devices) to interact with the network as first-class citizens via suitable/native transports (e.g. WSS), without the need for proxying or trust delegation to servers.

### Why are we not using QUIC for mainnet from the start?

The QUIC standard is still not finalized (at working draft 22 at the time of writing), and not all mainstream runtimes/languages have mature, standard, and/or fully-interoperable [QUIC support](https://github.com/quicwg/base-drafts/wiki/Implementations). One remarkable example is node.js, where the QUIC implementation is [in early development](https://github.com/nodejs/quic).

## Multiplexing

### Why are we using mplex/yamux?

[Yamux](https://github.com/hashicorp/yamux/blob/master/spec.md) is a multiplexer invented by Hashicorp that supports stream-level congestion control. Implementations exist in a limited set of languages, and it’s not a trivial piece to develop.

Conscious of that, the libp2p community conceptualized [mplex](https://github.com/libp2p/specs/blob/master/mplex/README.md) as a simple, minimal multiplexer for usage with libp2p. It does not support stream-level congestion control and is subject to head-of-line blocking.

Overlay multiplexers are not necessary with QUIC since the protocol provides native multiplexing, but they need to be layered atop TCP, WebSockets, and other transports that lack such support.

## Protocol Negotiation

### When is multiselect 2.0 due and why are we using it for mainnet?

multiselect 2.0 is currently being conceptualized. The debate started [on this issue](https://github.com/libp2p/specs/pull/95), but it got overloaded—as it tends to happen with large conceptual OSS discussions that touch the heart and core of a system.

In the following weeks (August 2019), there will be a renewed initiative to first define the requirements, constraints, assumptions, and features, in order to lock in basic consensus upfront and subsequently build on that consensus by submitting a specification for implementation.

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

Copied from the Noise Protocol Framework [website](http://www.noiseprotocol.org):

> Noise is a framework for building crypto protocols. Noise protocols support mutual and optional authentication, identity hiding, forward secrecy, zero round-trip encryption, and other advanced features.

Noise in itself does not specify a single handshake procedure, but provides a framework to build secure handshakes based on Diffie-Hellman key agreement with a variety of tradeoffs and guarantees.

Noise handshakes are lightweight and simple to understand, and are used in major cryptographic-centric projects like WireGuard, I2P, and Lightning. [Various](https://www.wireguard.com/papers/kobeissi-bhargavan-noise-explorer-2018.pdf) [studies](https://eprint.iacr.org/2019/436.pdf) have assessed the stated security goals of several Noise handshakes with positive results.

On the other hand, TLS 1.3 is the newest, simplified iteration of TLS. Old, insecure, obsolete ciphers and algorithms have been removed, adopting Ed25519 as the sole ECDH key agreement function. Handshakes are faster, 1-RTT data is supported, and session resumption is a reality, amongst other features.

*Note*: [TLS 1.3 is a prerequisite of the QUIC transport](https://tools.ietf.org/html/draft-ietf-quic-transport-22#section-7), although an experiment exists to integrate Noise as the QUIC crypto layer: [nQUIC](https://eprint.iacr.org/2019/028).

### Why are we using encryption at all?

Transport level encryption secures message exchange and provides properties that are useful for privacy, safety, and censorship resistance. These properties are derived from the following security guarantees that apply to the entire communication between two peers:

-  Peer authentication: the peer I’m talking to is really who they claim to be and who I expect them to be.
-  Confidentiality: no observer can eavesdrop on the content of our messages.
-  Integrity: the data has not been tampered with by a third-party while in transit.
-  Non-repudiation: the originating peer cannot dispute that they sent the message.
-  Depending on the chosen algorithms and mechanisms (e.g. continuous HMAC), we may obtain additional guarantees, such as non-replayability (this byte could’ve only been sent *now;* e.g. by using continuous HMACs), or perfect forward secrecy (in the case that a peer key is compromised, the content of a past conversation will not be compromised).

Note that transport-level encryption is not exclusive of application-level encryption or cryptography. Transport-level encryption secures the communication itself, while application-level cryptography is necessary for the application’s use cases (e.g. signatures, randomness, etc.).

### Will mainnnet networking be untested when it launches?

Before launching mainnet, the testnet will be switched over to mainnet networking parameters, including Noise handshakes, and other new protocols. This gives us an opportunity to drill coordinated network upgrades and verifying that there are no significant upgradeability gaps.

## Gossipsub

### Why are we using a pub/sub algorithm for block and attestation propagation?

Pubsub is a technique to broadcast/disseminate data across a network rapidly. Such data is packaged in fire-and-forget messages that do not require a response from every recipient. Peers subscribed to a topic participate in the propagation of messages in that topic.

The alternative is to maintain a fully connected mesh (all peers connected to each other 1:1), which scales poorly (O(n^2)).

### Why are we using topics to segregate encodings, yet only support one encoding?

For future extensibility with almost zero overhead now (besides the extra bytes in the topic name).

### How do we upgrade gossip channels (e.g. changes in encoding, compression)?

Changing gossipsub/broadcasts requires a coordinated upgrade where all clients start publishing to the new topic together, for example during a hard fork.

One can envision a two-phase deployment as well where clients start listening to the new topic in the first phase then start publishing some time later, letting the traffic naturally move over to the new topic.

### Why must all clients use the same gossip topic instead of one negotiated between each peer pair?

Supporting multiple topics/encodings would require the presence of relayers to translate between encodings and topics so as to avoid network fragmentation where participants have diverging views on the gossiped state, making the protocol more complicated and fragile.

Gossip protocols typically remember what messages they've seen for a finite period of time-based on message identity—if you publish the same message again after that time has passed, it will be re-broadcast—adding a relay delay also makes this scenario more likely.

One can imagine that in a complicated upgrade scenario, we might have peers publishing the same message on two topics/encodings, but the price here is pretty high in terms of overhead—both computational and networking—so we'd rather avoid that.

It is permitted for clients to publish data on alternative topics as long as they also publish on the network-wide mandatory topic.

### Why are the topics strings and not hashes?

Topic names have a hierarchical structure. In the future, gossipsub may support wildcard subscriptions (e.g. subscribe to all children topics under a root prefix) by way of prefix matching. Enforcing hashes for topic names would preclude us from leveraging such features going forward.

No security or privacy guarantees are lost as a result of choosing plaintext topic names, since the domain is finite anyway, and calculating a digest's preimage would be trivial.

Furthermore, the Eth2 topic names are shorter than their digest equivalents (assuming SHA-256 hash), so hashing topics would bloat messages unnecessarily.

### Why are we overriding the default libp2p pubsub `message-id`?

For our current purposes, there is no need to address messages based on source peer, and it seems likely we might even override the message `from` to obfuscate the peer. By overriding the default `message-id` to use content-addressing we can filter unnecessary duplicates before hitting the application layer.

Some examples of where messages could be duplicated:

* A validator client connected to multiple beacon nodes publishing duplicate gossip messages
* Attestation aggregation strategies where clients partially aggregate attestations and propagate them. Partial aggregates could be duplicated
* Clients re-publishing seen messages

### Why is there `MAXIMUM_GOSSIP_CLOCK_DISPARITY` when validating slot ranges of messages in gossip subnets?

For some gossip channels (e.g. those for Attestations and BeaconBlocks), there are designated ranges of slots during which particular messages can be sent, limiting messages gossiped to those that can be reasonably used in the consensus at the current time/slot. This is to reduce optionality in DoS attacks.

`MAXIMUM_GOSSIP_CLOCK_DISPARITY` provides some leeway in validating slot ranges to prevent the gossip network from becoming overly brittle with respect to clock disparity. For minimum and maximum allowable slot broadcast times, `MAXIMUM_GOSSIP_CLOCK_DISPARITY` MUST be subtracted and added respectively, marginally extending the valid range. Although messages can at times be eagerly gossiped to the network, the node's fork choice prevents integration of these messages into the actual consensus until the _actual local start_ of the designated slot.

The value of this constant is currently a placeholder and will be tuned based on data observed in testnets.

### Why are there `ATTESTATION_SUBNET_COUNT` attestation subnets?

Depending on the number of validators, it may be more efficient to group shard subnets and might provide better stability for the gossipsub channel. The exact grouping will be dependent on more involved network tests. This constant allows for more flexibility in setting up the network topology for attestation aggregation (as aggregation should happen on each subnet). The value is currently set to to be equal `MAX_COMMITTEES_PER_SLOT` until network tests indicate otherwise.

### Why are attestations limited to be broadcast on gossip channels within `SLOTS_PER_EPOCH` slots?

Attestations can only be included on chain within an epoch's worth of slots so this is the natural cutoff. There is no utility to the chain to broadcast attestations older than one epoch, and because validators have a chance to make a new attestation each epoch, there is minimal utility to the fork choice to relay old attestations as a new latest message can soon be created by each validator.

In addition to this, relaying attestations requires validating the attestation in the context of the `state` during which it was created. Thus, validating arbitrarily old attestations would put additional requirements on which states need to be readily available to the node. This would result in a higher resource burden and could serve as a DoS vector.

### Why are aggregate attestations broadcast to the global topic as `AggregateAndProof`s rather than just as `Attestation`s?

The dominant strategy for an individual validator is to always broadcast an aggregate containing their own attestation to the global channel to ensure that proposers see their attestation for inclusion. Using a private selection criteria and providing this proof of selection alongside the gossiped aggregate ensures that this dominant strategy will not flood the global channel.

Also, an attacker can create any number of honest-looking aggregates and broadcast them to the global pubsub channel. Thus without some sort of proof of selection as an aggregator, the global channel can trivially be spammed.

### Why are we sending entire objects in the pubsub and not just hashes?

Entire objects should be sent to get the greatest propagation speeds. If only hashes are sent, then block and attestation propagation is dependent on recursive requests from each peer. In a hash-only scenario, peers could receive hashes without knowing who to download the actual contents from. Sending entire objects ensures that they get propagated through the entire network.

### Should clients gossip blocks if they *cannot* validate the proposer signature due to not yet being synced, not knowing the head block, etc?

The prohibition of unverified-block-gossiping extends to nodes that cannot verify a signature due to not being fully synced to ensure that such (amplified) DOS attacks are not possible.

### How are we going to discover peers in a gossipsub topic?

In Phase 0, peers for attestation subnets will be found using the `attnets` entry in the ENR.

Although this method will be sufficient for early phases of Eth2, we aim to use the more appropriate discv5 topics for this and other similar tasks in the future. ENRs should ultimately not be used for this purpose. They are best suited to store identity, location, and capability information, rather than more volatile advertisements.

## Req/Resp

### Why segregate requests into dedicated protocol IDs?

Requests are segregated by protocol ID to:

1. Leverage protocol routing in libp2p, such that the libp2p stack will route the incoming stream to the appropriate handler. This allows the handler function for each request type to be self-contained. For an analogy, think about how you attach HTTP handlers to a REST API server.
2. Version requests independently. In a coarser-grained umbrella protocol, the entire protocol would have to be versioned even if just one field in a single message changed.
3. Enable clients to select the individual requests/versions they support. It would no longer be a strict requirement to support all requests, and clients, in principle, could support a subset of requests and variety of versions.
4. Enable flexibility and agility for clients adopting spec changes that impact the request, by signalling to peers exactly which subset of new/old requests they support.
5. Enable clients to explicitly choose backwards compatibility at the request granularity. Without this, clients would be forced to support entire versions of the coarser request protocol.
6. Parallelise RFCs (or Eth2 EIPs). By decoupling requests from one another, each RFC that affects the request protocol can be deployed/tested/debated independently without relying on a synchronization point to version the general top-level protocol.
  1. This has the benefit that clients can explicitly choose which RFCs to deploy without buying into all other RFCs that may be included in that top-level version.
  2. Affording this level of granularity with a top-level protocol would imply creating as many variants (e.g. /protocol/43-{a,b,c,d,...}) as the cartesian product of RFCs inflight, O(n^2).
7. Allow us to simplify the payload of requests. Request-id’s and method-ids no longer need to be sent. The encoding/request type and version can all be handled by the framework.

**Caveat**: The protocol negotiation component in the current version of libp2p is called multistream-select 1.0. It is somewhat naïve and introduces overhead on every request when negotiating streams, although implementation-specific optimizations are possible to save this cost. Multiselect 2.0 will remove this overhead by memoizing previously selected protocols, and modeling shared protocol tables. Fortunately, this req/resp protocol is not the expected network bottleneck in the protocol so the additional overhead is not expected to hinder interop testing. More info is to be released from the libp2p community in the coming weeks.

### Why are messages length-prefixed with a protobuf varint in the SSZ-encoding?

We are using single-use streams where each stream is closed at the end of the message. Thus, libp2p transparently handles message delimiting in the underlying stream. libp2p streams are full-duplex, and each party is responsible for closing their write side (like in TCP). We can therefore use stream closure to mark the end of the request and response independently.

Nevertheless, messages are still length-prefixed—this is now being considered for removal.

Advantages of length-prefixing include:

* Reader can prepare a correctly sized buffer before reading message
* Alignment with protocols like gRPC over HTTP/2 that prefix with length
* Sanity checking of stream closure / message length

Disadvantages include:

* Redundant methods of message delimiting—both stream end marker and length prefix
* Harder to stream as length must be known up-front
* Additional code path required to verify length

In some protocols, adding a length prefix serves as a form of DoS protection against very long messages, allowing the client to abort if an overlong message is about to be sent. In this protocol, we are globally limiting message sizes using `MAX_CHUNK_SIZE`, thus the length prefix does not afford any additional protection.

[Protobuf varint](https://developers.google.com/protocol-buffers/docs/encoding#varints) is an efficient technique to encode variable-length ints. Instead of reserving a fixed-size field of as many bytes as necessary to convey the maximum possible value, this field is elastic in exchange for 1-bit overhead per byte.

### Why do we version protocol strings with ordinals instead of semver?

Using semver for network protocols is confusing. It is never clear what a change in a field, even if backwards compatible on deserialization, actually implies. Network protocol agreement should be explicit. Imagine two peers:

-  Peer A supporting v1.1.1 of protocol X.
-  Peer B supporting v1.1.2 of protocol X.

These two peers should never speak to each other because the results can be unpredictable. This is an oversimplification: imagine the same problem with a set of 10 possible versions. We now have 10^2 (100) possible outcomes that peers need to model for. The resulting complexity is unwieldy.

For this reason, we rely on negotiation of explicit, verbatim protocols. In the above case, peer B would provide backwards compatibility by supporting and advertising both v1.1.1 and v1.1.2 of the protocol.

Therefore, semver would be relegated to convey expectations at the human level, and it wouldn't do a good job there either, because it's unclear if "backwards compatibility" and "breaking change" apply only to wire schema level, to behavior, etc.

For this reason, we remove and replace semver with ordinals that require explicit agreement and do not mandate a specific policy for changes.

### Why is it called Req/Resp and not RPC?

Req/Resp is used to avoid confusion with JSON-RPC and similar user-client interaction mechanisms.

### Why do we allow empty responses in block requests?

When requesting blocks by range or root, it may happen that there are no blocks in the selected range or the responding node does not have the requested blocks.

Thus, it may happen that we need to transmit an empty list - there are several ways to encode this:

0) Close the stream without sending any data
1) Add a `null` option to the `success` response, for example by introducing an additional byte
2) Respond with an error result, using a specific error code for "No data"

Semantically, it is not an error that a block is missing during a slot making option 2 unnatural.

Option 1 allows allows the responder to signal "no block", but this information may be wrong - for example in the case of a malicious node.

Under option 0, there is no way for a client to distinguish between a slot without a block and an incomplete response, but given that it already must contain logic to handle the uncertainty of a malicious peer, option 0 was chosen. Clients should mark any slots missing blocks as unknown until they can be verified as not containing a block by successive blocks.

Assuming option 0 with no special `null` encoding, consider a request for slots `2, 3, 4` - if there was no block produced at slot 4, the response would be `2, 3, EOF`. Now consider the same situation, but where only `4` is requested - closing the stream with only `EOF` (without any `response_chunk`) is consistent.

Failing to provide blocks that nodes "should" have is reason to trust a peer less - for example, if a particular peer gossips a block, it should have access to its parent. If a request for the parent fails, it's indicative of poor peer quality since peers should validate blocks before gossiping them.

## Discovery

### Why are we using discv5 and not libp2p Kademlia DHT?

discv5 is a standalone protocol, running on UDP on a dedicated port, meant for peer and service discovery only. discv5 supports self-certified, flexible peer records (ENRs) and topic-based advertisement, both of which are, or will be, requirements in this context.

On the other hand, libp2p Kademlia DHT is a fully-fledged DHT protocol/implementation with content routing and storage capabilities, both of which are irrelevant in this context.

We assume that Eth 1.0 nodes will evolve to support discv5. By sharing the discovery network between Eth 1.0 and 2.0, we benefit from the additive effect on network size that enhances resilience and resistance against certain attacks, to which smaller networks are more vulnerable. It should also help light clients of both networks find nodes with specific capabilities.

discv5 is in the process of being audited.

### What is the difference between an ENR and a multiaddr, and why are we using ENRs?

Ethereum Node Records are self-certified node records. Nodes craft and disseminate ENRs for themselves, proving authorship via a cryptographic signature. ENRs are sequentially indexed, enabling conflicts to be resolved.

ENRs are key-value records with string-indexed ASCII keys. They can store arbitrary information, but EIP-778 specifies a pre-defined dictionary, including IPv4 and IPv6 addresses, secp256k1 public keys, etc.

Comparing ENRs and multiaddrs is like comparing apples and oranges. ENRs are self-certified containers of identity, addresses, and metadata about a node. Multiaddrs are address strings with the peculiarity that they’re self-describing, composable and future-proof. An ENR can contain multiaddrs, and multiaddrs can be derived securely from the fields of an authenticated ENR.

discv5 uses ENRs and we will presumably need to:

1. Add `multiaddr` to the dictionary, so that nodes can advertise their multiaddr under a reserved namespace in ENRs. – and/or –
2. Define a bi-directional conversion function between multiaddrs and the corresponding denormalized fields in an ENR (ip, ip6, tcp, tcp6, etc.), for compatibility with nodes that do not support multiaddr natively (e.g. Eth 1.0 nodes).

## Compression/Encoding

### Why are we using SSZ for encoding?

SSZ is used at the consensus layer, and all implementations should have support for SSZ-encoding/decoding, requiring no further dependencies to be added to client implementations. This is a natural choice for serializing objects to be sent across the wire. The actual data in most protocols will be further compressed for efficiency.

SSZ has well-defined schemas for consensus objects (typically sent across the wire) reducing any serialization schema data that needs to be sent. It also has defined all required types that are required for this network specification.

### Why are we compressing, and at which layers?

We compress on the wire to achieve smaller payloads per-message, which, in aggregate, result in higher efficiency, better utilization of available bandwidth, and overall reduction in network-wide traffic overhead.

At this time, libp2p does not have an out-of-the-box compression feature that can be dynamically negotiated and layered atop connections and streams, but it is [being considered](https://github.com/libp2p/libp2p/issues/81).

This is a non-trivial feature because the behavior of network IO loops, kernel buffers, chunking, and packet fragmentation, amongst others, need to be taken into account. libp2p streams are unbounded streams, whereas compression algorithms work best on bounded byte streams of which we have some prior knowledge.

Compression tends not to be a one-size-fits-all problem. A lot of variables need careful evaluation, and generic approaches/choices lead to poor size shavings, which may even be counterproductive when factoring in the CPU and memory tradeoff.

For all these reasons, generically negotiating compression algorithms may be treated as a research problem at the libp2p community, one we’re happy to tackle in the medium-term.

At this stage, the wisest choice is to consider libp2p a messenger of bytes, and to make application layer participate in compressing those bytes. This looks different depending on the interaction layer:

-  Gossip domain: since gossipsub has a framing protocol and exposes an API, we compress the payload (when dictated by the encoding token in the topic name) prior to publishing the message via the API. No length prefixing is necessary because protobuf takes care of bounding the field in the serialized form.
-  Req/Resp domain: since we define custom protocols that operate on byte streams, implementers are encouraged to encapsulate the encoding and compression logic behind MessageReader and MessageWriter components/strategies that can be layered on top of the raw byte streams.

### Why are using Snappy for compression?

Snappy is used in Ethereum 1.0. It is well maintained by Google, has good benchmarks, and can calculate the size of the uncompressed object without inflating it in memory. This prevents DOS vectors where large uncompressed data is sent.

### Can I get access to unencrypted bytes on the wire for debugging purposes?

Yes, you can add loggers in your libp2p protocol handlers to log incoming and outgoing messages. It is recommended to use programming design patterns to encapsulate the logging logic cleanly.

If your libp2p library relies on frameworks/runtimes such as Netty (jvm) or Node.js (javascript), you can use logging facilities in those frameworks/runtimes to enable message tracing.

For specific ad-hoc testing scenarios, you can use the [plaintext/2.0.0 secure channel](https://github.com/libp2p/specs/blob/master/plaintext/README.md) (which is essentially no-op encryption or message authentication), in combination with tcpdump or Wireshark to inspect the wire.

# libp2p implementations matrix

This section will soon contain a matrix showing the maturity/state of the libp2p features required by this spec across the languages in which Eth2 clients are being developed.
