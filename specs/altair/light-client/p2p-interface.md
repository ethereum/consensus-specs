# Altair Light Client -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Networking](#networking)
  - [Configuration](#configuration)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`light_client_finality_update`](#light_client_finality_update)
        - [`light_client_optimistic_update`](#light_client_optimistic_update)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [GetLightClientBootstrap](#getlightclientbootstrap)
      - [LightClientUpdatesByRange](#lightclientupdatesbyrange)
      - [GetLightClientFinalityUpdate](#getlightclientfinalityupdate)
      - [GetLightClientOptimisticUpdate](#getlightclientoptimisticupdate)
- [Light clients](#light-clients)
- [Validator assignments](#validator-assignments)
  - [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Sync committee](#sync-committee)

<!-- mdformat-toc end -->

## Networking

This section extends the
[networking specification for Altair](../p2p-interface.md) with additional
messages, topics and data to the Req-Resp and Gossip domains.

### Configuration

| Name                               | Value          | Description                                                         |
| ---------------------------------- | -------------- | ------------------------------------------------------------------- |
| `MAX_REQUEST_LIGHT_CLIENT_UPDATES` | `2**7` (= 128) | Maximum number of `LightClientUpdate` instances in a single request |

### The gossip domain: gossipsub

Gossip meshes are added to allow light clients to stay in sync with the network.

#### Topics and messages

New global topics are added to provide light clients with the latest updates.

| name                             | Message Type                  |
| -------------------------------- | ----------------------------- |
| `light_client_finality_update`   | `LightClientFinalityUpdate`   |
| `light_client_optimistic_update` | `LightClientOptimisticUpdate` |

##### Global topics

###### `light_client_finality_update`

This topic is used to propagate the latest `LightClientFinalityUpdate` to light
clients, allowing them to keep track of the latest `finalized_header`.

The following validations MUST pass before forwarding the `finality_update` on
the network.

- _[IGNORE]_ The `finalized_header.beacon.slot` is greater than that of all
  previously forwarded `finality_update`s, or it matches the highest previously
  forwarded slot and also has a `sync_aggregate` indicating supermajority (>
  2/3) sync committee participation while the previously forwarded
  `finality_update` for that slot did not indicate supermajority
- _[IGNORE]_ The `finality_update` is received after the block at
  `signature_slot` was given enough time to propagate through the network --
  i.e. validate that one-third of `finality_update.signature_slot` has
  transpired (`SECONDS_PER_SLOT / INTERVALS_PER_SLOT` seconds after the start of
  the slot, with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance)

For full nodes, the following validations MUST additionally pass before
forwarding the `finality_update` on the network.

- _[IGNORE]_ The received `finality_update` matches the locally computed one
  exactly (as defined in
  [`create_light_client_finality_update`](./full-node.md#create_light_client_finality_update))

For light clients, the following validations MUST additionally pass before
forwarding the `finality_update` on the network.

- _[REJECT]_ The `finality_update` is valid -- i.e. validate that
  `process_light_client_finality_update` does not indicate errors
- _[IGNORE]_ The `finality_update` advances the `finalized_header` of the local
  `LightClientStore` -- i.e. validate that processing `finality_update`
  increases `store.finalized_header.beacon.slot`

Light clients SHOULD call `process_light_client_finality_update` even if the
message is ignored.

The gossip `ForkDigestValue` is determined based on
`compute_fork_version(compute_epoch_at_slot(finality_update.attested_header.beacon.slot))`.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`                  | Message SSZ type                   |
| ------------------------------- | ---------------------------------- |
| `GENESIS_FORK_VERSION`          | n/a                                |
| `ALTAIR_FORK_VERSION` and later | `altair.LightClientFinalityUpdate` |

###### `light_client_optimistic_update`

This topic is used to propagate the latest `LightClientOptimisticUpdate` to
light clients, allowing them to keep track of the latest `optimistic_header`.

The following validations MUST pass before forwarding the `optimistic_update` on
the network.

- _[IGNORE]_ The `attested_header.beacon.slot` is greater than that of all
  previously forwarded `optimistic_update`s
- _[IGNORE]_ The `optimistic_update` is received after the block at
  `signature_slot` was given enough time to propagate through the network --
  i.e. validate that one-third of `optimistic_update.signature_slot` has
  transpired (`SECONDS_PER_SLOT / INTERVALS_PER_SLOT` seconds after the start of
  the slot, with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance)

For full nodes, the following validations MUST additionally pass before
forwarding the `optimistic_update` on the network.

- _[IGNORE]_ The received `optimistic_update` matches the locally computed one
  exactly (as defined in
  [`create_light_client_optimistic_update`](./full-node.md#create_light_client_optimistic_update))

For light clients, the following validations MUST additionally pass before
forwarding the `optimistic_update` on the network.

- _[REJECT]_ The `optimistic_update` is valid -- i.e. validate that
  `process_light_client_optimistic_update` does not indicate errors
- _[IGNORE]_ The `optimistic_update` either matches corresponding fields of the
  most recently forwarded `LightClientFinalityUpdate` (if any), or it advances
  the `optimistic_header` of the local `LightClientStore` -- i.e. validate that
  processing `optimistic_update` increases `store.optimistic_header.beacon.slot`

Light clients SHOULD call `process_light_client_optimistic_update` even if the
message is ignored.

The gossip `ForkDigestValue` is determined based on
`compute_fork_version(compute_epoch_at_slot(optimistic_update.attested_header.beacon.slot))`.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`                  | Message SSZ type                     |
| ------------------------------- | ------------------------------------ |
| `GENESIS_FORK_VERSION`          | n/a                                  |
| `ALTAIR_FORK_VERSION` and later | `altair.LightClientOptimisticUpdate` |

### The Req/Resp domain

#### Messages

##### GetLightClientBootstrap

**Protocol ID:** `/eth2/beacon_chain/req/light_client_bootstrap/1/`

Request Content:

```
(
  Root
)
```

Response Content:

```
(
  LightClientBootstrap
)
```

Requests the `LightClientBootstrap` structure corresponding to a given
post-Altair beacon block root.

The request MUST be encoded as an SSZ-field.

Peers SHOULD provide results as defined in
[`create_light_client_bootstrap`](./full-node.md#create_light_client_bootstrap).
To fulfill a request, the requested block and its post state need to be known.

When a `LightClientBootstrap` instance cannot be produced for a given block
root, peers SHOULD respond with error code `3: ResourceUnavailable`.

A `ForkDigest`-context based on
`compute_fork_version(compute_epoch_at_slot(bootstrap.header.beacon.slot))` is
used to select the fork namespace of the Response type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`                  | Response SSZ type             |
| ------------------------------- | ----------------------------- |
| `GENESIS_FORK_VERSION`          | n/a                           |
| `ALTAIR_FORK_VERSION` and later | `altair.LightClientBootstrap` |

##### LightClientUpdatesByRange

**Protocol ID:** `/eth2/beacon_chain/req/light_client_updates_by_range/1/`

Request Content:

```
(
  start_period: uint64
  count: uint64
)
```

Response Content:

```
(
  List[LightClientUpdate, MAX_REQUEST_LIGHT_CLIENT_UPDATES]
)
```

Requests the `LightClientUpdate` instances in the sync committee period range
`[start_period, start_period + count)`, leading up to the current head sync
committee period as selected by fork choice.

The request MUST be encoded as an SSZ-container.

The response MUST consist of zero or more `response_chunk`. Each _successful_
`response_chunk` MUST contain a single `LightClientUpdate` payload.

Peers SHOULD provide results as defined in
[`create_light_client_update`](./full-node.md#create_light_client_update). They
MUST respond with at least the earliest known result within the requested range,
and MUST send results in consecutive order (by period). The response MUST NOT
contain more than `min(MAX_REQUEST_LIGHT_CLIENT_UPDATES, count)` results.

For each `response_chunk`, a `ForkDigest`-context based on
`compute_fork_version(compute_epoch_at_slot(update.attested_header.beacon.slot))`
is used to select the fork namespace of the Response type. Note that this
`fork_version` may be different from the one used to verify the
`update.sync_aggregate`, which is based on `update.signature_slot`.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`                  | Response chunk SSZ type    |
| ------------------------------- | -------------------------- |
| `GENESIS_FORK_VERSION`          | n/a                        |
| `ALTAIR_FORK_VERSION` and later | `altair.LightClientUpdate` |

##### GetLightClientFinalityUpdate

**Protocol ID:** `/eth2/beacon_chain/req/light_client_finality_update/1/`

No Request Content.

Response Content:

```
(
  LightClientFinalityUpdate
)
```

Requests the latest `LightClientFinalityUpdate` known by a peer.

Peers SHOULD provide results as defined in
[`create_light_client_finality_update`](./full-node.md#create_light_client_finality_update).

When no `LightClientFinalityUpdate` is available, peers SHOULD respond with
error code `3: ResourceUnavailable`.

A `ForkDigest`-context based on
`compute_fork_version(compute_epoch_at_slot(finality_update.attested_header.beacon.slot))`
is used to select the fork namespace of the Response type. Note that this
`fork_version` may be different from the one used to verify the
`finality_update.sync_aggregate`, which is based on
`finality_update.signature_slot`.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`                  | Response SSZ type                  |
| ------------------------------- | ---------------------------------- |
| `GENESIS_FORK_VERSION`          | n/a                                |
| `ALTAIR_FORK_VERSION` and later | `altair.LightClientFinalityUpdate` |

##### GetLightClientOptimisticUpdate

**Protocol ID:** `/eth2/beacon_chain/req/light_client_optimistic_update/1/`

No Request Content.

Response Content:

```
(
  LightClientOptimisticUpdate
)
```

Requests the latest `LightClientOptimisticUpdate` known by a peer.

Peers SHOULD provide results as defined in
[`create_light_client_optimistic_update`](./full-node.md#create_light_client_optimistic_update).

When no `LightClientOptimisticUpdate` is available, peers SHOULD respond with
error code `3: ResourceUnavailable`.

A `ForkDigest`-context based on
`compute_fork_version(compute_epoch_at_slot(optimistic_update.attested_header.beacon.slot))`
is used to select the fork namespace of the Response type. Note that this
`fork_version` may be different from the one used to verify the
`optimistic_update.sync_aggregate`, which is based on
`optimistic_update.signature_slot`.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`                  | Response SSZ type                    |
| ------------------------------- | ------------------------------------ |
| `GENESIS_FORK_VERSION`          | n/a                                  |
| `ALTAIR_FORK_VERSION` and later | `altair.LightClientOptimisticUpdate` |

## Light clients

Light clients using libp2p to stay in sync with the network SHOULD subscribe to
the [`light_client_finality_update`](#light_client_finality_update) and
[`light_client_optimistic_update`](#light_client_optimistic_update) pubsub
topics and validate all received messages while the
[light client sync process](./light-client.md#light-client-sync-process)
supports processing `LightClientFinalityUpdate` and
`LightClientOptimisticUpdate` structures.

Light clients MAY also collect historic light client data and make it available
to other peers. If they do, they SHOULD advertise supported message endpoints in
[the Req/Resp domain](#the-reqresp-domain), and MAY also update the contents of
their [`Status`](../../phase0/p2p-interface.md#status) message to reflect the
locally available light client data.

If only limited light client data is locally available, the light client SHOULD
use data based on `genesis_block` and `GENESIS_SLOT` in its `Status` message.
Hybrid peers that also implement full node functionality MUST only incorporate
data based on their full node sync progress into their `Status` message.

## Validator assignments

This section extends the [honest validator specification](../validator.md) with
additional responsibilities to enable light clients to sync with the network.

### Beacon chain responsibilities

All full nodes SHOULD subscribe to and provide stability on the
[`light_client_finality_update`](#light_client_finality_update) and
[`light_client_optimistic_update`](#light_client_optimistic_update) pubsub
topics by validating all received messages.

### Sync committee

Whenever fork choice selects a new head block with a sync aggregate
participation `>= MIN_SYNC_COMMITTEE_PARTICIPANTS` and a post-Altair parent
block, full nodes with at least one validator assigned to the current sync
committee at the block's `slot` SHOULD broadcast derived light client data as
follows:

- If `finalized_header.beacon.slot` increased, a `LightClientFinalityUpdate`
  SHOULD be broadcasted to the pubsub topic `light_client_finality_update` if no
  matching message has not yet been forwarded as part of gossip validation.
- If `attested_header.beacon.slot` increased, a `LightClientOptimisticUpdate`
  SHOULD be broadcasted to the pubsub topic `light_client_optimistic_update` if
  no matching message has not yet been forwarded as part of gossip validation.

These messages SHOULD be broadcasted after one-third of `slot` has transpired
(`SECONDS_PER_SLOT / INTERVALS_PER_SLOT` seconds after the start of the slot).
To ensure that the corresponding block was given enough time to propagate
through the network, they SHOULD NOT be sent earlier. Note that this is
different from how other messages are handled, e.g., attestations, which may be
sent early.
