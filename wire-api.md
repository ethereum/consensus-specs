# Phase 0 Wire API [WIP]

This is the minimal wire API required for Phase 0 of Eth2.0. Note that this is _not_ the wire protocol but the interface right above. Once we settle on the API required, we can specify the underlying protocol.

All API methods are specified as the plural `list` version, assuming that if singular objects are sent or requested that the input will just be a list of length 1.

"Bad form" is any action that is not explicitly against the protocol but is not in the best interest of one's peers or the protocol in general. Messages/requests that are considered bad form may reduce the reputation of the sending node and may result in being dropped.

## Network topology

Ethereum 2.0 network topology consists of a pubsub mapping of peers to "topics". These topics along with peer mappings effectively form subnets.

The primary topics of core protocol consideration are:
* `beacon`: All messages for the beacon chain are mapped to topic `beacon`.
* `shard-{number}` for all integers, `number` in `range(SHARD_SUBNET_COUNT)`: Messages for a given shard defined by `shard_number` are mapped to topic `shard-{shard_number % SHARD_SUBNET_COUNT}`.

We use `discv5` to discover peers of select topics, and we use `gossipsub`, a libp2p routing protocol, to route messages of a particular topic to the subnet in question.

Note: attempting to broadcast or request messages about a topic not subscribed to by the peer is considered bad form. For example, running `send_attestations(attestations)` where one or more of the attestations have `attestation.data.shard == 5` to a peer not subscribed to `shard-5` might result in that peer dropping the node.

## Dependencies

This document depends on:
* [SSZ spec](https://github.com/ethereum/eth2.0-specs/blob/master/specs/simple-serialize.md)
* [Phase 0 spec](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/core/0_beacon-chain.md)

## API

### Sync

The following is a basic sync protocol akin to eth1.0. _This is very likely to change pending input from those intimately familiar with the pain points of 1.0 sync_.

`status` message is sent in the initial handshake between two peers. After handshake and status exchange, the peer with higher `latest_finalized_epoch` or, if epochs are equal, the higher `best_slot` sends a list of `beacon_block_roots` via `send_beacon_block_roots`.

Status handshake fields:
* `protocol_version`
* `network_id`
* `latest_finalized_root`
* `latest_finalized_epoch`
* `best_root`
* `best_slot`

### Beacon Blocks

Supported pubsub topics:
* `beacon`

The following definitions are used in the API:
* `block_header`: a serialized `BeaconBlock` in which `BeaconBlock.body` is the `hash_tree_root` of the associated `BeaconBlockBody`.
* `block_body`: a serialied `BeaconBlockBody`.
* `block_root`: the `hash_tree_root` of a `BeaconBlock`.

API:
* `send_beacon_block_roots(block_roots)`: Sends list of `block_roots` to peer.
* `send_beacon_block_headers(block_headers)`: Sends list of `block_headers` to peer.
* `request_beacon_block_headers(block_roots)`: Requests the associated `block_headers` for the given `block_roots` from peer.
* `send_beacon_block_bodies(block_bodies)`: Sends list of `block_bodies` to peer.
* `request_beacon_block_bodies(block_roots)`: Requests the associated `block_bodies` for the given `block_roots` from peer.

Notes:
* It is assumed that both the associated `BeaconBlock` and `BeaconBlockBody` can be looked up via `block_root`.

### Attestations

Supported pubsub topics:
* `beacon`
* all `shard-{number}` topics

The following definitions are used in the API:
* `attestation`: a serialized `Attestation` with full serialized `AttestationData` for `Attestation.data`.

API:
* `send_attestations(attestations)`: Sends list of `attestations` to peer.

Notes:
* It is expected that an attestation is only broadcast to either `beacon` topic or `shard-{attestation.data.shard}` topic. Broadcasting to mismatched shard topics is considered bad form.
* It is expected that only aggregate attestations are broadcast to the `beacon` topic. Repeated broadcasting of attestations with a signle signer to the `beacon` topic is considered bad form.
* There is a shard subnet design decision here. Due to the likelihood of `attestation.data` to be highly repeated across a committee during a given slot, it could be valuable to just pass the `attestation` with a `root` in the `attestation.data` field. If the recipient does not already have an `AttestationData` for the received `root`, then the recipient would explicitly request the root. This reduces the total data passed by 184 bytes in the case that the recipient has already received the `attestation.data` but increases the rounds of communication when they haven't.
* We do not currently specify a getter method for an attestation by its `root`. Due to the diverse ways attestations might both be aggregated and stored, it is not feasible to reliably lookup via a `root`. The attestations that a client cares about are (1) those that made it on-chain into a `BeaconBlock` and (2) the most recent set of attestations being actively broadcast on the wire. We might provide a `request_attestations(slot)` or `request_attestations(epoch)` but do not provide it in this minimal API specification.

### Exits

Supported pubsub topics:
* `beacon`

The following definitions are used in the API:
* `exit`: a serialized `Exit`.

API:
* `send_exit(exit)`: Sends `exit` to peer.

Notes:
* We do not specify a getter for an exit by its `root`. Standard usage is for 