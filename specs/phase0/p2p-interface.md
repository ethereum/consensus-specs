# Phase 0 -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Network fundamentals](#network-fundamentals)
  - [Transport](#transport)
  - [Encryption and identification](#encryption-and-identification)
  - [Protocol negotiation](#protocol-negotiation)
  - [Multiplexing](#multiplexing)
- [Consensus-layer network interaction domains](#consensus-layer-network-interaction-domains)
  - [Custom types](#custom-types)
  - [Constants](#constants)
  - [Configuration](#configuration)
  - [Helpers](#helpers)
    - [`compute_fork_version`](#compute_fork_version)
    - [`compute_fork_digest`](#compute_fork_digest)
  - [MetaData](#metadata)
  - [Maximum message sizes](#maximum-message-sizes)
    - [`max_compressed_len`](#max_compressed_len)
    - [`max_message_size`](#max_message_size)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
        - [`beacon_aggregate_and_proof`](#beacon_aggregate_and_proof)
        - [`voluntary_exit`](#voluntary_exit)
        - [`proposer_slashing`](#proposer_slashing)
        - [`attester_slashing`](#attester_slashing)
      - [Attestation subnets](#attestation-subnets)
        - [`beacon_attestation_{subnet_id}`](#beacon_attestation_subnet_id)
      - [Attestations and Aggregation](#attestations-and-aggregation)
    - [Encodings](#encodings)
    - [Gossipsub size limits](#gossipsub-size-limits)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Protocol identification](#protocol-identification)
    - [Req/Resp interaction](#reqresp-interaction)
      - [Requesting side](#requesting-side)
      - [Responding side](#responding-side)
    - [Encoding strategies](#encoding-strategies)
      - [SSZ-snappy encoding strategy](#ssz-snappy-encoding-strategy)
    - [Messages](#messages)
      - [Status v1](#status-v1)
      - [Goodbye v1](#goodbye-v1)
      - [BeaconBlocksByRange v1](#beaconblocksbyrange-v1)
      - [BeaconBlocksByRoot v1](#beaconblocksbyroot-v1)
      - [Ping v1](#ping-v1)
      - [GetMetaData v1](#getmetadata-v1)
  - [The discovery domain: discv5](#the-discovery-domain-discv5)
    - [Integration into libp2p stacks](#integration-into-libp2p-stacks)
    - [ENR structure](#enr-structure)
      - [Attestation subnet bitfield](#attestation-subnet-bitfield)
      - [`eth2` field](#eth2-field)
  - [Attestation subnet subscription](#attestation-subnet-subscription)
- [Design decision rationale](#design-decision-rationale)
  - [Transport](#transport-1)
    - [Why are we defining specific transports?](#why-are-we-defining-specific-transports)
    - [Can clients support other transports/handshakes than the ones mandated by the spec?](#can-clients-support-other-transportshandshakes-than-the-ones-mandated-by-the-spec)
    - [What are the advantages of using TCP/QUIC/Websockets?](#what-are-the-advantages-of-using-tcpquicwebsockets)
    - [Why do we not just support a single transport?](#why-do-we-not-just-support-a-single-transport)
    - [Why are we not using QUIC from the start?](#why-are-we-not-using-quic-from-the-start)
  - [Multiplexing](#multiplexing-1)
    - [Why are we using mplex/yamux?](#why-are-we-using-mplexyamux)
  - [Protocol negotiation](#protocol-negotiation-1)
    - [When is multiselect 2.0 due and why do we plan to migrate to it?](#when-is-multiselect-20-due-and-why-do-we-plan-to-migrate-to-it)
    - [What is the difference between connection-level and stream-level protocol negotiation?](#what-is-the-difference-between-connection-level-and-stream-level-protocol-negotiation)
  - [Encryption](#encryption)
    - [Why are we not supporting SecIO?](#why-are-we-not-supporting-secio)
    - [Why are we using Noise?](#why-are-we-using-noise)
    - [Why are we using encryption at all?](#why-are-we-using-encryption-at-all)
  - [Gossipsub](#gossipsub)
    - [Why are we using a pub/sub algorithm for block and attestation propagation?](#why-are-we-using-a-pubsub-algorithm-for-block-and-attestation-propagation)
    - [Why are we using topics to segregate encodings, yet only support one encoding?](#why-are-we-using-topics-to-segregate-encodings-yet-only-support-one-encoding)
    - [How do we upgrade gossip channels (e.g. changes in encoding, compression)?](#how-do-we-upgrade-gossip-channels-eg-changes-in-encoding-compression)
    - [Why must all clients use the same gossip topic instead of one negotiated between each peer pair?](#why-must-all-clients-use-the-same-gossip-topic-instead-of-one-negotiated-between-each-peer-pair)
    - [Why are the topics strings and not hashes?](#why-are-the-topics-strings-and-not-hashes)
    - [Why are we using the `StrictNoSign` signature policy?](#why-are-we-using-the-strictnosign-signature-policy)
    - [Why are we overriding the default libp2p pubsub `message-id`?](#why-are-we-overriding-the-default-libp2p-pubsub-message-id)
    - [Why are these specific gossip parameters chosen?](#why-are-these-specific-gossip-parameters-chosen)
    - [Why is there `MAXIMUM_GOSSIP_CLOCK_DISPARITY` when validating slot ranges of messages in gossip subnets?](#why-is-there-maximum_gossip_clock_disparity-when-validating-slot-ranges-of-messages-in-gossip-subnets)
    - [Why are there `ATTESTATION_SUBNET_COUNT` attestation subnets?](#why-are-there-attestation_subnet_count-attestation-subnets)
    - [Why are attestations limited to be broadcast on gossip channels within `SLOTS_PER_EPOCH` slots?](#why-are-attestations-limited-to-be-broadcast-on-gossip-channels-within-slots_per_epoch-slots)
    - [Why are aggregate attestations broadcast to the global topic as `AggregateAndProof`s rather than just as `Attestation`s?](#why-are-aggregate-attestations-broadcast-to-the-global-topic-as-aggregateandproofs-rather-than-just-as-attestations)
    - [Why are we sending entire objects in the pubsub and not just hashes?](#why-are-we-sending-entire-objects-in-the-pubsub-and-not-just-hashes)
    - [Should clients gossip blocks if they cannot validate the proposer signature due to not yet being synced, not knowing the head block, etc?](#should-clients-gossip-blocks-if-they-cannot-validate-the-proposer-signature-due-to-not-yet-being-synced-not-knowing-the-head-block-etc)
    - [How are we going to discover peers in a gossipsub topic?](#how-are-we-going-to-discover-peers-in-a-gossipsub-topic)
    - [How should fork version be used in practice?](#how-should-fork-version-be-used-in-practice)
  - [Req/Resp](#reqresp)
    - [Why segregate requests into dedicated protocol IDs?](#why-segregate-requests-into-dedicated-protocol-ids)
    - [Why are messages length-prefixed with a protobuf varint in the SSZ-encoding?](#why-are-messages-length-prefixed-with-a-protobuf-varint-in-the-ssz-encoding)
    - [Why do we version protocol strings with ordinals instead of semver?](#why-do-we-version-protocol-strings-with-ordinals-instead-of-semver)
    - [Why is it called Req/Resp and not RPC?](#why-is-it-called-reqresp-and-not-rpc)
    - [What is a typical rate limiting strategy?](#what-is-a-typical-rate-limiting-strategy)
    - [Why do we allow empty responses in block requests?](#why-do-we-allow-empty-responses-in-block-requests)
    - [Why does `BeaconBlocksByRange` let the server choose which branch to send blocks from?](#why-does-beaconblocksbyrange-let-the-server-choose-which-branch-to-send-blocks-from)
    - [Why are `BlocksByRange` requests only required to be served for the latest `MIN_EPOCHS_FOR_BLOCK_REQUESTS` epochs?](#why-are-blocksbyrange-requests-only-required-to-be-served-for-the-latest-min_epochs_for_block_requests-epochs)
    - [Why must the proposer signature be checked when backfilling blocks in the database?](#why-must-the-proposer-signature-be-checked-when-backfilling-blocks-in-the-database)
    - [What's the effect of empty slots on the sync algorithm?](#whats-the-effect-of-empty-slots-on-the-sync-algorithm)
  - [Discovery](#discovery)
    - [Why are we using discv5 and not libp2p Kademlia DHT?](#why-are-we-using-discv5-and-not-libp2p-kademlia-dht)
    - [What is the difference between an ENR and a multiaddr, and why are we using ENRs?](#what-is-the-difference-between-an-enr-and-a-multiaddr-and-why-are-we-using-enrs)
    - [Why do we not form ENRs and find peers until genesis block/state is known?](#why-do-we-not-form-enrs-and-find-peers-until-genesis-blockstate-is-known)
  - [Compression/Encoding](#compressionencoding)
    - [Why are we using SSZ for encoding?](#why-are-we-using-ssz-for-encoding)
    - [Why are we compressing, and at which layers?](#why-are-we-compressing-and-at-which-layers)
    - [Why are we using Snappy for compression?](#why-are-we-using-snappy-for-compression)
    - [Can I get access to unencrypted bytes on the wire for debugging purposes?](#can-i-get-access-to-unencrypted-bytes-on-the-wire-for-debugging-purposes)
    - [What are SSZ type size bounds?](#what-are-ssz-type-size-bounds)
    - [Why is the message size defined in terms of application payload?](#why-is-the-message-size-defined-in-terms-of-application-payload)
    - [Why is there a limit on message sizes at all?](#why-is-there-a-limit-on-message-sizes-at-all)
- [libp2p implementations matrix](#libp2p-implementations-matrix)

<!-- mdformat-toc end -->

## Introduction

This document contains the networking specification for Phase 0.

It consists of four main sections:

1. A specification of the network fundamentals.
2. A specification of the three network interaction *domains* of the
   proof-of-stake consensus layer: (a) the gossip domain, (b) the discovery
   domain, and (c) the Req/Resp domain.
3. The rationale and further explanation for the design choices made in the
   previous two sections.
4. An analysis of the maturity/state of the libp2p features required by this
   spec across the languages in which clients are being developed.

## Network fundamentals

This section outlines the specification for the networking stack in Ethereum
consensus-layer clients.

### Transport

Even though libp2p is a multi-transport stack (designed to listen on multiple
simultaneous transports and endpoints transparently), we hereby define a profile
for basic interoperability.

All implementations MUST support the TCP libp2p transport, MAY support the QUIC
(UDP) libp2p transport, and MUST be enabled for both dialing and listening (i.e.
outbound and inbound connections). The libp2p TCP and QUIC (UDP) transports
support listening on IPv4 and IPv6 addresses (and on multiple simultaneously).

Clients must support listening on at least one of IPv4 or IPv6. Clients that do
_not_ have support for listening on IPv4 SHOULD be cognizant of the potential
disadvantages in terms of Internet-wide routability/support. Clients MAY choose
to listen only on IPv6, but MUST be capable of dialing both IPv4 and IPv6
addresses.

All listening endpoints must be publicly dialable, and thus not rely on libp2p
circuit relay, AutoNAT, or AutoRelay facilities. (Usage of circuit relay,
AutoNAT, or AutoRelay will be specifically re-examined soon.)

Nodes operating behind a NAT, or otherwise undialable by default (e.g. container
runtime, firewall, etc.), MUST have their infrastructure configured to enable
inbound traffic on the announced public listening endpoint.

### Encryption and identification

The [Libp2p-noise](https://github.com/libp2p/specs/tree/master/noise) secure
channel handshake with `secp256k1` identities will be used for encryption.

As specified in the libp2p specification, clients MUST support the `XX`
handshake pattern.

### Protocol negotiation

Clients MUST use exact equality when negotiating protocol versions to use and
MAY use the version to give priority to higher version numbers.

Clients MUST support
[multistream-select 1.0](https://github.com/multiformats/multistream-select/)
and MAY support [multiselect 2.0](https://github.com/libp2p/specs/pull/95) when
the spec solidifies. Once all clients have implementations for multiselect 2.0,
multistream-select 1.0 MAY be phased out.

### Multiplexing

During connection bootstrapping, libp2p dynamically negotiates a mutually
supported multiplexing method to conduct parallel conversations. This applies to
transports that are natively incapable of multiplexing (e.g. TCP, WebSockets,
WebRTC), and is omitted for capable transports (e.g. QUIC).

Two multiplexers are commonplace in libp2p implementations:
[mplex](https://github.com/libp2p/specs/tree/master/mplex) and
[yamux](https://github.com/libp2p/specs/blob/master/yamux/README.md). Their
protocol IDs are, respectively: `/mplex/6.7.0` and `/yamux/1.0.0`.

Clients MUST support [mplex](https://github.com/libp2p/specs/tree/master/mplex)
and MAY support
[yamux](https://github.com/libp2p/specs/blob/master/yamux/README.md). If both
are supported by the client, yamux MUST take precedence during negotiation. See
the [Rationale](#design-decision-rationale) section below for tradeoffs.

## Consensus-layer network interaction domains

### Custom types

We define the following Python custom types for type hinting and readability:

| Name       | SSZ equivalent | Description       |
| ---------- | -------------- | ----------------- |
| `NodeID`   | `uint256`      | node identifier   |
| `SubnetID` | `uint64`       | subnet identifier |

### Constants

| Name           | Value |               Unit               |
| -------------- | ----- | :------------------------------: |
| `NODE_ID_BITS` | `256` | The bit length of uint256 is 256 |

### Configuration

This section outlines configurations that are used in this spec.

| Name                                 | Value                                                                                  | Description                                                                           |
| ------------------------------------ | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `MAX_PAYLOAD_SIZE`                   | `10 * 2**20` (= 10485760, 10 MiB)                                                      | The maximum allowed size of uncompressed payload in gossipsub messages and RPC chunks |
| `MAX_REQUEST_BLOCKS`                 | `2**10` (= 1024)                                                                       | Maximum number of blocks in a single request                                          |
| `EPOCHS_PER_SUBNET_SUBSCRIPTION`     | `2**8` (= 256)                                                                         | Number of epochs on a subnet subscription (~27 hours)                                 |
| `MIN_EPOCHS_FOR_BLOCK_REQUESTS`      | `MIN_VALIDATOR_WITHDRAWABILITY_DELAY + CHURN_LIMIT_QUOTIENT // 2` (= 33024, ~5 months) | The minimum epoch range over which a node must serve blocks                           |
| `ATTESTATION_PROPAGATION_SLOT_RANGE` | `32`                                                                                   | The maximum number of slots during which an attestation can be propagated             |
| `MAXIMUM_GOSSIP_CLOCK_DISPARITY`     | `500`                                                                                  | The maximum **milliseconds** of clock disparity assumed between honest nodes          |
| `MESSAGE_DOMAIN_INVALID_SNAPPY`      | `DomainType('0x00000000')`                                                             | 4-byte domain for gossip message-id isolation of *invalid* snappy messages            |
| `MESSAGE_DOMAIN_VALID_SNAPPY`        | `DomainType('0x01000000')`                                                             | 4-byte domain for gossip message-id isolation of *valid* snappy messages              |
| `SUBNETS_PER_NODE`                   | `2`                                                                                    | The number of long-lived subnets a beacon node should be subscribed to                |
| `ATTESTATION_SUBNET_COUNT`           | `2**6` (= 64)                                                                          | The number of attestation subnets used in the gossipsub protocol.                     |
| `ATTESTATION_SUBNET_EXTRA_BITS`      | `0`                                                                                    | The number of extra bits of a NodeId to use when mapping to a subscribed subnet       |
| `ATTESTATION_SUBNET_PREFIX_BITS`     | `int(ceillog2(ATTESTATION_SUBNET_COUNT) + ATTESTATION_SUBNET_EXTRA_BITS)`              |                                                                                       |
| `MAX_CONCURRENT_REQUESTS`            | `2`                                                                                    | Maximum number of concurrent requests per protocol ID that a client may issue         |

### Helpers

#### `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    return GENESIS_FORK_VERSION
```

#### `compute_fork_digest`

```python
def compute_fork_digest(
    genesis_validators_root: Root,
    epoch: Epoch,
) -> ForkDigest:
    """
    Return the 4-byte fork digest for the ``genesis_validators_root`` at a given ``epoch``.

    This is a digest primarily used for domain separation on the p2p layer.
    4-bytes suffices for practical separation of forks/chains.
    """
    fork_version = compute_fork_version(epoch)
    base_digest = compute_fork_data_root(fork_version, genesis_validators_root)
    return ForkDigest(base_digest[:4])
```

### MetaData

Clients MUST locally store the following `MetaData`:

```
(
  seq_number: uint64
  attnets: Bitvector[ATTESTATION_SUBNET_COUNT]
)
```

Where

- `seq_number` is a `uint64` starting at `0` used to version the node's
  metadata. If any other field in the local `MetaData` changes, the node MUST
  increment `seq_number` by 1.
- `attnets` is a `Bitvector` representing the node's persistent attestation
  subnet subscriptions.

*Note*: `MetaData.seq_number` is used for versioning of the node's metadata, is
entirely independent of the ENR sequence number, and will in most cases be out
of sync with the ENR sequence number.

### Maximum message sizes

Maximum message sizes are derived from the maximum payload size that the network
can carry according to the following functions:

#### `max_compressed_len`

```python
def max_compressed_len(n: uint64) -> uint64:
    # Worst-case compressed length for a given payload of size n when using snappy:
    # https://github.com/google/snappy/blob/32ded457c0b1fe78ceb8397632c416568d6714a0/snappy.cc#L218C1-L218C47
    return uint64(32 + n + n / 6)
```

#### `max_message_size`

```python
def max_message_size() -> uint64:
    # Allow 1024 bytes for framing and encoding overhead but at least 1MiB in case MAX_PAYLOAD_SIZE is small.
    return max(max_compressed_len(MAX_PAYLOAD_SIZE) + 1024, 1024 * 1024)
```

### The gossip domain: gossipsub

Clients MUST support the
[gossipsub v1](https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/gossipsub-v1.0.md)
libp2p Protocol including the
[gossipsub v1.1](https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/gossipsub-v1.1.md)
extension.

**Protocol ID:** `/meshsub/1.1.0`

**Gossipsub Parameters**

The following gossipsub
[parameters](https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/gossipsub-v1.0.md#parameters)
will be used:

- `D` (topic stable mesh target count): 8
- `D_low` (topic stable mesh low watermark): 6
- `D_high` (topic stable mesh high watermark): 12
- `D_lazy` (gossip target): 6
- `heartbeat_interval` (frequency of heartbeat, seconds): 0.7
- `fanout_ttl` (ttl for fanout maps for topics we are not subscribed to but have
  published to, seconds): 60
- `mcache_len` (number of windows to retain full messages in cache for `IWANT`
  responses): 6
- `mcache_gossip` (number of windows to gossip about): 3
- `seen_ttl` (expiry time for cache of seen message ids, seconds):
  SECONDS_PER_SLOT * SLOTS_PER_EPOCH * 2

*Note*: Gossipsub v1.1 introduces a number of
[additional parameters](https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/gossipsub-v1.1.md#overview-of-new-parameters)
for peer scoring and other attack mitigations. These are currently under
investigation and will be spec'd and released to mainnet when they are ready.

#### Topics and messages

Topics are plain UTF-8 strings and are encoded on the wire as determined by
protobuf (gossipsub messages are enveloped in protobuf messages). Topic strings
have form: `/eth2/ForkDigestValue/Name/Encoding`. This defines both the type of
data being sent on the topic and how the data field of the message is encoded.

- `ForkDigestValue` - the lowercase hex-encoded (no "0x" prefix) bytes of
  `compute_fork_digest(genesis_validators_root, epoch)` where
  - `genesis_validators_root` is the static `Root` found in
    `state.genesis_validators_root`
  - `epoch` is the context epoch of the message to be sent on the topic
- `Name` - see table below
- `Encoding` - the encoding strategy describes a specific representation of
  bytes that will be transmitted over the wire. See the [Encodings](#Encodings)
  section for further details.

Clients MUST reject messages with an unknown topic.

*Note*: `ForkDigestValue` is composed of values that are not known until the
genesis block/state are available. Due to this, clients SHOULD NOT subscribe to
gossipsub topics until these genesis values are known.

The optional `from` (1), `seqno` (3), `signature` (5) and `key` (6) protobuf
fields are omitted from the message, since messages are identified by content,
anonymous, and signed where necessary in the application layer. Starting from
Gossipsub v1.1, clients MUST enforce this by applying the `StrictNoSign`
[signature policy](https://github.com/libp2p/specs/blob/master/pubsub/README.md#signature-policy-options).

The `message-id` of a gossipsub message MUST be the following 20 byte value
computed from the message data:

- If `message.data` has a valid snappy decompression, set `message-id` to the
  first 20 bytes of the `SHA256` hash of the concatenation of
  `MESSAGE_DOMAIN_VALID_SNAPPY` with the snappy decompressed message data, i.e.
  `SHA256(MESSAGE_DOMAIN_VALID_SNAPPY + snappy_decompress(message.data))[:20]`.
- Otherwise, set `message-id` to the first 20 bytes of the `SHA256` hash of the
  concatenation of `MESSAGE_DOMAIN_INVALID_SNAPPY` with the raw message data,
  i.e. `SHA256(MESSAGE_DOMAIN_INVALID_SNAPPY + message.data)[:20]`.

Where relevant, clients MUST reject messages with `message-id` sizes other than
20 bytes.

*Note*: The above logic handles two exceptional cases: (1) multiple snappy
`data` can decompress to the same value, and (2) some message `data` can fail to
snappy decompress altogether.

The payload is carried in the `data` field of a gossipsub message, and varies
depending on the topic:

| Name                             | Message Type              |
| -------------------------------- | ------------------------- |
| `beacon_block`                   | `SignedBeaconBlock`       |
| `beacon_aggregate_and_proof`     | `SignedAggregateAndProof` |
| `beacon_attestation_{subnet_id}` | `Attestation`             |
| `voluntary_exit`                 | `SignedVoluntaryExit`     |
| `proposer_slashing`              | `ProposerSlashing`        |
| `attester_slashing`              | `AttesterSlashing`        |

Clients MUST reject (fail validation) messages containing an incorrect type, or
invalid payload.

When processing incoming gossip, clients MAY descore or disconnect peers who
fail to observe these constraints.

For any optional queueing, clients SHOULD maintain maximum queue sizes to avoid
DoS vectors.

Gossipsub v1.1 introduces
[Extended Validators](https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/gossipsub-v1.1.md#extended-validators)
for the application to aid in the gossipsub peer-scoring scheme. We utilize
`ACCEPT`, `REJECT`, and `IGNORE`. For each gossipsub topic, there are
application specific validations. If all validations pass, return `ACCEPT`. If
one or more validations fail while processing the items in order, return either
`REJECT` or `IGNORE` as specified in the prefix of the particular condition.

##### Global topics

There are two primary global topics used to propagate beacon blocks
(`beacon_block`) and aggregate attestations (`beacon_aggregate_and_proof`) to
all nodes on the network.

There are three additional global topics that are used to propagate lower
frequency validator messages (`voluntary_exit`, `proposer_slashing`, and
`attester_slashing`).

###### `beacon_block`

The `beacon_block` topic is used solely for propagating new signed beacon blocks
to all nodes on the networks. Signed blocks are sent in their entirety.

The following validations MUST pass before forwarding the `signed_beacon_block`
on the network.

- _[IGNORE]_ The block is not from a future slot (with a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. validate that
  `signed_beacon_block.message.slot <= current_slot` (a client MAY queue future
  blocks for processing at the appropriate slot).
- _[IGNORE]_ The block is from a slot greater than the latest finalized slot --
  i.e. validate that
  `signed_beacon_block.message.slot > compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)`
  (a client MAY choose to validate and store such blocks for additional purposes
  -- e.g. slashing detection, archive nodes, etc).
- _[IGNORE]_ The block is the first block with valid signature received for the
  proposer for the slot, `signed_beacon_block.message.slot`.
- _[REJECT]_ The proposer signature, `signed_beacon_block.signature`, is valid
  with respect to the `proposer_index` pubkey.
- _[IGNORE]_ The block's parent (defined by `block.parent_root`) has been seen
  (via gossip or non-gossip sources) (a client MAY queue blocks for processing
  once the parent block is retrieved).
- _[REJECT]_ The block's parent (defined by `block.parent_root`) passes
  validation.
- _[REJECT]_ The block is from a higher slot than its parent.
- _[REJECT]_ The current `finalized_checkpoint` is an ancestor of `block` --
  i.e.
  `get_checkpoint_block(store, block.parent_root, store.finalized_checkpoint.epoch) == store.finalized_checkpoint.root`
- _[REJECT]_ The block is proposed by the expected `proposer_index` for the
  block's slot in the context of the current shuffling (defined by
  `parent_root`/`slot`). If the `proposer_index` cannot immediately be verified
  against the expected shuffling, the block MAY be queued for later processing
  while proposers for the block's branch are calculated -- in such a case _do
  not_ `REJECT`, instead `IGNORE` this message.

###### `beacon_aggregate_and_proof`

The `beacon_aggregate_and_proof` topic is used to propagate aggregated
attestations (as `SignedAggregateAndProof`s) to subscribing nodes (typically
validators) to be included in future blocks.

We define the following variables for convenience:

- `aggregate_and_proof = signed_aggregate_and_proof.message`
- `aggregate = aggregate_and_proof.aggregate`
- `index = aggregate.data.index`
- `aggregation_bits = aggregate.aggregation_bits`

The following validations MUST pass before forwarding the
`signed_aggregate_and_proof` on the network.

- _[REJECT]_ The committee index is within the expected range -- i.e.
  `index < get_committee_count_per_slot(state, aggregate.data.target.epoch)`.
- _[IGNORE]_ `aggregate.data.slot` is within the last
  `ATTESTATION_PROPAGATION_SLOT_RANGE` slots (with a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e.
  `aggregate.data.slot + ATTESTATION_PROPAGATION_SLOT_RANGE >= current_slot >= aggregate.data.slot`
  (a client MAY queue future aggregates for processing at the appropriate slot).
- _[REJECT]_ The aggregate attestation's epoch matches its target -- i.e.
  `aggregate.data.target.epoch == compute_epoch_at_slot(aggregate.data.slot)`
- _[REJECT]_ The number of aggregation bits matches the committee size -- i.e.
  `len(aggregation_bits) == len(get_beacon_committee(state, aggregate.data.slot, index))`.
- _[REJECT]_ The aggregate attestation has participants -- that is,
  `len(get_attesting_indices(state, aggregate)) >= 1`.
- _[IGNORE]_ A valid aggregate attestation defined by
  `hash_tree_root(aggregate.data)` whose `aggregation_bits` is a non-strict
  superset has _not_ already been seen. (via aggregate gossip, within a verified
  block, or through the creation of an equivalent aggregate locally).
- _[IGNORE]_ The `aggregate` is the first valid aggregate received for the
  aggregator with index `aggregate_and_proof.aggregator_index` for the epoch
  `aggregate.data.target.epoch`.
- _[REJECT]_ The attestation has participants -- that is,
  `len(get_attesting_indices(state, aggregate)) >= 1`.
- _[REJECT]_ `aggregate_and_proof.selection_proof` selects the validator as an
  aggregator for the slot -- i.e.
  `is_aggregator(state, aggregate.data.slot, index, aggregate_and_proof.selection_proof)`
  returns `True`.
- _[REJECT]_ The aggregator's validator index is within the committee -- i.e.
  `aggregate_and_proof.aggregator_index in get_beacon_committee(state, aggregate.data.slot, index)`.
- _[REJECT]_ The `aggregate_and_proof.selection_proof` is a valid signature of
  the `aggregate.data.slot` by the validator with index
  `aggregate_and_proof.aggregator_index`.
- _[REJECT]_ The aggregator signature, `signed_aggregate_and_proof.signature`,
  is valid.
- _[REJECT]_ The signature of `aggregate` is valid.
- _[IGNORE]_ The block being voted for (`aggregate.data.beacon_block_root`) has
  been seen (via gossip or non-gossip sources) (a client MAY queue aggregates
  for processing once block is retrieved).
- _[REJECT]_ The block being voted for (`aggregate.data.beacon_block_root`)
  passes validation.
- _[REJECT]_ The aggregate attestation's target block is an ancestor of the
  block named in the LMD vote -- i.e.
  `get_checkpoint_block(store, aggregate.data.beacon_block_root, aggregate.data.target.epoch) == aggregate.data.target.root`
- _[IGNORE]_ The current `finalized_checkpoint` is an ancestor of the `block`
  defined by `aggregate.data.beacon_block_root` -- i.e.
  `get_checkpoint_block(store, aggregate.data.beacon_block_root, finalized_checkpoint.epoch) == store.finalized_checkpoint.root`

###### `voluntary_exit`

The `voluntary_exit` topic is used solely for propagating signed voluntary
validator exits to proposers on the network. Signed voluntary exits are sent in
their entirety.

The following validations MUST pass before forwarding the
`signed_voluntary_exit` on to the network.

- _[IGNORE]_ The voluntary exit is the first valid voluntary exit received for
  the validator with index `signed_voluntary_exit.message.validator_index`.
- _[REJECT]_ All of the conditions within `process_voluntary_exit` pass
  validation.

###### `proposer_slashing`

The `proposer_slashing` topic is used solely for propagating proposer slashings
to proposers on the network. Proposer slashings are sent in their entirety.

The following validations MUST pass before forwarding the `proposer_slashing` on
to the network.

- _[IGNORE]_ The proposer slashing is the first valid proposer slashing received
  for the proposer with index
  `proposer_slashing.signed_header_1.message.proposer_index`.
- _[REJECT]_ All of the conditions within `process_proposer_slashing` pass
  validation.

###### `attester_slashing`

The `attester_slashing` topic is used solely for propagating attester slashings
to proposers on the network. Attester slashings are sent in their entirety.

Clients who receive an attester slashing on this topic MUST validate the
conditions within `process_attester_slashing` before forwarding it across the
network.

- _[IGNORE]_ At least one index in the intersection of the attesting indices of
  each attestation has not yet been seen in any prior `attester_slashing` (i.e.
  `attester_slashed_indices = set(attestation_1.attesting_indices).intersection(attestation_2.attesting_indices)`,
  verify if
  `any(attester_slashed_indices.difference(prior_seen_attester_slashed_indices))`).
- _[REJECT]_ All of the conditions within `process_attester_slashing` pass
  validation.

##### Attestation subnets

Attestation subnets are used to propagate unaggregated attestations to
subsections of the network.

###### `beacon_attestation_{subnet_id}`

The `beacon_attestation_{subnet_id}` topics are used to propagate unaggregated
attestations to the subnet `subnet_id` (typically beacon and persistent
committees) to be aggregated before being gossiped to
`beacon_aggregate_and_proof`.

We define the following variables for convenience:

- `index = attestation.data.index`
- `aggregation_bits = attestation.aggregation_bits`

The following validations MUST pass before forwarding the `attestation` on the
subnet.

- _[REJECT]_ The committee index is within the expected range -- i.e.
  `index < get_committee_count_per_slot(state, attestation.data.target.epoch)`.
- _[REJECT]_ The attestation is for the correct subnet -- i.e.
  `compute_subnet_for_attestation(committees_per_slot, attestation.data.slot, index) == subnet_id`,
  where
  `committees_per_slot = get_committee_count_per_slot(state, attestation.data.target.epoch)`,
  which may be pre-computed along with the committee information for the
  signature check.
- _[IGNORE]_ `attestation.data.slot` is within the last
  `ATTESTATION_PROPAGATION_SLOT_RANGE` slots (within a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e.
  `attestation.data.slot + ATTESTATION_PROPAGATION_SLOT_RANGE >= current_slot >= attestation.data.slot`
  (a client MAY queue future attestations for processing at the appropriate
  slot).
- _[REJECT]_ The attestation's epoch matches its target -- i.e.
  `attestation.data.target.epoch == compute_epoch_at_slot(attestation.data.slot)`
- _[REJECT]_ The attestation is unaggregated -- that is, it has exactly one
  participating validator (`len([bit for bit in aggregation_bits if bit]) == 1`,
  i.e. exactly 1 bit is set).
- _[REJECT]_ The number of aggregation bits matches the committee size -- i.e.
  `len(aggregation_bits) == len(get_beacon_committee(state, attestation.data.slot, index))`.
- _[IGNORE]_ There has been no other valid attestation seen on an attestation
  subnet that has an identical `attestation.data.target.epoch` and participating
  validator index.
- _[REJECT]_ The signature of `attestation` is valid.
- _[IGNORE]_ The block being voted for (`attestation.data.beacon_block_root`)
  has been seen (via gossip or non-gossip sources) (a client MAY queue
  attestations for processing once block is retrieved).
- _[REJECT]_ The block being voted for (`attestation.data.beacon_block_root`)
  passes validation.
- _[REJECT]_ The attestation's target block is an ancestor of the block named in
  the LMD vote -- i.e.
  `get_checkpoint_block(store, attestation.data.beacon_block_root, attestation.data.target.epoch) == attestation.data.target.root`
- _[IGNORE]_ The current `finalized_checkpoint` is an ancestor of the `block`
  defined by `attestation.data.beacon_block_root` -- i.e.
  `get_checkpoint_block(store, attestation.data.beacon_block_root, store.finalized_checkpoint.epoch) == store.finalized_checkpoint.root`

##### Attestations and Aggregation

Attestation broadcasting is grouped into subnets defined by a topic. The number
of subnets is defined via `ATTESTATION_SUBNET_COUNT`. The correct subnet for an
attestation can be calculated with `compute_subnet_for_attestation`.
`beacon_attestation_{subnet_id}` topics, are rotated through throughout the
epoch in a similar fashion to rotating through shards in committees (future
beacon-chain upgrade). The subnets are rotated through with
`committees_per_slot = get_committee_count_per_slot(state, attestation.data.target.epoch)`
subnets per slot.

Unaggregated attestations are sent as `Attestation`s to the subnet topic,
`beacon_attestation_{compute_subnet_for_attestation(committees_per_slot, attestation.data.slot, attestation.data.index)}`
as `Attestation`s.

Aggregated attestations are sent to the `beacon_aggregate_and_proof` topic as
`AggregateAndProof`s.

#### Encodings

Topics are post-fixed with an encoding. Encodings define how the payload of a
gossipsub message is encoded.

- `ssz_snappy` - All objects are SSZ-encoded and then compressed with
  [Snappy](https://github.com/google/snappy) block compression. Example: The
  beacon aggregate attestation topic string is
  `/eth2/446a7232/beacon_aggregate_and_proof/ssz_snappy`, the fork digest is
  `446a7232` and the data field of a gossipsub message is an `AggregateAndProof`
  that has been SSZ-encoded and then compressed with Snappy.

Snappy has two formats: "block" and "frames" (streaming). Gossip messages remain
relatively small (100s of bytes to 100s of kilobytes) so
[basic snappy block compression](https://github.com/google/snappy/blob/master/format_description.txt)
is used to avoid the additional overhead associated with snappy frames.

Implementations MUST use a single encoding for gossip. Changing an encoding will
require coordination between participating implementations.

#### Gossipsub size limits

Size limits are placed both on the
[`RPCMsg`](https://github.com/libp2p/specs/blob/b5f7fce29b32d4c7d0efe37b019936a11e5db872/pubsub/README.md#the-rpc)
frame as well as the encoded payload in each
[`Message`](https://github.com/libp2p/specs/blob/b5f7fce29b32d4c7d0efe37b019936a11e5db872/pubsub/README.md#the-message).

Clients MUST reject and MUST NOT emit or propagate messages whose size exceed
the following limits:

- The size of the encoded `RPCMsg` (including control messages, framing, topics,
  etc) must not exceed `max_message_size()`.
- The size of the compressed payload in the `Message.data` field must not exceed
  `max_compressed_len(MAX_PAYLOAD_SIZE)`.
- The size of the uncompressed payload must not exceed `MAX_PAYLOAD_SIZE` or the
  [type-specific SSZ bound](#what-are-ssz-type-size-bounds), whichever is lower.

### The Req/Resp domain

#### Protocol identification

Each message type is segregated into its own libp2p protocol ID, which is a
case-sensitive UTF-8 string of the form:

```
/ProtocolPrefix/MessageName/SchemaVersion/Encoding
```

With:

- `ProtocolPrefix` - messages are grouped into families identified by a shared
  libp2p protocol name prefix. In this case, we use `/eth2/beacon_chain/req`.
- `MessageName` - each request is identified by a name consisting of English
  alphabet, digits and underscores (`_`).
- `SchemaVersion` - an ordinal version number (e.g. 1, 2, 3…). Each schema is
  versioned to facilitate backward and forward-compatibility when possible.
- `Encoding` - while the schema defines the data types in more abstract terms,
  the encoding strategy describes a specific representation of bytes that will
  be transmitted over the wire. See the [Encodings](#Encoding-strategies)
  section for further details.

This protocol segregation allows libp2p `multistream-select 1.0` /
`multiselect 2.0` to handle the request type, version, and encoding negotiation
before establishing the underlying streams.

#### Req/Resp interaction

We use ONE stream PER request/response interaction. Streams are closed when the
interaction finishes, whether in success or in error.

Request/response messages MUST adhere to the encoding specified in the protocol
name and follow this structure (relaxed BNF grammar):

```
request   ::= <encoding-dependent-header> | <encoded-payload>
response  ::= <response_chunk>*
response_chunk  ::= <result> | <encoding-dependent-header> | <encoded-payload>
result    ::= “0” | “1” | “2” | [“128” ... ”255”]
```

The encoding-dependent header may carry metadata or assertions such as the
encoded payload length, for integrity and attack proofing purposes. Because
req/resp streams are single-use and stream closures implicitly delimit the
boundaries, it is not strictly necessary to length-prefix payloads; however,
certain encodings like SSZ do, for added security.

A `response` is formed by zero or more `response_chunk`s. Responses that consist
of a single SSZ-list (such as `BlocksByRange` and `BlocksByRoot`) send each list
item as a `response_chunk`. All other response types (non-Lists) send a single
`response_chunk`.

For both `request`s and `response`s, the `encoding-dependent-header` MUST be
valid, and the `encoded-payload` must be valid within the constraints of the
`encoding-dependent-header`. This includes type-specific bounds on payload size
for some encoding strategies. Regardless of these type specific bounds, a global
maximum uncompressed byte size of `MAX_PAYLOAD_SIZE` MUST be applied to all
method response chunks.

Clients MUST ensure that lengths are within these bounds; if not, they SHOULD
reset the stream immediately. Clients tracking peer reputation MAY decrement the
score of the misbehaving peer under this circumstance.

##### Requesting side

Once a new stream with the protocol ID for the request type has been negotiated,
the full request message SHOULD be sent immediately. The request MUST be encoded
according to the encoding strategy.

The requester MUST close the write side of the stream once it finishes writing
the request message. At this point, the stream will be half-closed.

The requester MUST NOT make more than `MAX_CONCURRENT_REQUESTS` concurrent
requests with the same protocol ID.

If a timeout occurs or the response is no longer relevant, the requester SHOULD
reset the stream.

A requester SHOULD read from the stream until either:

1. An error result is received in one of the chunks (the error payload MAY be
   read before stopping).
2. The responder closes the stream.
3. Any part of the `response_chunk` fails validation.
4. The maximum number of requested chunks are read.

For requests consisting of a single valid `response_chunk`, the requester SHOULD
read the chunk fully, as defined by the `encoding-dependent-header`, before
closing the stream.

##### Responding side

Once a new stream with the protocol ID for the request type has been negotiated,
the responder SHOULD process the incoming request and MUST validate it before
processing it. Request processing and validation MUST be done according to the
encoding strategy, until EOF (denoting stream half-closure by the requester).

The responder MUST:

1. Use the encoding strategy to read the optional header.
2. If there are any length assertions for length `N`, it should read exactly `N`
   bytes from the stream, at which point an EOF should arise (no more bytes).
   Should this not be the case, it should be treated as a failure.
3. Deserialize the expected type, and process the request.
4. Write the response which may consist of zero or more `response_chunk`s
   (result, optional header, payload).
5. Close their write side of the stream. At this point, the stream will be fully
   closed.

If steps (1), (2), or (3) fail due to invalid, malformed, or inconsistent data,
the responder MUST respond in error. Clients tracking peer reputation MAY record
such failures, as well as unexpected events, e.g. early stream resets.

The responder MAY rate-limit chunks by withholding each chunk until capacity is
available. The responder MUST NOT respond with an error or close the stream when
rate limiting.

When rate limiting, the responder MUST send each `response_chunk` in full
promptly but may introduce delays between each chunk.

Chunks start with a **single-byte** response code which determines the contents
of the `response_chunk` (`result` particle in the BNF grammar above). For
multiple chunks, only the last chunk is allowed to have a non-zero error code
(i.e. The chunk stream is terminated once an error occurs).

The response code can have one of the following values, encoded as a single
unsigned byte:

- 0: **Success** -- a normal response follows, with contents matching the
  expected message schema and encoding specified in the request.
- 1: **InvalidRequest** -- the contents of the request are semantically invalid,
  or the payload is malformed, or could not be understood. The response payload
  adheres to the `ErrorMessage` schema (described below).
- 2: **ServerError** -- the responder encountered an error while processing the
  request. The response payload adheres to the `ErrorMessage` schema (described
  below).
- 3: **ResourceUnavailable** -- the responder does not have requested resource.
  The response payload adheres to the `ErrorMessage` schema (described below).
  *Note*: This response code is only valid as a response where specified.

Clients MAY use response codes above `128` to indicate alternative, erroneous
request-specific responses.

The range `[4, 127]` is RESERVED for future usages, and should be treated as
error if not recognized expressly.

The `ErrorMessage` schema is:

```
(
  error_message: List[byte, 256]
)
```

*Note*: By convention, the `error_message` is a sequence of bytes that MAY be
interpreted as a UTF-8 string (for debugging purposes). Clients MUST treat as
valid any byte sequences.

The responder MAY penalise peers that concurrently open more than
`MAX_CONCURRENT_REQUESTS` streams for the same request type, for the protocol
IDs defined in this specification.

#### Encoding strategies

The token of the negotiated protocol ID specifies the type of encoding to be
used for the req/resp interaction. Only one value is possible at this time:

- `ssz_snappy`: The contents are first
  [SSZ-encoded](../../ssz/simple-serialize.md) and then compressed with
  [Snappy](https://github.com/google/snappy) frames compression. For objects
  containing a single field, only the field is SSZ-encoded not a container with
  a single field. For example, the `BeaconBlocksByRoot` request is an
  SSZ-encoded list of `Root`'s. This encoding type MUST be supported by all
  clients.

##### SSZ-snappy encoding strategy

The [SimpleSerialize (SSZ) specification](../../ssz/simple-serialize.md)
outlines how objects are SSZ-encoded.

To achieve snappy encoding on top of SSZ, we feed the serialized form of the
object to the Snappy compressor on encoding. The inverse happens on decoding.

Snappy has two formats: "block" and "frames" (streaming). To support large
requests and response chunks, snappy-framing is used.

Since snappy frame contents
[have a maximum size of `65536` bytes](https://github.com/google/snappy/blob/master/framing_format.txt#L104)
and frame headers are just `identifier (1) + checksum (4)` bytes, the expected
buffering of a single frame is acceptable.

**Encoding-dependent header:** Req/Resp protocols using the `ssz_snappy`
encoding strategy MUST encode the length of the raw SSZ bytes, encoded as an
unsigned
[protobuf varint](https://developers.google.com/protocol-buffers/docs/encoding#varints).

*Writing*: By first computing and writing the SSZ byte length, the SSZ encoder
can then directly write the chunk contents to the stream. When Snappy is
applied, it can be passed through a buffered Snappy writer to compress frame by
frame.

*Reading*: After reading the expected SSZ byte length, the SSZ decoder can
directly read the contents from the stream. When snappy is applied, it can be
passed through a buffered Snappy reader to decompress frame by frame.

Before reading the payload, the header MUST be validated:

- The length-prefix MUST be encoded as an unsigned protobuf varint. It SHOULD be
  minimally encoded (i.e., without any redundant bytes) and MUST not exceed 10
  bytes in length, which is sufficient to represent any `uint64` value. The
  length-prefix MUST be decoded into a type which supports the full range of
  `uint64` values.
- The length-prefix is within the expected
  [size bounds derived from the payload SSZ type](#what-are-ssz-type-size-bounds)
  or `MAX_PAYLOAD_SIZE`, whichever is smaller.

After reading a valid header, the payload MAY be read, while maintaining the
size constraints from the header.

A reader MUST NOT read more than `max_compressed_len(n)` bytes after reading the
SSZ length-prefix `n` from the header.

A reader MUST consider the following cases as invalid input:

- Any remaining bytes, after having read the `n` SSZ bytes. An EOF is expected
  if more bytes are read than required.
- An early EOF, before fully reading the declared length-prefix worth of SSZ
  bytes.

In case of an invalid input (header or payload), a reader MUST:

- From requests: send back an error message, response code `InvalidRequest`. The
  request itself is ignored.
- From responses: ignore the response, the response MUST be considered bad
  server behavior.

All messages that contain only a single field MUST be encoded directly as the
type of that field and MUST NOT be encoded as an SSZ container.

Responses that are SSZ-lists (for example `List[SignedBeaconBlock, ...]`) send
their constituents individually as `response_chunk`s. For example, the
`List[SignedBeaconBlock, ...]` response type sends zero or more
`response_chunk`s. Each _successful_ `response_chunk` contains a single
`SignedBeaconBlock` payload.

#### Messages

##### Status v1

**Protocol ID:** `/eth2/beacon_chain/req/status/1/`

Request, Response Content:

```
(
  fork_digest: ForkDigest
  finalized_root: Root
  finalized_epoch: Epoch
  head_root: Root
  head_slot: Slot
)
```

As seen by the client at the time of sending the message:

- `fork_digest`: The node's `ForkDigest`
  (`compute_fork_digest(genesis_validators_root, epoch)`) where
  - `genesis_validators_root` is the static `Root` found in
    `state.genesis_validators_root`
  - `epoch` is the node's current epoch defined by the wall-clock time (not
    necessarily the epoch to which the node is sync).
- `finalized_root`: `store.finalized_checkpoint.root` according to
  [fork choice](./fork-choice.md). (Note this defaults to `Root(b'\x00' * 32)`
  for the genesis finalized checkpoint).
- `finalized_epoch`: `store.finalized_checkpoint.epoch` according to
  [fork choice](./fork-choice.md).
- `head_root`: The `hash_tree_root` root of the current head block
  (`BeaconBlock`).
- `head_slot`: The slot of the block corresponding to the `head_root`.

The dialing client MUST send a `Status` request upon connection.

The request/response MUST be encoded as an SSZ-container.

The response MUST consist of a single `response_chunk`.

Clients SHOULD immediately disconnect from one another following the handshake
above under the following conditions:

1. If `fork_digest` does not match the node's local `fork_digest`, since the
   client’s chain is on another fork.
2. If the (`finalized_root`, `finalized_epoch`) shared by the peer is not in the
   client's chain at the expected epoch. For example, if Peer 1 sends (root,
   epoch) of (A, 5) and Peer 2 sends (B, 3) but Peer 1 has root C at epoch 3,
   then Peer 1 would disconnect because it knows that their chains are
   irreparably disjoint.

Once the handshake completes, the client with the lower `finalized_epoch` or
`head_slot` (if the clients have equal `finalized_epoch`s) SHOULD request beacon
blocks from its counterparty via the `BeaconBlocksByRange` request.

*Note*: Under abnormal network condition or after some rounds of
`BeaconBlocksByRange` requests, the client might need to send `Status` request
again to learn if the peer has a higher head. Implementers are free to implement
such behavior in their own way.

##### Goodbye v1

**Protocol ID:** `/eth2/beacon_chain/req/goodbye/1/`

Request, Response Content:

```
(
  uint64
)
```

Client MAY send goodbye messages upon disconnection. The reason field MAY be one
of the following values:

- 1: Client shut down.
- 2: Irrelevant network.
- 3: Fault/error.

Clients MAY use reason codes above `128` to indicate alternative, erroneous
request-specific responses.

The range `[4, 127]` is RESERVED for future usage.

The request/response MUST be encoded as a single SSZ-field.

The response MUST consist of a single `response_chunk`.

##### BeaconBlocksByRange v1

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/1/`

Request Content:

```
(
  start_slot: Slot
  count: uint64
  step: uint64 # Deprecated, must be set to 1
)
```

Response Content:

```
(
  List[SignedBeaconBlock, MAX_REQUEST_BLOCKS]
)
```

Requests beacon blocks in the slot range `[start_slot, start_slot + count)`,
leading up to the current head block as selected by fork choice. For example,
requesting blocks starting at `start_slot=2` and `count=4` would return the
blocks at slots `[2, 3, 4, 5]`. In cases where a slot is empty for a given slot
number, no block is returned. For example, if slot 4 were empty in the previous
example, the returned array would contain `[2, 3, 5]`.

`step` is deprecated and must be set to 1. Clients may respond with a single
block if a larger step is returned during the deprecation transition period.

`/eth2/beacon_chain/req/beacon_blocks_by_range/1/` is deprecated. Clients MAY
respond with an empty list during the deprecation transition period.

`BeaconBlocksByRange` is primarily used to sync historical blocks.

The request MUST be encoded as an SSZ-container.

The response MUST consist of zero or more `response_chunk`. Each _successful_
`response_chunk` MUST contain a single `SignedBeaconBlock` payload.

Clients MUST keep a record of signed blocks seen on the epoch range
`[max(GENESIS_EPOCH, current_epoch - MIN_EPOCHS_FOR_BLOCK_REQUESTS), current_epoch]`
where `current_epoch` is defined by the current wall-clock time, and clients
MUST support serving requests of blocks on this range.

Peers that are unable to reply to block requests within the
`MIN_EPOCHS_FOR_BLOCK_REQUESTS` epoch range SHOULD respond with error code
`3: ResourceUnavailable`. Such peers that are unable to successfully reply to
this range of requests MAY get descored or disconnected at any time.

*Note*: The above requirement implies that nodes that start from a recent weak
subjectivity checkpoint MUST backfill the local block database to at least epoch
`current_epoch - MIN_EPOCHS_FOR_BLOCK_REQUESTS` to be fully compliant with
`BlocksByRange` requests. To safely perform such a backfill of blocks to the
recent state, the node MUST validate both (1) the proposer signatures and (2)
that the blocks form a valid chain up to the most recent block referenced in the
weak subjectivity state.

*Note*: Although clients that bootstrap from a weak subjectivity checkpoint can
begin participating in the networking immediately, other peers MAY disconnect
and/or temporarily ban such an un-synced or semi-synced client.

Clients MUST respond with at least the first block that exists in the range, if
they have it, and no more than `MAX_REQUEST_BLOCKS` blocks.

The following blocks, where they exist, MUST be sent in consecutive order.

Clients MAY limit the number of blocks in the response.

The response MUST contain no more than `count` blocks.

Clients MUST respond with blocks from their view of the current fork choice --
that is, blocks from the single chain defined by the current head. Of note,
blocks from slots before the finalization MUST lead to the finalized block
reported in the `Status` handshake.

Clients MUST respond with blocks that are consistent from a single chain within
the context of the request. This applies to any `step` value. In particular when
`step == 1`, each `parent_root` MUST match the `hash_tree_root` of the preceding
block.

After the initial block, clients MAY stop in the process of responding if their
fork choice changes the view of the chain in the context of the request.

##### BeaconBlocksByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/1/`

Request Content:

```
(
  List[Root, MAX_REQUEST_BLOCKS]
)
```

Response Content:

```
(
  List[SignedBeaconBlock, MAX_REQUEST_BLOCKS]
)
```

Requests blocks by block root (= `hash_tree_root(SignedBeaconBlock.message)`).
The response is a list of `SignedBeaconBlock` whose length is less than or equal
to the number of requested blocks. It may be less in the case that the
responding peer is missing blocks.

No more than `MAX_REQUEST_BLOCKS` may be requested at a time.

`BeaconBlocksByRoot` is primarily used to recover recent blocks (e.g. when
receiving a block or attestation whose parent is unknown).

The request MUST be encoded as an SSZ-field.

The response MUST consist of zero or more `response_chunk`. Each _successful_
`response_chunk` MUST contain a single `SignedBeaconBlock` payload.

Clients MUST support requesting blocks since the latest finalized epoch.

Clients MUST respond with at least one block, if they have it. Clients MAY limit
the number of blocks in the response.

Clients MAY include a block in the response as soon as it passes the gossip
validation rules. Clients SHOULD NOT respond with blocks that fail the beacon
chain state transition.

`/eth2/beacon_chain/req/beacon_blocks_by_root/1/` is deprecated. Clients MAY
respond with an empty list during the deprecation transition period.

##### Ping v1

**Protocol ID:** `/eth2/beacon_chain/req/ping/1/`

Request Content:

```
(
  uint64
)
```

Response Content:

```
(
  uint64
)
```

Sent intermittently, the `Ping` protocol checks liveness of connected peers.
Peers request and respond with their local metadata sequence number
(`MetaData.seq_number`).

If the peer does not respond to the `Ping` request, the client MAY disconnect
from the peer.

A client can then determine if their local record of a peer's MetaData is up to
date and MAY request an updated version via the `MetaData` RPC method if not.

The request MUST be encoded as an SSZ-field.

The response MUST consist of a single `response_chunk`.

##### GetMetaData v1

**Protocol ID:** `/eth2/beacon_chain/req/metadata/1/`

No Request Content.

Response Content:

```
(
  MetaData
)
```

Requests the MetaData of a peer. The request opens and negotiates the stream
without sending any request content. Once established the receiving peer
responds with it's local most up-to-date MetaData.

The response MUST be encoded as an SSZ-container.

The response MUST consist of a single `response_chunk`.

### The discovery domain: discv5

Discovery Version 5
([discv5](https://github.com/ethereum/devp2p/blob/master/discv5/discv5.md))
(Protocol version v5.1) is used for peer discovery.

`discv5` is a standalone protocol, running on UDP on a dedicated port, meant for
peer discovery only. `discv5` supports self-certified, flexible peer records
(ENRs) and topic-based advertisement, both of which are (or will be)
requirements in this context.

#### Integration into libp2p stacks

`discv5` SHOULD be integrated into the client’s libp2p stack by implementing an
adaptor to make it conform to the
[service discovery](https://github.com/libp2p/go-libp2p-core/blob/master/discovery/discovery.go)
and
[peer routing](https://github.com/libp2p/go-libp2p-core/blob/master/routing/routing.go#L36-L44)
abstractions and interfaces (go-libp2p links provided).

Inputs to operations include peer IDs (when locating a specific peer) or
capabilities (when searching for peers with a specific capability), and the
outputs will be multiaddrs converted from the ENR records returned by the discv5
backend.

This integration enables the libp2p stack to subsequently form connections and
streams with discovered peers.

#### ENR structure

The Ethereum Node Record (ENR) for an Ethereum consensus client MUST contain the
following entries (exclusive of the sequence number and signature, which MUST be
present in an ENR):

- The compressed secp256k1 publickey, 33 bytes (`secp256k1` field).

The ENR MAY contain the following entries:

- An IPv4 address (`ip` field) and/or IPv6 address (`ip6` field).
- An IPv4 TCP port (`tcp` field) representing the local libp2p TCP listening
  port and/or the corresponding IPv6 port (`tcp6` field).
- An IPv4 QUIC port (`quic` field) representing the local libp2p QUIC (UDP)
  listening port and/or the corresponding IPv6 port (`quic6` field).
- An IPv4 UDP port (`udp` field) representing the local discv5 listening port
  and/or the corresponding IPv6 port (`udp6` field).

Specifications of these parameters can be found in the
[ENR Specification](http://eips.ethereum.org/EIPS/eip-778).

##### Attestation subnet bitfield

The ENR `attnets` entry signifies the attestation subnet bitfield with the
following form to more easily discover peers participating in particular
attestation gossip subnets.

| Key       | Value                                     |
| :-------- | :---------------------------------------- |
| `attnets` | SSZ `Bitvector[ATTESTATION_SUBNET_COUNT]` |

If a node's `MetaData.attnets` has any non-zero bit, the ENR MUST include the
`attnets` entry with the same value as `MetaData.attnets`.

If a node's `MetaData.attnets` is composed of all zeros, the ENR MAY optionally
include the `attnets` entry or leave it out entirely.

##### `eth2` field

ENRs MUST carry a generic `eth2` key with an 16-byte value of the node's current
fork digest, next fork version, and next fork epoch to ensure connections are
made with peers on the intended Ethereum network.

| Key    | Value           |
| :----- | :-------------- |
| `eth2` | SSZ `ENRForkID` |

Specifically, the value of the `eth2` key MUST be the following SSZ encoded
object (`ENRForkID`)

```
(
  fork_digest: ForkDigest
  next_fork_version: Version
  next_fork_epoch: Epoch
)
```

The fields of `ENRForkID` are defined as

- `fork_digest` is `compute_fork_digest(genesis_validators_root, epoch)` where:
  - `genesis_validators_root` is the static `Root` found in
    `state.genesis_validators_root`.
  - `epoch` is the node's current epoch defined by the wall-clock time (not
    necessarily the epoch to which the node is sync).
- `next_fork_version` is the fork version corresponding to the next planned hard
  fork at a future epoch. If no future fork is planned, set
  `next_fork_version = current_fork_version` to signal this fact
- `next_fork_epoch` is the epoch at which the next fork is planned and the
  `current_fork_version` will be updated. If no future fork is planned, set
  `next_fork_epoch = FAR_FUTURE_EPOCH` to signal this fact

*Note*: `fork_digest` is composed of values that are not known until the genesis
block/state are available. Due to this, clients SHOULD NOT form ENRs and begin
peer discovery until genesis values are known. One notable exception to this
rule is the distribution of bootnode ENRs prior to genesis. In this case,
bootnode ENRs SHOULD be initially distributed with `eth2` field set as
`ENRForkID(fork_digest=compute_fork_digest(b'\x00'*32, GENESIS_EPOCH), next_fork_version=GENESIS_FORK_VERSION, next_fork_epoch=FAR_FUTURE_EPOCH)`.
After genesis values are known, the bootnodes SHOULD update ENRs to participate
in normal discovery operations.

Clients SHOULD connect to peers with `fork_digest`, `next_fork_version`, and
`next_fork_epoch` that match local values.

Clients MAY connect to peers with the same `fork_digest` but a different
`next_fork_version`/`next_fork_epoch`. Unless `ENRForkID` is manually updated to
matching prior to the earlier `next_fork_epoch` of the two clients, these
connecting clients will be unable to successfully interact starting at the
earlier `next_fork_epoch`.

### Attestation subnet subscription

Because Phase 0 does not have shards and thus does not have Shard Committees,
there is no stable backbone to the attestation subnets
(`beacon_attestation_{subnet_id}`). To provide this stability, each beacon node
should:

- Remain subscribed to `SUBNETS_PER_NODE` for `EPOCHS_PER_SUBNET_SUBSCRIPTION`
  epochs.
- Maintain advertisement of the selected subnets in their node's ENR `attnets`
  entry by setting the selected `subnet_id` bits to `True` (e.g.
  `ENR["attnets"][subnet_id] = True`) for all persistent attestation subnets.
- Select these subnets based on their node-id as specified by the following
  `compute_subscribed_subnets(node_id, epoch)` function.

```python
def compute_subscribed_subnet(node_id: NodeID, epoch: Epoch, index: int) -> SubnetID:
    node_id_prefix = node_id >> (NODE_ID_BITS - ATTESTATION_SUBNET_PREFIX_BITS)
    node_offset = node_id % EPOCHS_PER_SUBNET_SUBSCRIPTION
    permutation_seed = hash(
        uint_to_bytes(uint64((epoch + node_offset) // EPOCHS_PER_SUBNET_SUBSCRIPTION))
    )
    permutated_prefix = compute_shuffled_index(
        node_id_prefix,
        1 << ATTESTATION_SUBNET_PREFIX_BITS,
        permutation_seed,
    )
    return SubnetID((permutated_prefix + index) % ATTESTATION_SUBNET_COUNT)
```

```python
def compute_subscribed_subnets(node_id: NodeID, epoch: Epoch) -> Sequence[SubnetID]:
    return [compute_subscribed_subnet(node_id, epoch, index) for index in range(SUBNETS_PER_NODE)]
```

*Note*: When preparing for a hard fork, a node must select and subscribe to
subnets of the future fork versioning at least `EPOCHS_PER_SUBNET_SUBSCRIPTION`
epochs in advance of the fork. These new subnets for the fork are maintained in
addition to those for the current fork until the fork occurs. After the fork
occurs, let the subnets from the previous fork reach the end of life with no
replacements.

## Design decision rationale

### Transport

#### Why are we defining specific transports?

libp2p peers can listen on multiple transports concurrently, and these can
change over time. Multiaddrs encode not only the address but also the transport
to be used to dial.

Due to this dynamic nature, agreeing on specific transports like TCP, QUIC, or
WebSockets on paper becomes irrelevant.

However, it is useful to define a minimum baseline for interoperability
purposes.

#### Can clients support other transports/handshakes than the ones mandated by the spec?

Clients may support other transports such as libp2p QUIC, WebSockets, and WebRTC
transports, if available in the language of choice. While interoperability shall
not be harmed by lack of such support, the advantages are desirable:

- Better latency, performance, and other QoS characteristics (QUIC).
- Paving the way for interfacing with future light clients (WebSockets, WebRTC).

The libp2p QUIC transport inherently relies on TLS 1.3 per requirement in
section 7 of the
[QUIC protocol specification](https://tools.ietf.org/html/draft-ietf-quic-transport-22#section-7)
and the accompanying
[QUIC-TLS document](https://tools.ietf.org/html/draft-ietf-quic-tls-22).

The usage of one handshake procedure or the other shall be transparent to the
application layer, once the libp2p Host/Node object has been configured
appropriately.

#### What are the advantages of using TCP/QUIC/Websockets?

TCP is a reliable, ordered, full-duplex, congestion-controlled network protocol
that powers much of the Internet as we know it today. HTTP/1.1 and HTTP/2 run
atop TCP.

QUIC is a new protocol that’s in the final stages of specification by the IETF
QUIC WG. It emerged from Google’s SPDY experiment. The QUIC transport is
undoubtedly promising. It’s UDP-based yet reliable, ordered, multiplexed,
natively secure (TLS 1.3), reduces latency vs. TCP, and offers stream-level and
connection-level congestion control (thus removing head-of-line blocking), 0-RTT
connection establishment, and endpoint migration, amongst other features. UDP
also has better NAT traversal properties than TCP—something we desperately
pursue in peer-to-peer networks.

QUIC is being adopted as the underlying protocol for HTTP/3. This has the
potential to award us censorship resistance via deep packet inspection for free.
Provided that we use the same port numbers and encryption mechanisms as HTTP/3,
our traffic may be indistinguishable from standard web traffic, and we may only
become subject to standard IP-based firewall filtering—something we can
counteract via other mechanisms.

WebSockets and/or WebRTC transports are necessary for interaction with browsers,
and will become increasingly important as we incorporate browser-based light
clients to the Ethereum network.

#### Why do we not just support a single transport?

Networks evolve. Hardcoding design decisions leads to ossification, preventing
the evolution of networks alongside the state of the art. Introducing changes on
an ossified protocol is very costly, and sometimes, downright impracticable
without causing undesirable breakage.

Modeling for upgradeability and dynamic transport selection from the get-go lays
the foundation for a future-proof stack.

Clients can adopt new transports without breaking old ones, and the
multi-transport ability enables constrained and sandboxed environments (e.g.
browsers, embedded devices) to interact with the network as first-class citizens
via suitable/native transports (e.g. WSS), without the need for proxying or
trust delegation to servers.

#### Why are we not using QUIC from the start?

The QUIC standard is still not finalized (at working draft 22 at the time of
writing), and not all mainstream runtimes/languages have mature, standard,
and/or fully-interoperable
[QUIC support](https://github.com/quicwg/base-drafts/wiki/Implementations). One
remarkable example is node.js, where the QUIC implementation is
[in early development](https://github.com/nodejs/quic).

*Note*:
[TLS 1.3 is a prerequisite of the QUIC transport](https://tools.ietf.org/html/draft-ietf-quic-transport-22#section-7),
although an experiment exists to integrate Noise as the QUIC crypto layer:
[nQUIC](https://eprint.iacr.org/2019/028).

On the other hand, TLS 1.3 is the newest, simplified iteration of TLS. Old,
insecure, obsolete ciphers and algorithms have been removed, adopting Ed25519 as
the sole ECDH key agreement function. Handshakes are faster, 1-RTT data is
supported, and session resumption is a reality, amongst other features.

### Multiplexing

#### Why are we using mplex/yamux?

[Yamux](https://github.com/hashicorp/yamux/blob/master/spec.md) is a multiplexer
invented by Hashicorp that supports stream-level congestion control.
Implementations exist in a limited set of languages, and it’s not a trivial
piece to develop.

Conscious of that, the libp2p community conceptualized
[mplex](https://github.com/libp2p/specs/blob/master/mplex/README.md) as a
simple, minimal multiplexer for usage with libp2p. It does not support
stream-level congestion control and is subject to head-of-line blocking.

Overlay multiplexers are not necessary with QUIC since the protocol provides
native multiplexing, but they need to be layered atop TCP, WebSockets, and other
transports that lack such support.

### Protocol negotiation

#### When is multiselect 2.0 due and why do we plan to migrate to it?

multiselect 2.0 is currently being conceptualized. The debate started
[on this issue](https://github.com/libp2p/specs/pull/95), but it got
overloaded—as it tends to happen with large conceptual OSS discussions that
touch the heart and core of a system.

At some point in 2020, we expect a renewed initiative to first define the
requirements, constraints, assumptions, and features, in order to lock in basic
consensus upfront and subsequently build on that consensus by submitting a
specification for implementation.

We plan to eventually migrate to multiselect 2.0 because it will:

1. Reduce round trips during connection bootstrapping and stream protocol
   negotiation.
2. Enable efficient one-stream-per-request interaction patterns.
3. Leverage *push data* mechanisms of underlying protocols to expedite
   negotiation.
4. Provide the building blocks for enhanced censorship resistance.

#### What is the difference between connection-level and stream-level protocol negotiation?

All libp2p connections must be authenticated, encrypted, and multiplexed.
Connections using network transports unsupportive of native
authentication/encryption and multiplexing (e.g. TCP) need to undergo protocol
negotiation to agree on a mutually supported:

1. authentication/encryption mechanism (such as SecIO, TLS 1.3, Noise).
2. overlay multiplexer (such as mplex, Yamux, spdystream).

In this specification, we refer to these two as *connection-level negotiations*.
Transports supporting those features natively (such as QUIC) omit those
negotiations.

After successfully selecting a multiplexer, all subsequent I/O happens over
*streams*. When opening streams, peers pin a protocol to that stream, by
conducting *stream-level protocol negotiation*.

At present, multistream-select 1.0 is used for both types of negotiation, but
multiselect 2.0 will use dedicated mechanisms for connection bootstrapping
process and stream protocol negotiation.

### Encryption

#### Why are we not supporting SecIO?

SecIO has been the default encryption layer for libp2p for years. It is used in
IPFS and Filecoin. And although it will be superseded shortly, it is proven to
work at scale.

Although SecIO has wide language support, we won’t be using it for mainnet
because, amongst other things, it requires several round trips to be sound, and
doesn’t support early data (0-RTT data), a mechanism that multiselect 2.0 will
leverage to reduce round trips during connection bootstrapping.

SecIO is not considered secure for the purposes of this spec.

#### Why are we using Noise?

Copied from the Noise Protocol Framework
[website](http://www.noiseprotocol.org):

> Noise is a framework for building crypto protocols. Noise protocols support
> mutual and optional authentication, identity hiding, forward secrecy, zero
> round-trip encryption, and other advanced features.

Noise in itself does not specify a single handshake procedure, but provides a
framework to build secure handshakes based on Diffie-Hellman key agreement with
a variety of tradeoffs and guarantees.

Noise handshakes are lightweight and simple to understand, and are used in major
cryptographic-centric projects like WireGuard, I2P, and Lightning.
[Various](https://www.wireguard.com/papers/kobeissi-bhargavan-noise-explorer-2018.pdf)
[studies](https://eprint.iacr.org/2019/436.pdf) have assessed the stated
security goals of several Noise handshakes with positive results.

#### Why are we using encryption at all?

Transport level encryption secures message exchange and provides properties that
are useful for privacy, safety, and censorship resistance. These properties are
derived from the following security guarantees that apply to the entire
communication between two peers:

- Peer authentication: the peer I’m talking to is really who they claim to be
  and who I expect them to be.
- Confidentiality: no observer can eavesdrop on the content of our messages.
- Integrity: the data has not been tampered with by a third-party while in
  transit.
- Non-repudiation: the originating peer cannot dispute that they sent the
  message.
- Depending on the chosen algorithms and mechanisms (e.g. continuous HMAC), we
  may obtain additional guarantees, such as non-replayability (this byte
  could’ve only been sent *now;* e.g. by using continuous HMACs), or perfect
  forward secrecy (in the case that a peer key is compromised, the content of a
  past conversation will not be compromised).

Note that transport-level encryption is not exclusive of application-level
encryption or cryptography. Transport-level encryption secures the communication
itself, while application-level cryptography is necessary for the application’s
use cases (e.g. signatures, randomness, etc.).

### Gossipsub

#### Why are we using a pub/sub algorithm for block and attestation propagation?

Pubsub is a technique to broadcast/disseminate data across a network rapidly.
Such data is packaged in fire-and-forget messages that do not require a response
from every recipient. Peers subscribed to a topic participate in the propagation
of messages in that topic.

The alternative is to maintain a fully connected mesh (all peers connected to
each other 1:1), which scales poorly (O(n^2)).

#### Why are we using topics to segregate encodings, yet only support one encoding?

For future extensibility with almost zero overhead now (besides the extra bytes
in the topic name).

#### How do we upgrade gossip channels (e.g. changes in encoding, compression)?

Changing gossipsub/broadcasts requires a coordinated upgrade where all clients
start publishing to the new topic together, during a hard fork.

When a node is preparing for upcoming tasks (e.g. validator duty lookahead) on a
gossipsub topic, the node should join the topic of the future epoch in which the
task is to occur in addition to listening to the topics for the current epoch.

#### Why must all clients use the same gossip topic instead of one negotiated between each peer pair?

Supporting multiple topics/encodings would require the presence of relayers to
translate between encodings and topics so as to avoid network fragmentation
where participants have diverging views on the gossiped state, making the
protocol more complicated and fragile.

Gossip protocols typically remember what messages they've seen for a finite
period of time-based on message identity -- if you publish the same message
again after that time has passed, it will be re-broadcast—adding a relay delay
also makes this scenario more likely.

One can imagine that in a complicated upgrade scenario, we might have peers
publishing the same message on two topics/encodings, but the price here is
pretty high in terms of overhead -- both computational and networking -- so we'd
rather avoid that.

It is permitted for clients to publish data on alternative topics as long as
they also publish on the network-wide mandatory topic.

#### Why are the topics strings and not hashes?

Topic names have a hierarchical structure. In the future, gossipsub may support
wildcard subscriptions (e.g. subscribe to all children topics under a root
prefix) by way of prefix matching. Enforcing hashes for topic names would
preclude us from leveraging such features going forward.

No security or privacy guarantees are lost as a result of choosing plaintext
topic names, since the domain is finite anyway, and calculating a digest's
preimage would be trivial.

Furthermore, the topic names are shorter than their digest equivalents (assuming
SHA-256 hash), so hashing topics would bloat messages unnecessarily.

#### Why are we using the `StrictNoSign` signature policy?

The policy omits the `from` (1), `seqno` (3), `signature` (5) and `key` (6)
fields. These fields would:

- Expose origin of sender (`from`), type of sender (based on `seqno`)
- Add extra unused data to the gossip, since message IDs are based on `data`,
  not on the `from` and `seqno`.
- Introduce more message validation than necessary, e.g. no `signature`.

#### Why are we overriding the default libp2p pubsub `message-id`?

For our current purposes, there is no need to address messages based on source
peer, or track a message `seqno`. By overriding the default `message-id` to use
content-addressing we can filter unnecessary duplicates before hitting the
application layer.

Some examples of where messages could be duplicated:

- A validator client connected to multiple beacon nodes publishing duplicate
  gossip messages
- Attestation aggregation strategies where clients partially aggregate
  attestations and propagate them. Partial aggregates could be duplicated
- Clients re-publishing seen messages

#### Why are these specific gossip parameters chosen?

- `D`, `D_low`, `D_high`, `D_lazy`: recommended defaults.
- `heartbeat_interval`: 0.7 seconds, recommended for the beacon chain in the
  [GossipSub evaluation report by Protocol Labs](https://gateway.ipfs.io/ipfs/QmRAFP5DBnvNjdYSbWhEhVRJJDFCLpPyvew5GwCCB4VxM4).
- `fanout_ttl`: 60 seconds, recommended default. Fanout is primarily used by
  committees publishing attestations to subnets. This happens once per epoch per
  validator and the subnet changes each epoch so there is little to gain in
  having a `fanout_ttl` be increased from the recommended default.
- `mcache_len`: 6, increase by one to ensure that mcache is around for long
  enough for `IWANT`s to respond to `IHAVE`s in the context of the shorter
  `heartbeat_interval`. If `mcache_gossip` is increased, this param should be
  increased to be at least `3` (~2 seconds) more than `mcache_gossip`.
- `mcache_gossip`: 3, recommended default. This can be increased to 5 or 6 (~4
  seconds) if gossip times are longer than expected and the current window does
  not provide enough responsiveness during adverse conditions.
- `seen_ttl`:
  `SLOTS_PER_EPOCH * SECONDS_PER_SLOT / heartbeat_interval = approx. 550`.
  Attestation gossip validity is bounded by an epoch, so this is the safe max
  bound.

#### Why is there `MAXIMUM_GOSSIP_CLOCK_DISPARITY` when validating slot ranges of messages in gossip subnets?

For some gossip channels (e.g. those for Attestations and BeaconBlocks), there
are designated ranges of slots during which particular messages can be sent,
limiting messages gossiped to those that can be reasonably used in the consensus
at the current time/slot. This is to reduce optionality in DoS attacks.

`MAXIMUM_GOSSIP_CLOCK_DISPARITY` provides some leeway in validating slot ranges
to prevent the gossip network from becoming overly brittle with respect to clock
disparity. For minimum and maximum allowable slot broadcast times,
`MAXIMUM_GOSSIP_CLOCK_DISPARITY` MUST be subtracted and added respectively,
marginally extending the valid range. Although messages can at times be eagerly
gossiped to the network, the node's fork choice prevents integration of these
messages into the actual consensus until the _actual local start_ of the
designated slot.

#### Why are there `ATTESTATION_SUBNET_COUNT` attestation subnets?

Depending on the number of validators, it may be more efficient to group shard
subnets and might provide better stability for the gossipsub channel. The exact
grouping will be dependent on more involved network tests. This constant allows
for more flexibility in setting up the network topology for attestation
aggregation (as aggregation should happen on each subnet). The value is
currently set to be equal to `MAX_COMMITTEES_PER_SLOT` if/until network tests
indicate otherwise.

#### Why are attestations limited to be broadcast on gossip channels within `SLOTS_PER_EPOCH` slots?

Attestations can only be included on chain within an epoch's worth of slots so
this is the natural cutoff. There is no utility to the chain to broadcast
attestations older than one epoch, and because validators have a chance to make
a new attestation each epoch, there is minimal utility to the fork choice to
relay old attestations as a new latest message can soon be created by each
validator.

In addition to this, relaying attestations requires validating the attestation
in the context of the `state` during which it was created. Thus, validating
arbitrarily old attestations would put additional requirements on which states
need to be readily available to the node. This would result in a higher resource
burden and could serve as a DoS vector.

#### Why are aggregate attestations broadcast to the global topic as `AggregateAndProof`s rather than just as `Attestation`s?

The dominant strategy for an individual validator is to always broadcast an
aggregate containing their own attestation to the global channel to ensure that
proposers see their attestation for inclusion. Using a private selection
criteria and providing this proof of selection alongside the gossiped aggregate
ensures that this dominant strategy will not flood the global channel.

Also, an attacker can create any number of honest-looking aggregates and
broadcast them to the global pubsub channel. Thus without some sort of proof of
selection as an aggregator, the global channel can trivially be spammed.

#### Why are we sending entire objects in the pubsub and not just hashes?

Entire objects should be sent to get the greatest propagation speeds. If only
hashes are sent, then block and attestation propagation is dependent on
recursive requests from each peer. In a hash-only scenario, peers could receive
hashes without knowing who to download the actual contents from. Sending entire
objects ensures that they get propagated through the entire network.

#### Should clients gossip blocks if they *cannot* validate the proposer signature due to not yet being synced, not knowing the head block, etc?

The prohibition of unverified-block-gossiping extends to nodes that cannot
verify a signature due to not being fully synced to ensure that such (amplified)
DOS attacks are not possible.

#### How are we going to discover peers in a gossipsub topic?

In Phase 0, peers for attestation subnets will be found using the `attnets`
entry in the ENR.

Although this method will be sufficient for early upgrade of the beacon chain,
we aim to use the more appropriate discv5 topics for this and other similar
tasks in the future. ENRs should ultimately not be used for this purpose. They
are best suited to store identity, location, and capability information, rather
than more volatile advertisements.

#### How should fork version be used in practice?

Fork versions are to be manually updated (likely via incrementing) at each hard
fork. This is to provide native domain separation for signatures as well as to
aid in usefulness for identifying peers (via ENRs) and versioning network
protocols (e.g. using fork version to naturally version gossipsub topics).

`BeaconState.genesis_validators_root` is mixed into signature and ENR fork
domains (`ForkDigest`) to aid in the ease of domain separation between chains.
This allows fork versions to safely be reused across chains except for the case
of contentious forks using the same genesis. In these cases, extra care should
be taken to isolate fork versions (e.g. flip a high order bit in all future
versions of one of the chains).

A node locally stores all previous and future planned fork versions along with
the each fork epoch. This allows for handling sync and processing messages
starting from past forks/epochs.

### Req/Resp

#### Why segregate requests into dedicated protocol IDs?

Requests are segregated by protocol ID to:

1. Leverage protocol routing in libp2p, such that the libp2p stack will route
   the incoming stream to the appropriate handler. This allows the handler
   function for each request type to be self-contained. For an analogy, think
   about how you attach HTTP handlers to a REST API server.
2. Version requests independently. In a coarser-grained umbrella protocol, the
   entire protocol would have to be versioned even if just one field in a single
   message changed.
3. Enable clients to select the individual requests/versions they support. It
   would no longer be a strict requirement to support all requests, and clients,
   in principle, could support a subset of requests and variety of versions.
4. Enable flexibility and agility for clients adopting spec changes that impact
   the request, by signalling to peers exactly which subset of new/old requests
   they support.
5. Enable clients to explicitly choose backwards compatibility at the request
   granularity. Without this, clients would be forced to support entire versions
   of the coarser request protocol.
6. Parallelise RFCs (or EIPs). By decoupling requests from one another, each RFC
   that affects the request protocol can be deployed/tested/debated
   independently without relying on a synchronization point to version the
   general top-level protocol.
   1. This has the benefit that clients can explicitly choose which RFCs to
      deploy without buying into all other RFCs that may be included in that
      top-level version.
   2. Affording this level of granularity with a top-level protocol would imply
      creating as many variants (e.g. /protocol/43-{a,b,c,d,...}) as the
      cartesian product of RFCs in-flight, O(n^2).
7. Allow us to simplify the payload of requests. Request-id’s and method-ids no
   longer need to be sent. The encoding/request type and version can all be
   handled by the framework.

**Caveat**: The protocol negotiation component in the current version of libp2p
is called multistream-select 1.0. It is somewhat naïve and introduces overhead
on every request when negotiating streams, although implementation-specific
optimizations are possible to save this cost. Multiselect 2.0 will eventually
remove this overhead by memoizing previously selected protocols, and modeling
shared protocol tables. Fortunately, this req/resp protocol is not the expected
network bottleneck in the protocol so the additional overhead is not expected to
significantly hinder this domain.

#### Why are messages length-prefixed with a protobuf varint in the SSZ-encoding?

We are using single-use streams where each stream is closed at the end of the
message. Thus, libp2p transparently handles message delimiting in the underlying
stream. libp2p streams are full-duplex, and each party is responsible for
closing their write side (like in TCP). We can therefore use stream closure to
mark the end of the request and response independently.

Nevertheless, in the case of `ssz_snappy`, messages are still length-prefixed
with the length of the underlying data:

- A basic reader can prepare a correctly sized buffer before reading the message
- A more advanced reader can stream-decode SSZ given the length of the SSZ data.
- Alignment with protocols like gRPC over HTTP/2 that prefix with length
- Sanity checking of message length, and enabling much stricter message length
  limiting based on SSZ type information, to provide even more DOS protection
  than the global message length already does. E.g. a small `Status` message
  does not nearly require `MAX_PAYLOAD_SIZE` bytes.

[Protobuf varint](https://developers.google.com/protocol-buffers/docs/encoding#varints)
is an efficient technique to encode variable-length (unsigned here) ints.
Instead of reserving a fixed-size field of as many bytes as necessary to convey
the maximum possible value, this field is elastic in exchange for 1-bit overhead
per byte.

#### Why do we version protocol strings with ordinals instead of semver?

Using semver for network protocols is confusing. It is never clear what a change
in a field, even if backwards compatible on deserialization, actually implies.
Network protocol agreement should be explicit. Imagine two peers:

- Peer A supporting v1.1.1 of protocol X.
- Peer B supporting v1.1.2 of protocol X.

These two peers should never speak to each other because the results can be
unpredictable. This is an oversimplification: imagine the same problem with a
set of 10 possible versions. We now have 10^2 (100) possible outcomes that peers
need to model for. The resulting complexity is unwieldy.

For this reason, we rely on negotiation of explicit, verbatim protocols. In the
above case, peer B would provide backwards compatibility by supporting and
advertising both v1.1.1 and v1.1.2 of the protocol.

Therefore, semver would be relegated to convey expectations at the human level,
and it wouldn't do a good job there either, because it's unclear if "backwards
compatibility" and "breaking change" apply only to wire schema level, to
behavior, etc.

For this reason, we remove and replace semver with ordinals that require
explicit agreement and do not mandate a specific policy for changes.

#### Why is it called Req/Resp and not RPC?

Req/Resp is used to avoid confusion with JSON-RPC and similar user-client
interaction mechanisms.

#### What is a typical rate limiting strategy?

The responder typically will want to rate limit requests to protect against spam
and to manage resource consumption, while the requester will want to maximise
performance based on its own resource allocation strategy. For the network, it
is beneficial if available resources are used optimally.

Broadly, the requester does not know the capacity / limit of each server but can
derive it from the rate of responses for the purpose of selecting the next peer
for a request.

Because the server withholds the response until capacity is available, a client
can optimistically send requests without risking running into negative scoring
situations or sub-optimal rate polling.

A typical approach for the requester is to implement a timeout on the request
that depends on the nature of the request and on connectivity parameters in
general - for example when requesting blocks, a peer might choose to send a
request to a second peer if the first peer does not respond within a reasonable
time, and to reset the request to the first peer if the second peer responds
faster. Clients may use past response performance to reward fast peers when
implementing peer scoring.

A typical approach for the responder is to implement a two-level token/leaky
bucket with a per-peer limit and a global limit. The granularity of rate
limiting may be based either on full requests or individual chunks with the
latter being preferable. A token cost may be assigned to the request itself and
separately each chunk in the response so as to remain protected both against
large and frequent requests.

For requesters, rate limiting is not distinguishable from other conditions
causing slow responses (slow peers, congestion etc) and since the latter
conditions must be handled anyway, including rate limiting in this strategy
keeps the implementation simple.

#### Why do we allow empty responses in block requests?

When requesting blocks by range or root, it may happen that there are no blocks
in the selected range or the responding node does not have the requested blocks.

Thus, it may happen that we need to transmit an empty list - there are several
ways to encode this:

0. Close the stream without sending any data
1. Add a `null` option to the `success` response, for example by introducing an
   additional byte
2. Respond with an error result, using a specific error code for "No data"

Semantically, it is not an error that a block is missing during a slot making
option 2 unnatural.

Option 1 allows the responder to signal "no block", but this information may be
wrong - for example in the case of a malicious node.

Under option 0, there is no way for a client to distinguish between a slot
without a block and an incomplete response, but given that it already must
contain logic to handle the uncertainty of a malicious peer, option 0 was
chosen. Clients should mark any slots missing blocks as unknown until they can
be verified as not containing a block by successive blocks.

Assuming option 0 with no special `null` encoding, consider a request for slots
`2, 3, 4` -- if there was no block produced at slot 4, the response would be
`2, 3, EOF`. Now consider the same situation, but where only `4` is requested --
closing the stream with only `EOF` (without any `response_chunk`) is consistent.

Failing to provide blocks that nodes "should" have is reason to trust a peer
less -- for example, if a particular peer gossips a block, it should have access
to its parent. If a request for the parent fails, it's indicative of poor peer
quality since peers should validate blocks before gossiping them.

#### Why does `BeaconBlocksByRange` let the server choose which branch to send blocks from?

When connecting, the `Status` message gives an idea about the sync status of a
particular peer, but this changes over time. By the time a subsequent
`BeaconBlockByRange` request is processed, the information may be stale, and the
responder might have moved on to a new finalization point and pruned blocks
around the previous head and finalized blocks.

To avoid this race condition, we allow the responder to choose which branch to
send to the requester. The requester then goes on to validate the blocks and
incorporate them in their own database -- because they follow the same rules,
they should at this point arrive at the same canonical chain.

#### Why are `BlocksByRange` requests only required to be served for the latest `MIN_EPOCHS_FOR_BLOCK_REQUESTS` epochs?

Due to economic finality and weak subjectivity requirements of a proof-of-stake
blockchain, for a new node to safely join the network the node must provide a
recent checkpoint found out-of-band. This checkpoint can be in the form of a
`root` & `epoch` or it can be the entire beacon state and then a simple block
sync from there to the head. We expect the latter to be the dominant UX
strategy.

These checkpoints *in the worst case* (i.e. very large validator set and maximal
allowed safety decay) must be from the most recent
`MIN_EPOCHS_FOR_BLOCK_REQUESTS` epochs, and thus a user must be able to block
sync to the head from this starting point. Thus, this defines the epoch range
outside which nodes may prune blocks, and the epoch range that a new node
syncing from a checkpoint must backfill.

`MIN_EPOCHS_FOR_BLOCK_REQUESTS` is calculated using the arithmetic from
`compute_weak_subjectivity_period` found in the
[weak subjectivity guide](./weak-subjectivity.md). Specifically to find this max
epoch range, we use the worst case event of a very large validator size
(`>= MIN_PER_EPOCH_CHURN_LIMIT * CHURN_LIMIT_QUOTIENT`).

<!-- eth2spec: skip -->

```python
MIN_EPOCHS_FOR_BLOCK_REQUESTS = (
    MIN_VALIDATOR_WITHDRAWABILITY_DELAY + MAX_SAFETY_DECAY * CHURN_LIMIT_QUOTIENT // (2 * 100)
)
```

Where `MAX_SAFETY_DECAY = 100` and thus `MIN_EPOCHS_FOR_BLOCK_REQUESTS = 33024`
(~5 months).

#### Why must the proposer signature be checked when backfilling blocks in the database?

When backfilling blocks in a database from a know safe block/state (e.g. when
starting from a weak subjectivity state), the node not only must ensure the
`BeaconBlock`s form a chain to the known safe block, but also must check that
the proposer signature is valid in the `SignedBeaconBlock` wrapper.

This is because the signature is not part of the `BeaconBlock` hash chain, and
thus could be corrupted by an attacker serving valid `BeaconBlock`s but invalid
signatures contained in `SignedBeaconBlock`.

Although in this particular use case this does not represent a decay in safety
(due to the assumptions of starting at a weak subjectivity checkpoint), it would
represent invalid historic data and could be unwittingly transmitted to
additional nodes.

#### What's the effect of empty slots on the sync algorithm?

When syncing one can only tell that a slot has been skipped on a particular
branch by examining subsequent blocks and analyzing the graph formed by the
parent root. Because the server side may choose to omit blocks in the response
for any reason, clients must validate the graph and be prepared to fill in gaps.

For example, if a peer responds with blocks [2, 3] when asked for [2, 3, 4],
clients may not assume that block 4 doesn't exist -- it merely means that the
responding peer did not send it (they may not have it yet or may maliciously be
trying to hide it) and successive blocks will be needed to determine if there
exists a block at slot 4 in this particular branch.

### Discovery

#### Why are we using discv5 and not libp2p Kademlia DHT?

discv5 is a standalone protocol, running on UDP on a dedicated port, meant for
peer and service discovery only. discv5 supports self-certified, flexible peer
records (ENRs) and topic-based advertisement, both of which are, or will be,
requirements in this context.

On the other hand, libp2p Kademlia DHT is a fully-fledged DHT
protocol/implementations with content routing and storage capabilities, both of
which are irrelevant in this context.

Ethereum execution-layer nodes will evolve to support discv5. By sharing the
discovery network between Ethereum consensus-layer and execution-layer clients,
we benefit from the additive effect on network size that enhances resilience and
resistance against certain attacks, to which smaller networks are more
vulnerable. It should also help light clients of both networks find nodes with
specific capabilities.

discv5 is in the process of being audited.

#### What is the difference between an ENR and a multiaddr, and why are we using ENRs?

Ethereum Node Records are self-certified node records. Nodes craft and
disseminate ENRs for themselves, proving authorship via a cryptographic
signature. ENRs are sequentially indexed, enabling conflicts to be resolved.

ENRs are key-value records with string-indexed ASCII keys. They can store
arbitrary information, but EIP-778 specifies a pre-defined dictionary, including
IPv4 and IPv6 addresses, secp256k1 public keys, etc.

Comparing ENRs and multiaddrs is like comparing apples and oranges. ENRs are
self-certified containers of identity, addresses, and metadata about a node.
Multiaddrs are address strings with the peculiarity that they’re
self-describing, composable and future-proof. An ENR can contain multiaddrs, and
multiaddrs can be derived securely from the fields of an authenticated ENR.

discv5 uses ENRs and we will presumably need to:

1. Add `multiaddr` to the dictionary, so that nodes can advertise their
   multiaddr under a reserved namespace in ENRs. – and/or –
2. Define a bi-directional conversion function between multiaddrs and the
   corresponding denormalized fields in an ENR (ip, ip6, tcp, tcp6, etc.), for
   compatibility with nodes that do not support multiaddr natively (e.g.
   Ethereum execution-layer nodes).

#### Why do we not form ENRs and find peers until genesis block/state is known?

Although client software might very well be running locally prior to the
solidification of the beacon-chain genesis state and block, clients cannot form
valid ENRs prior to this point. ENRs contain `fork_digest` which utilizes the
`genesis_validators_root` for a cleaner separation between chains so prior to
knowing genesis, we cannot use `fork_digest` to cleanly find peers on our
intended chain. Once genesis data is known, we can then form ENRs and safely
find peers.

When using a proof-of-work deposit contract for deposits, `fork_digest` will be
known `GENESIS_DELAY` (7 days in mainnet configuration) before `genesis_time`,
providing ample time to find peers and form initial connections and gossip
subnets prior to genesis.

### Compression/Encoding

#### Why are we using SSZ for encoding?

SSZ is used at the consensus layer, and all implementations should have support
for SSZ-encoding/decoding, requiring no further dependencies to be added to
client implementations. This is a natural choice for serializing objects to be
sent across the wire. The actual data in most protocols will be further
compressed for efficiency.

SSZ has well-defined schemas for consensus objects (typically sent across the
wire) reducing any serialization schema data that needs to be sent. It also has
defined all required types that are required for this network specification.

#### Why are we compressing, and at which layers?

We compress on the wire to achieve smaller payloads per-message, which, in
aggregate, result in higher efficiency, better utilization of available
bandwidth, and overall reduction in network-wide traffic overhead.

At this time, libp2p does not have an out-of-the-box compression feature that
can be dynamically negotiated and layered atop connections and streams, but it
is [being considered](https://github.com/libp2p/libp2p/issues/81).

This is a non-trivial feature because the behavior of network IO loops, kernel
buffers, chunking, and packet fragmentation, amongst others, need to be taken
into account. libp2p streams are unbounded streams, whereas compression
algorithms work best on bounded byte streams of which we have some prior
knowledge.

Compression tends not to be a one-size-fits-all problem. A lot of variables need
careful evaluation, and generic approaches/choices lead to poor size shavings,
which may even be counterproductive when factoring in the CPU and memory
tradeoff.

For all these reasons, generically negotiating compression algorithms may be
treated as a research problem at the libp2p community, one we’re happy to tackle
in the medium-term.

At this stage, the wisest choice is to consider libp2p a messenger of bytes, and
to make application layer participate in compressing those bytes. This looks
different depending on the interaction layer:

- Gossip domain: since gossipsub has a framing protocol and exposes an API, we
  compress the payload (when dictated by the encoding token in the topic name)
  prior to publishing the message via the API. No length-prefixing is necessary
  because protobuf takes care of bounding the field in the serialized form.
- Req/Resp domain: since we define custom protocols that operate on byte
  streams, implementers are encouraged to encapsulate the encoding and
  compression logic behind MessageReader and MessageWriter components/strategies
  that can be layered on top of the raw byte streams.

#### Why are we using Snappy for compression?

Snappy is used in Ethereum 1.0. It is well maintained by Google, has good
benchmarks, and can calculate the size of the uncompressed object without
inflating it in memory. This prevents DOS vectors where large uncompressed data
is sent.

#### Can I get access to unencrypted bytes on the wire for debugging purposes?

Yes, you can add loggers in your libp2p protocol handlers to log incoming and
outgoing messages. It is recommended to use programming design patterns to
encapsulate the logging logic cleanly.

If your libp2p library relies on frameworks/runtimes such as Netty (jvm) or
Node.js (javascript), you can use logging facilities in those
frameworks/runtimes to enable message tracing.

For specific ad-hoc testing scenarios, you can use the
[plaintext/2.0.0 secure channel](https://github.com/libp2p/specs/blob/master/plaintext/README.md)
(which is essentially no-op encryption or message authentication), in
combination with tcpdump or Wireshark to inspect the wire.

#### What are SSZ type size bounds?

The SSZ encoding outputs of each type have size bounds: each dynamic type, such
as a list, has a "limit", which can be used to compute the maximum valid output
size. Note that for some more complex dynamic-length objects, element offsets (4
bytes each) may need to be included. Other types are static, they have a fixed
size: no dynamic-length content is involved, and the minimum and maximum bounds
are the same.

For reference, the type bounds can be computed ahead of time,
[as per this example](https://gist.github.com/protolambda/db75c7faa1e94f2464787a480e5d613e).
It is advisable to derive these lengths from the SSZ type definitions in use, to
ensure that version changes do not cause out-of-sync type bounds.

#### Why is the message size defined in terms of application payload?

When transmitting messages over gossipsub and/or the req/resp domain, we want to
ensure that the same payload sizes are supported regardless of the underlying
transport, decoupling the consensus layer from libp2p-induced overhead and the
particular transmission strategy.

To derive "encoded size limits" from desired application sizes, we take into
account snappy compression and framing overhead.

In the case of gossipsub, the protocol supports sending multiple application
payloads as well as mixing application data with control messages in each
gossipsub frame. The limit is set such that at least one max-sized
application-level message together with a small amount (1 KiB) of gossipsub
overhead is allowed. Implementations are free to pack multiple smaller
application messages into a single gossipsub frame, and/or combine it with
control messages as they see fit.

The limit is set on the uncompressed payload size in particular to protect
against decompression bombs.

#### Why is there a limit on message sizes at all?

The message size limit protects against several forms of DoS and network-based
amplification attacks and provides upper bounds for resource (network, memory)
usage in the client based on protocol requirements to decode, buffer, cache,
store and re-transmit messages which in turn translate into performance and
protection tradeoffs, ensuring capacity to handle worst cases during recovery
from network instability.

In particular, blocks—-currently the only message type without a practical
SSZ-derived upper bound on size—-cannot be fully verified synchronously as part
of gossipsub validity checks. This means that there exist cases where invalid
messages signed by a validator may be amplified by the network.

## libp2p implementations matrix

This section will soon contain a matrix showing the maturity/state of the libp2p
features required by this spec across the languages in which clients are being
developed.
