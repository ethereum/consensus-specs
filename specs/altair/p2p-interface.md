# Altair -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Altair](#modifications-in-altair)
  - [Helpers](#helpers)
    - [Modified `Seen`](#modified-seen)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
    - [New `is_current_slot`](#new-is_current_slot)
    - [New `get_sync_subcommittee_pubkeys`](#new-get_sync_subcommittee_pubkeys)
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

This document contains the consensus-layer networking specifications for Altair.
This document should be viewed as additive to the
[document from Phase 0](../phase0/p2p-interface.md) and will be referred to as
the "Phase 0 document" hereafter. Readers should understand the Phase 0 document
and use it as a basis to understand the changes outlined in this document.

Altair adds new messages, topics and data to the Req-Resp, Gossip and Discovery
domain. Some Phase 0 features will be deprecated, but not removed immediately.

## Modifications in Altair

### Helpers

#### Modified `Seen`

```python
@dataclass
class Seen(object):
    proposer_slots: Set[Tuple[ValidatorIndex, Slot]]
    aggregator_epochs: Set[Tuple[ValidatorIndex, Epoch]]
    aggregate_data_roots: Dict[Root, Set[Tuple[boolean, ...]]]
    voluntary_exit_indices: Set[ValidatorIndex]
    proposer_slashing_indices: Set[ValidatorIndex]
    attester_slashing_indices: Set[ValidatorIndex]
    attestation_validator_epochs: Set[Tuple[ValidatorIndex, Epoch]]
    # [New in Altair]
    sync_contribution_aggregator_slots: Set[Tuple[ValidatorIndex, Slot, uint64]]
    # [New in Altair]
    sync_contribution_data: Dict[Tuple[Slot, Root, uint64], Set[Tuple[boolean, ...]]]
    # [New in Altair]
    sync_message_validator_slots: Set[Tuple[Slot, ValidatorIndex, uint64]]
```

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

#### New `is_current_slot`

```python
def is_current_slot(
    state: BeaconState,
    slot: Slot,
    current_time_ms: uint64,
) -> bool:
    """
    Check if the given slot is the current slot
    (with MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance).
    """
    return is_within_slot_range(state, slot, 0, current_time_ms)
```

#### New `get_sync_subcommittee_pubkeys`

```python
def get_sync_subcommittee_pubkeys(
    state: BeaconState, subcommittee_index: uint64
) -> Sequence[BLSPubkey]:
    # Committees assigned to `slot` sign for `slot - 1`
    # This creates the exceptional logic below when transitioning between sync committee periods
    next_slot_epoch = compute_epoch_at_slot(Slot(state.slot + 1))
    if compute_sync_committee_period(get_current_epoch(state)) == compute_sync_committee_period(
        next_slot_epoch
    ):
        sync_committee = state.current_sync_committee
    else:
        sync_committee = state.next_sync_committee

    # Return pubkeys for the subcommittee index
    sync_subcommittee_size = SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT
    i = subcommittee_index * sync_subcommittee_size
    return sync_committee.pubkeys[i : i + sync_subcommittee_size]
```

### MetaData

The `MetaData` stored locally by clients is updated with an additional field to
communicate the sync committee subnet subscriptions:

```
(
  seq_number: uint64
  attnets: Bitvector[ATTESTATION_SUBNET_COUNT]
  syncnets: Bitvector[SYNC_COMMITTEE_SUBNET_COUNT]
)
```

Where

- `seq_number` and `attnets` have the same meaning defined in the Phase 0
  document.
- `syncnets` is a `Bitvector` representing the node's sync committee subnet
  subscriptions. This field should mirror the data in the node's ENR as outlined
  in the [validator guide](./validator.md#sync-committee-subnet-stability).

### The gossip domain: gossipsub

Gossip meshes are added in Altair to support the consensus activities of the
sync committees. Validators use an aggregation scheme to balance the processing
and networking load across all of the relevant actors.

#### Topics and messages

Topics follow the same specification as in the Phase 0 document. New topics are
added in Altair to support the sync committees and the beacon block topic is
updated with the modified type.

The specification around the creation, validation, and dissemination of messages
has not changed from the Phase 0 document.

The derivation of the `message-id` has changed starting with Altair to
incorporate the message `topic` along with the message `data`. These are fields
of the `Message` Protobuf, and interpreted as empty byte strings if missing. The
`message-id` MUST be the following 20 byte value computed from the message:

- If `message.data` has a valid snappy decompression, set `message-id` to the
  first 20 bytes of the `SHA256` hash of the concatenation of the following
  data: `MESSAGE_DOMAIN_VALID_SNAPPY`, the length of the topic byte string
  (encoded as little-endian `uint64`), the topic byte string, and the snappy
  decompressed message data: i.e.
  `SHA256(MESSAGE_DOMAIN_VALID_SNAPPY + uint_to_bytes(uint64(len(message.topic))) + message.topic + snappy_decompress(message.data))[:20]`.
- Otherwise, set `message-id` to the first 20 bytes of the `SHA256` hash of the
  concatenation of the following data: `MESSAGE_DOMAIN_INVALID_SNAPPY`, the
  length of the topic byte string (encoded as little-endian `uint64`), the topic
  byte string, and the raw message data: i.e.
  `SHA256(MESSAGE_DOMAIN_INVALID_SNAPPY + uint_to_bytes(uint64(len(message.topic))) + message.topic + message.data)[:20]`.

Implementations may need to carefully handle the function that computes the
`message-id`. In particular, messages on topics with the Phase 0 fork digest
should use the `message-id` procedure specified in the Phase 0 document.
Messages on topics with the Altair fork digest should use the `message-id`
procedure defined here. If an implementation only supports a single `message-id`
function, it can define a switch inline; for example,
`if topic in phase0_topics: return phase0_msg_id_fn(message) else return altair_msg_id_fn(message)`.

The new topics along with the type of the `data` field of a gossipsub message
are given in this table:

| Name                                    | Message Type                   |
| --------------------------------------- | ------------------------------ |
| `beacon_block`                          | `SignedBeaconBlock` (modified) |
| `sync_committee_contribution_and_proof` | `SignedContributionAndProof`   |
| `sync_committee_{subnet_id}`            | `SyncCommitteeMessage`         |

Definitions of these new types can be found in the
[Altair validator guide](./validator.md#containers).

Note that the `ForkDigestValue` path segment of the topic separates the old and
the new `beacon_block` topics.

##### Global topics

Altair changes the type of the global beacon block topic and adds one global
topic to propagate partially aggregated sync committee messages to all potential
proposers of beacon blocks.

###### `beacon_block`

The existing specification for this topic does not change from the Phase 0
document, but the type of the payload does change to the (modified)
`SignedBeaconBlock`. This type changes due to the inclusion of the inner
`BeaconBlockBody` that is modified in Altair.

See the [state transition document](./beacon-chain.md#beaconblockbody) for
Altair for further details.

###### `sync_committee_contribution_and_proof`

This topic is used to propagate partially aggregated sync committee messages to
be included in future blocks. The `state` parameter is the head state.

```python
def validate_sync_committee_contribution_and_proof_gossip(
    seen: Seen,
    state: BeaconState,
    signed_contribution_and_proof: SignedContributionAndProof,
    current_time_ms: uint64,
) -> None:
    """
    Validate a SignedContributionAndProof for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    contribution_and_proof = signed_contribution_and_proof.message
    contribution = contribution_and_proof.contribution

    # [IGNORE] The contribution's slot is for the current slot
    # (with a MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance)
    if not is_current_slot(state, contribution.slot, current_time_ms):
        raise GossipIgnore("contribution is not for the current slot")

    # [REJECT] The subcommittee index is in the allowed range
    if contribution.subcommittee_index >= SYNC_COMMITTEE_SUBNET_COUNT:
        raise GossipReject("subcommittee index out of range")

    # [REJECT] The contribution has participants
    if not any(contribution.aggregation_bits):
        raise GossipReject("contribution has no participants")

    # [REJECT] The selection_proof selects the validator as an aggregator for the slot
    if not is_sync_committee_aggregator(contribution_and_proof.selection_proof):
        raise GossipReject("validator is not selected as aggregator")

    # [REJECT] The aggregator index is valid
    if contribution_and_proof.aggregator_index >= len(state.validators):
        raise GossipReject("aggregator index out of range")

    # [REJECT] The aggregator's validator index is in the declared subcommittee
    # of the current sync committee
    aggregator_pubkey = state.validators[contribution_and_proof.aggregator_index].pubkey
    subcommittee_pubkeys = get_sync_subcommittee_pubkeys(state, contribution.subcommittee_index)
    if aggregator_pubkey not in subcommittee_pubkeys:
        raise GossipReject("aggregator not in subcommittee")

    # [IGNORE] A valid sync committee contribution with equal slot, beacon_block_root
    # and subcommittee_index whose aggregation_bits is non-strict superset
    # has not already been seen
    contribution_key = (
        contribution.slot,
        contribution.beacon_block_root,
        contribution.subcommittee_index,
    )
    contribution_bits = tuple(bool(bit) for bit in contribution.aggregation_bits)
    seen_bits = seen.sync_contribution_data.get(contribution_key, set())
    if is_non_strict_superset(seen_bits, contribution_bits):
        raise GossipIgnore("already seen contribution for this data")

    # [IGNORE] The sync committee contribution is the first valid contribution received
    # for the aggregator with index contribution_and_proof.aggregator_index
    # for the slot contribution.slot and subcommittee index contribution.subcommittee_index
    aggregator_key = (
        contribution_and_proof.aggregator_index,
        contribution.slot,
        contribution.subcommittee_index,
    )
    if aggregator_key in seen.sync_contribution_aggregator_slots:
        raise GossipIgnore("already seen contribution from this aggregator")

    # [REJECT] The contribution_and_proof.selection_proof is a valid signature
    # of the SyncAggregatorSelectionData derived from the contribution
    # by the validator with index contribution_and_proof.aggregator_index
    selection_data = SyncAggregatorSelectionData(
        slot=contribution.slot,
        subcommittee_index=contribution.subcommittee_index,
    )
    domain = get_domain(
        state, DOMAIN_SYNC_COMMITTEE_SELECTION_PROOF, compute_epoch_at_slot(contribution.slot)
    )
    signing_root = compute_signing_root(selection_data, domain)
    if not bls.Verify(aggregator_pubkey, signing_root, contribution_and_proof.selection_proof):
        raise GossipReject("invalid selection proof signature")

    # [REJECT] The aggregator signature, signed_contribution_and_proof.signature, is valid
    domain = get_domain(
        state, DOMAIN_CONTRIBUTION_AND_PROOF, compute_epoch_at_slot(contribution.slot)
    )
    signing_root = compute_signing_root(contribution_and_proof, domain)
    if not bls.Verify(aggregator_pubkey, signing_root, signed_contribution_and_proof.signature):
        raise GossipReject("invalid aggregator signature")

    # [REJECT] The aggregate signature is valid for the message beacon_block_root
    # and aggregate pubkey derived from the participation info in aggregation_bits
    # for the subcommittee specified by the contribution.subcommittee_index
    participant_pubkeys = [
        subcommittee_pubkeys[i] for i, bit in enumerate(contribution.aggregation_bits) if bit
    ]
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, compute_epoch_at_slot(contribution.slot))
    signing_root = compute_signing_root(contribution.beacon_block_root, domain)
    if not eth_fast_aggregate_verify(participant_pubkeys, signing_root, contribution.signature):
        raise GossipReject("invalid aggregate signature")

    # Mark this contribution as seen
    seen.sync_contribution_aggregator_slots.add(aggregator_key)
    if contribution_key not in seen.sync_contribution_data:
        seen.sync_contribution_data[contribution_key] = set()
    seen.sync_contribution_data[contribution_key].add(contribution_bits)
```

##### Sync committee subnets

Sync committee subnets are used to propagate unaggregated sync committee
messages to subsections of the network.

###### `sync_committee_{subnet_id}`

The `sync_committee_{subnet_id}` topics are used to propagate unaggregated sync
committee messages to the subnet `subnet_id` to be aggregated before being
gossiped to the global `sync_committee_contribution_and_proof` topic. The
`state` parameter is the head state.

```python
def validate_sync_committee_message_gossip(
    seen: Seen,
    state: BeaconState,
    sync_committee_message: SyncCommitteeMessage,
    subnet_id: uint64,
    current_time_ms: uint64,
) -> None:
    """
    Validate a SyncCommitteeMessage for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    # [IGNORE] The message's slot is for the current slot
    # (with a MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance)
    if not is_current_slot(state, sync_committee_message.slot, current_time_ms):
        raise GossipIgnore("message is not for the current slot")

    # [REJECT] The validator index is valid
    if sync_committee_message.validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    # [REJECT] The subnet_id is valid for the given validator
    # (this implies the validator is part of the broader current sync committee
    # along with the correct subcommittee)
    valid_subnets = compute_subnets_for_sync_committee(
        state, sync_committee_message.validator_index
    )
    if subnet_id not in valid_subnets:
        raise GossipReject("subnet_id is not valid for the validator")

    # [IGNORE] There has been no other valid sync committee message for the declared slot
    # for the validator referenced by sync_committee_message.validator_index
    # (this validation is per topic so that for a given slot, multiple messages could be
    # forwarded with the same validator_index as long as the subnet_ids are distinct)
    message_key = (sync_committee_message.slot, sync_committee_message.validator_index, subnet_id)
    if message_key in seen.sync_message_validator_slots:
        raise GossipIgnore("already seen message from this validator for this slot and subnet")

    # [REJECT] The signature is valid for the message beacon_block_root
    # for the validator referenced by validator_index
    validator = state.validators[sync_committee_message.validator_index]
    domain = get_domain(
        state, DOMAIN_SYNC_COMMITTEE, compute_epoch_at_slot(sync_committee_message.slot)
    )
    signing_root = compute_signing_root(sync_committee_message.beacon_block_root, domain)
    if not bls.Verify(validator.pubkey, signing_root, sync_committee_message.signature):
        raise GossipReject("invalid sync committee message signature")

    # Mark this message as seen
    seen.sync_message_validator_slots.add(message_key)
```

##### Sync committees and aggregation

The aggregation scheme closely follows the design of the attestation aggregation
scheme. Sync committee messages are broadcast into "subnets" defined by a topic.
The number of subnets is defined by `SYNC_COMMITTEE_SUBNET_COUNT` in the
[Altair validator guide](./validator.md#constants). Sync committee members are
divided into "subcommittees" which are then assigned to a subnet for the
duration of tenure in the sync committee. Individual validators can be
duplicated in the broader sync committee such that they are included multiple
times in a given subcommittee or across multiple subcommittees.

Unaggregated messages (along with metadata) are sent as `SyncCommitteeMessage`s
on the `sync_committee_{subnet_id}` topics.

Aggregated sync committee messages are packaged into (signed)
`SyncCommitteeContribution` along with proofs and gossiped to the
`sync_committee_contribution_and_proof` topic.

#### Transitioning the gossip

With any fork, the fork version, and thus the `ForkDigestValue`, change. Message
types are unique per topic, and so for a smooth transition a node must
temporarily subscribe to both the old and new topics.

The topics that are not removed in a fork are updated with a new
`ForkDigestValue`. In advance of the fork, a node SHOULD subscribe to the
post-fork variants of the topics.

Subscriptions are expected to be well-received, all updated nodes should
subscribe as well. Topic-meshes can be grafted quickly as the nodes are already
connected and exchanging gossip control messages.

Messages SHOULD NOT be re-broadcast from one fork to the other. A node's
behavior before the fork and after the fork are as follows:

Pre-fork:

- Peers who propagate messages on the post-fork topics MAY be scored negatively
  proportionally to time till fork, to account for clock discrepancy.
- Messages can be IGNORED on the post-fork topics, with a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` margin.

Post-fork:

- Peers who propagate messages on the pre-fork topics MUST NOT be scored
  negatively. Lagging IWANT may force them to.
- Messages on pre and post-fork variants of topics share application-level
  caches. E.g. an attestation on the both the old and new topic is ignored like
  any duplicate.
- Two epochs after the fork, pre-fork topics SHOULD be unsubscribed from. This
  is well after the configured `seen_ttl`.

### The Req/Resp domain

#### Req-Resp interaction

An additional `<context-bytes>` field is introduced to the `response_chunk` as
defined in the Phase 0 document:

```
response_chunk  ::= <result> | <context-bytes> | <encoding-dependent-header> | <encoded-payload>
```

All Phase 0 methods are compatible: `<context-bytes>` is empty by default. On a
non-zero `<result>` with `ErrorMessage` payload, the `<context-bytes>` is also
empty.

In Altair and later forks, `<context-bytes>` functions as a short meta-data,
defined per req-resp method, and can parametrize the payload decoder.

##### `ForkDigest`-context

Starting with Altair, and in future forks, SSZ type definitions may change. For
this common case, we define the `ForkDigest`-context:

A fixed-width 4 byte `<context-bytes>`, set to the `ForkDigest` matching the
chunk: `compute_fork_digest(genesis_validators_root, epoch)`.

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

Request and Response remain unchanged. A `ForkDigest`-context is used to select
the fork namespace of the Response type.

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by `compute_epoch_at_slot(signed_beacon_block.message.slot)`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`         | Chunk SSZ type             |
| ---------------------- | -------------------------- |
| `GENESIS_FORK_VERSION` | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`  | `altair.SignedBeaconBlock` |

##### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

Request and Response remain unchanged. A `ForkDigest`-context is used to select
the fork namespace of the Response type.

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by `compute_epoch_at_slot(signed_beacon_block.message.slot)`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`         | Chunk SSZ type             |
| ---------------------- | -------------------------- |
| `GENESIS_FORK_VERSION` | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`  | `altair.SignedBeaconBlock` |

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

In advance of the fork, implementations can opt in to both run the v1 and v2 for
a smooth transition. This is non-breaking, and is recommended as soon as the
fork specification is stable.

The v1 variants will be deprecated, and implementations should use v2 when
available (as negotiated with peers via LibP2P multistream-select).

The v1 method MAY be unregistered at the fork boundary. In the event of a
request on v1 for an Altair specific payload, the responder MUST return the
**InvalidRequest** response code.

### The discovery domain: discv5

#### ENR structure

##### Sync committee bitfield

An additional bitfield is added to the ENR under the key `syncnets` to
facilitate sync committee subnet discovery. The length of this bitfield is
`SYNC_COMMITTEE_SUBNET_COUNT` where each bit corresponds to a distinct
`subnet_id` for a specific sync committee subnet. The `i`th bit is set in this
bitfield if the validator is currently subscribed to the `sync_committee_{i}`
topic.

| Key        | Value                                        |
| :--------- | :------------------------------------------- |
| `syncnets` | SSZ `Bitvector[SYNC_COMMITTEE_SUBNET_COUNT]` |

See the [validator document](./validator.md#sync-committee-subnet-stability) for
further details on how the new bits are used.
