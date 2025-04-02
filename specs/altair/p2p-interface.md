# Altair -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Altair](#modifications-in-altair)
  - [MetaData](#metadata)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
        - [`sync_committee_contribution_and_proof`](#sync_committee_contribution_and_proof)
      - [Sync committee subnets](#sync-committee-subnets)
        - [`sync_committee_{subnet_id}`](#sync_committee_subnet_id)
      - [Sync committees and aggregation](#sync-committees-and-aggregation)
    - [Transitioning the gossip](#transitioning-the-gossip)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Req-Resp interaction](#req-resp-interaction)
      - [`ForkDigest`-context](#forkdigest-context)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
      - [GetMetaData v2](#getmetadata-v2)
    - [Transitioning from v1 to v2](#transitioning-from-v1-to-v2)
  - [The discovery domain: discv5](#the-discovery-domain-discv5)
    - [ENR structure](#enr-structure)
      - [Sync committee bitfield](#sync-committee-bitfield)

<!-- mdformat-toc end -->

## Introduction

This document contains the networking specification for Altair.
This document should be viewed as additive to the [document from Phase 0](../phase0/p2p-interface.md) and will be referred to as the "Phase 0 document" hereafter.
Readers should understand the Phase 0 document and use it as a basis to understand the changes outlined in this document.

Altair adds new messages, topics and data to the Req-Resp, Gossip and Discovery domain. Some Phase 0 features will be deprecated, but not removed immediately.

## Modifications in Altair

### MetaData

The `MetaData` stored locally by clients is updated with an additional field to communicate the sync committee subnet subscriptions:

```
(
  seq_number: uint64
  attnets: Bitvector[ATTESTATION_SUBNET_COUNT]
  syncnets: Bitvector[SYNC_COMMITTEE_SUBNET_COUNT]
)
```

Where

- `seq_number` and `attnets` have the same meaning defined in the Phase 0 document.
- `syncnets` is a `Bitvector` representing the node's sync committee subnet subscriptions. This field should mirror the data in the node's ENR as outlined in the [validator guide](./validator.md#sync-committee-subnet-stability).

### The gossip domain: gossipsub

Gossip meshes are added in Altair to support the consensus activities of the sync committees.
Validators use an aggregation scheme to balance the processing and networking load across all of the relevant actors.

#### Topics and messages

Topics follow the same specification as in the Phase 0 document.
New topics are added in Altair to support the sync committees and the beacon block topic is updated with the modified type.

The specification around the creation, validation, and dissemination of messages has not changed from the Phase 0 document.

The derivation of the `message-id` has changed starting with Altair to incorporate the message `topic` along with the message `data`. These are fields of the `Message` Protobuf, and interpreted as empty byte strings if missing.
The `message-id` MUST be the following 20 byte value computed from the message:

* If `message.data` has a valid snappy decompression, set `message-id` to the first 20 bytes of the `SHA256` hash of
  the concatenation of the following data: `MESSAGE_DOMAIN_VALID_SNAPPY`, the length of the topic byte string (encoded as little-endian `uint64`),
  the topic byte string, and the snappy decompressed message data:
  i.e. `SHA256(MESSAGE_DOMAIN_VALID_SNAPPY + uint_to_bytes(uint64(len(message.topic))) + message.topic + snappy_decompress(message.data))[:20]`.
* Otherwise, set `message-id` to the first 20 bytes of the `SHA256` hash of
  the concatenation of the following data: `MESSAGE_DOMAIN_INVALID_SNAPPY`, the length of the topic byte string (encoded as little-endian `uint64`),
  the topic byte string, and the raw message data:
  i.e. `SHA256(MESSAGE_DOMAIN_INVALID_SNAPPY + uint_to_bytes(uint64(len(message.topic))) + message.topic + message.data)[:20]`.

Implementations may need to carefully handle the function that computes the `message-id`. In particular, messages on topics with the Phase 0
fork digest should use the `message-id` procedure specified in the Phase 0 document.
Messages on topics with the Altair fork digest should use the `message-id` procedure defined here.
If an implementation only supports a single `message-id` function, it can define a switch inline;
for example, `if topic in phase0_topics: return phase0_msg_id_fn(message) else return altair_msg_id_fn(message)`.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `beacon_block` | `SignedBeaconBlock` (modified) |
| `sync_committee_contribution_and_proof` | `SignedContributionAndProof` |
| `sync_committee_{subnet_id}` | `SyncCommitteeMessage` |

Definitions of these new types can be found in the [Altair validator guide](./validator.md#containers).

Note that the `ForkDigestValue` path segment of the topic separates the old and the new `beacon_block` topics.

##### Global topics

Altair changes the type of the global beacon block topic and adds one global topic to propagate partially aggregated sync committee messages to all potential proposers of beacon blocks.

###### `beacon_block`

The existing specification for this topic does not change from the Phase 0 document,
but the type of the payload does change to the (modified) `SignedBeaconBlock`.
This type changes due to the inclusion of the inner `BeaconBlockBody` that is modified in Altair.

See the [state transition document](./beacon-chain.md#beaconblockbody) for Altair for further details.

###### `sync_committee_contribution_and_proof`

This topic is used to propagate partially aggregated sync committee messages to be included in future blocks.

The following validations MUST pass before forwarding the `signed_contribution_and_proof` on the network; define `contribution_and_proof = signed_contribution_and_proof.message`, `contribution = contribution_and_proof.contribution`, and the following function `get_sync_subcommittee_pubkeys` for convenience:

```python
def get_sync_subcommittee_pubkeys(state: BeaconState, subcommittee_index: uint64) -> Sequence[BLSPubkey]:
    # Committees assigned to `slot` sign for `slot - 1`
    # This creates the exceptional logic below when transitioning between sync committee periods
    next_slot_epoch = compute_epoch_at_slot(Slot(state.slot + 1))
    if compute_sync_committee_period(get_current_epoch(state)) == compute_sync_committee_period(next_slot_epoch):
        sync_committee = state.current_sync_committee
    else:
        sync_committee = state.next_sync_committee

    # Return pubkeys for the subcommittee index
    sync_subcommittee_size = SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT
    i = subcommittee_index * sync_subcommittee_size
    return sync_committee.pubkeys[i:i + sync_subcommittee_size]
```

- _[IGNORE]_ The contribution's slot is for the current slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance), i.e. `contribution.slot == current_slot`.
- _[REJECT]_ The subcommittee index is in the allowed range, i.e. `contribution.subcommittee_index < SYNC_COMMITTEE_SUBNET_COUNT`.
- _[REJECT]_ The contribution has participants --
  that is, `any(contribution.aggregation_bits)`.
- _[REJECT]_ `contribution_and_proof.selection_proof` selects the validator as an aggregator for the slot -- i.e. `is_sync_committee_aggregator(contribution_and_proof.selection_proof)` returns `True`.
- _[REJECT]_ The aggregator's validator index is in the declared subcommittee of the current sync committee --
  i.e. `state.validators[contribution_and_proof.aggregator_index].pubkey in get_sync_subcommittee_pubkeys(state, contribution.subcommittee_index)`.
- _[IGNORE]_ A valid sync committee contribution with equal `slot`, `beacon_block_root` and `subcommittee_index` whose `aggregation_bits` is non-strict superset has _not_ already been seen.
- _[IGNORE]_ The sync committee contribution is the first valid contribution received for the aggregator with index `contribution_and_proof.aggregator_index`
  for the slot `contribution.slot` and subcommittee index `contribution.subcommittee_index`
  (this requires maintaining a cache of size `SYNC_COMMITTEE_SIZE` for this topic that can be flushed after each slot).
- _[REJECT]_ The `contribution_and_proof.selection_proof` is a valid signature of the `SyncAggregatorSelectionData` derived from the `contribution` by the validator with index `contribution_and_proof.aggregator_index`.
- _[REJECT]_ The aggregator signature, `signed_contribution_and_proof.signature`, is valid.
- _[REJECT]_ The aggregate signature is valid for the message `beacon_block_root` and aggregate pubkey derived from the participation info in `aggregation_bits` for the subcommittee specified by the `contribution.subcommittee_index`.

##### Sync committee subnets

Sync committee subnets are used to propagate unaggregated sync committee messages to subsections of the network.

###### `sync_committee_{subnet_id}`

The `sync_committee_{subnet_id}` topics are used to propagate unaggregated sync committee messages to the subnet `subnet_id` to be aggregated before being gossiped to the global `sync_committee_contribution_and_proof` topic.

The following validations MUST pass before forwarding the `sync_committee_message` on the network:

- _[IGNORE]_ The message's slot is for the current slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance), i.e. `sync_committee_message.slot == current_slot`.
- _[REJECT]_ The `subnet_id` is valid for the given validator, i.e. `subnet_id in compute_subnets_for_sync_committee(state, sync_committee_message.validator_index)`.
  Note this validation implies the validator is part of the broader current sync committee along with the correct subcommittee.
- _[IGNORE]_ There has been no other valid sync committee message for the declared `slot` for the validator referenced by `sync_committee_message.validator_index`
  (this requires maintaining a cache of size `SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT` for each subnet that can be flushed after each slot).
  Note this validation is _per topic_ so that for a given `slot`, multiple messages could be forwarded with the same `validator_index` as long as the `subnet_id`s are distinct.
- _[REJECT]_ The `signature` is valid for the message `beacon_block_root` for the validator referenced by `validator_index`.

##### Sync committees and aggregation

The aggregation scheme closely follows the design of the attestation aggregation scheme.
Sync committee messages are broadcast into "subnets" defined by a topic.
The number of subnets is defined by `SYNC_COMMITTEE_SUBNET_COUNT` in the [Altair validator guide](./validator.md#constants).
Sync committee members are divided into "subcommittees" which are then assigned to a subnet for the duration of tenure in the sync committee.
Individual validators can be duplicated in the broader sync committee such that they are included multiple times in a given subcommittee or across multiple subcommittees.

Unaggregated messages (along with metadata) are sent as `SyncCommitteeMessage`s on the `sync_committee_{subnet_id}` topics.

Aggregated sync committee messages are packaged into (signed) `SyncCommitteeContribution` along with proofs and gossiped to the `sync_committee_contribution_and_proof` topic.

#### Transitioning the gossip

With any fork, the fork version, and thus the `ForkDigestValue`, change.
Message types are unique per topic, and so for a smooth transition a node must temporarily subscribe to both the old and new topics.

The topics that are not removed in a fork are updated with a new `ForkDigestValue`. In advance of the fork, a node SHOULD subscribe to the post-fork variants of the topics.

Subscriptions are expected to be well-received, all updated nodes should subscribe as well.
Topic-meshes can be grafted quickly as the nodes are already connected and exchanging gossip control messages.

Messages SHOULD NOT be re-broadcast from one fork to the other.
A node's behavior before the fork and after the fork are as follows:

Pre-fork:

- Peers who propagate messages on the post-fork topics MAY be scored negatively proportionally to time till fork,
  to account for clock discrepancy.
- Messages can be IGNORED on the post-fork topics, with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` margin.

Post-fork:

- Peers who propagate messages on the pre-fork topics MUST NOT be scored negatively. Lagging IWANT may force them to.
- Messages on pre and post-fork variants of topics share application-level caches.
  E.g. an attestation on the both the old and new topic is ignored like any duplicate.
- Two epochs after the fork, pre-fork topics SHOULD be unsubscribed from. This is well after the configured `seen_ttl`.

### The Req/Resp domain

#### Req-Resp interaction

An additional `<context-bytes>` field is introduced to the `response_chunk` as defined in the Phase 0 document:

```
response_chunk  ::= <result> | <context-bytes> | <encoding-dependent-header> | <encoded-payload>
```

All Phase 0 methods are compatible: `<context-bytes>` is empty by default.
On a non-zero `<result>` with `ErrorMessage` payload, the `<context-bytes>` is also empty.

In Altair and later forks, `<context-bytes>` functions as a short meta-data,
defined per req-resp method, and can parametrize the payload decoder.

##### `ForkDigest`-context

Starting with Altair, and in future forks, SSZ type definitions may change.
For this common case, we define the `ForkDigest`-context:

A fixed-width 4 byte `<context-bytes>`, set to the `ForkDigest` matching the chunk:
 `compute_fork_digest(fork_version, genesis_validators_root)`.

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

Request and Response remain unchanged. A `ForkDigest`-context is used to select the fork namespace of the Response type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type             |
| ------------------------ | -------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock` |

##### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

Request and Response remain unchanged. A `ForkDigest`-context is used to select the fork namespace of the Response type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type             |
| ------------------------ | -------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock` |

##### GetMetaData v2

**Protocol ID:** `/eth2/beacon_chain/req/metadata/2/`

No Request Content.

Response Content:

```
(
  MetaData
)
```

Requests the MetaData of a peer, using the new `MetaData` definition given above
that is extended from phase 0 in Altair. Other conditions for the `GetMetaData`
protocol are unchanged from the phase 0 p2p networking document.

#### Transitioning from v1 to v2

In advance of the fork, implementations can opt in to both run the v1 and v2 for a smooth transition.
This is non-breaking, and is recommended as soon as the fork specification is stable.

The v1 variants will be deprecated, and implementations should use v2 when available
(as negotiated with peers via LibP2P multistream-select).

The v1 method MAY be unregistered at the fork boundary.
In the event of a request on v1 for an Altair specific payload,
the responder MUST return the **InvalidRequest** response code.

### The discovery domain: discv5

#### ENR structure

##### Sync committee bitfield

An additional bitfield is added to the ENR under the key `syncnets` to facilitate sync committee subnet discovery.
The length of this bitfield is `SYNC_COMMITTEE_SUBNET_COUNT` where each bit corresponds to a distinct `subnet_id` for a specific sync committee subnet.
The `i`th bit is set in this bitfield if the validator is currently subscribed to the `sync_committee_{i}` topic.

| Key          | Value                                            |
|:-------------|:-------------------------------------------------|
| `syncnets`    | SSZ `Bitvector[SYNC_COMMITTEE_SUBNET_COUNT]`        |

See the [validator document](./validator.md#sync-committee-subnet-stability) for further details on how the new bits are used.
