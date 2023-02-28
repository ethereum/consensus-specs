# Deneb -- Networking

This document contains the consensus-layer networking specification for Deneb.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Configuration](#configuration)
- [Containers](#containers)
  - [`BlobSidecar`](#blobsidecar)
  - [`SignedBlobSidecar`](#signedblobsidecar)
  - [`BlobIdentifier`](#blobidentifier)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`beacon_block`](#beacon_block)
      - [`blob_sidecar_{index}`](#blob_sidecar_index)
  - [Transitioning the gossip](#transitioning-the-gossip)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
    - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
    - [BlobSidecarsByRoot v1](#blobsidecarsbyroot-v1)
    - [BlobSidecarsByRange v1](#blobsidecarsbyrange-v1)
- [Design decision rationale](#design-decision-rationale)
  - [Why are blobs relayed as a sidecar, separate from beacon blocks?](#why-are-blobs-relayed-as-a-sidecar-separate-from-beacon-blocks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Configuration

| Name                                     | Value                             | Description                                                         |
|------------------------------------------|-----------------------------------|---------------------------------------------------------------------|
| `MAX_REQUEST_BLOCKS_DENEB`               | `2**7` (= 128)                    | Maximum number of blocks in a single request                        |
| `MAX_REQUEST_BLOB_SIDECARS`              | `MAX_REQUEST_BLOCKS_DENEB * MAX_BLOBS_PER_BLOCK`      | Maximum number of blob sidecars in a single request                 |
| `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` | `2**12` (= 4096 epochs, ~18 days) | The minimum epoch range over which a node must serve blob sidecars |

## Containers

### `BlobSidecar`

```python
class BlobSidecar(Container):
    block_root: Root
    index: BlobIndex  # Index of blob in block
    slot: Slot
    block_parent_root: Root  # Proposer shuffling determinant
    proposer_index: ValidatorIndex
    blob: Blob
    kzg_commitment: KZGCommitment
    kzg_proof: KZGProof  # Allows for quick verification of kzg_commitment
```

### `SignedBlobSidecar`

```python
class SignedBlobSidecar(Container):
    message: BlobSidecar
    signature: BLSSignature
```

### `BlobIdentifier`

```python
class BlobIdentifier(Container):
    block_root: Root
    index: BlobIndex
```

## The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of Deneb to support upgraded types.

### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is modified to also support deneb blocks and new topics are added per table below. All other topics remain stable.

The specification around the creation, validation, and dissemination of messages has not changed from the Capella document unless explicitly noted here.

The derivation of the `message-id` remains stable.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `blob_sidecar_{index}` | `SignedBlobSidecar` (new) |

#### Global topics

Deneb introduces new global topics for blob sidecars.

##### `beacon_block`

The *type* of the payload of this topic changes to the (modified) `SignedBeaconBlock` found in deneb.

##### `blob_sidecar_{index}`

This topic is used to propagate signed blob sidecars, one for each sidecar index. The number of indices is defined by `MAX_BLOBS_PER_BLOCK`.

The following validations MUST pass before forwarding the `sidecar` on the network, assuming the alias `sidecar = signed_blob_sidecar.message`:

- _[REJECT]_ The sidecar is for the correct topic -- i.e. `sidecar.index` matches the topic `{index}`.
- _[IGNORE]_ The sidecar is not from a future slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. validate that `sidecar.slot <= current_slot` (a client MAY queue future sidecars for processing at the appropriate slot).
- _[IGNORE]_ The sidecar is from a slot greater than the latest finalized slot -- i.e. validate that `sidecar.slot > compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)`
- _[IGNORE]_ The sidecar's block's parent (defined by `sidecar.block_parent_root`) has been seen (via both gossip and non-gossip sources) (a client MAY queue sidecars for processing once the parent block is retrieved).
- _[REJECT]_ The sidecar's block's parent (defined by `sidecar.block_parent_root`) passes validation.
- _[REJECT]_ The proposer signature, `signed_blob_sidecar.signature`, is valid with respect to the `sidecar.proposer_index` pubkey.
- _[IGNORE]_ The sidecar is the only sidecar with valid signature received for the tuple `(sidecar.block_root, sidecar.index)`.
- _[REJECT]_ The sidecar is proposed by the expected `proposer_index` for the block's slot in the context of the current shuffling (defined by `block_parent_root`/`slot`).
  If the `proposer_index` cannot immediately be verified against the expected shuffling, the sidecar MAY be queued for later processing while proposers for the block's branch are calculated -- in such a case _do not_ `REJECT`, instead `IGNORE` this message.


### Transitioning the gossip

See gossip transition details found in the [Altair document](../altair/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for this upgrade.

## The Req/Resp domain

### Messages

#### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The Deneb fork-digest is introduced to the `context` enum to specify Deneb beacon block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[0]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |

No more than `MAX_REQUEST_BLOCKS_DENEB` may be requested at a time.

#### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |

No more than `MAX_REQUEST_BLOCKS_DENEB` may be requested at a time.

#### BlobSidecarsByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/blob_sidecars_by_root/1/`

New in deneb.

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `DENEB_FORK_VERSION`     | `deneb.BlobSidecar`           |

Request Content:

```
(
  List[BlobIdentifier, MAX_REQUEST_BLOBS_SIDECARS]
)
```

Response Content:

```
(
  List[BlobSidecar, MAX_REQUEST_BLOBS_SIDECARS]
)
```

Requests sidecars by block root and index.
The response is a list of `BlobSidecar` whose length is less than or equal to the number of requests.
It may be less in the case that the responding peer is missing blocks or sidecars.

The response is unsigned, i.e. `BlobSidecar`, as the signature of the beacon block proposer
may not be available beyond the initial distribution via gossip.

No more than `MAX_REQUEST_BLOBS_SIDECARS` may be requested at a time.

`BlobSidecarsByRoot` is primarily used to recover recent blobs (e.g. when receiving a block with a transaction whose corresponding blob is missing).

The response MUST consist of zero or more `response_chunk`.
Each _successful_ `response_chunk` MUST contain a single `BlobSidecar` payload.

Clients MUST support requesting sidecars since `minimum_request_epoch`, where `minimum_request_epoch = max(finalized_epoch, current_epoch - MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS, DENEB_FORK_EPOCH)`. If any root in the request content references a block earlier than `minimum_request_epoch`, peers MAY respond with error code `3: ResourceUnavailable` or not include the blob in the response.

Clients MUST respond with at least one sidecar, if they have it.
Clients MAY limit the number of blocks and sidecars in the response.

#### BlobSidecarsByRange v1

**Protocol ID:** `/eth2/beacon_chain/req/blob_sidecars_by_range/1/`

New in deneb.

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `DENEB_FORK_VERSION`     | `deneb.BlobSidecar`           |

Request Content:
```
(
  start_slot: Slot
  count: uint64
)
```

Response Content:
```
(
  List[BlobSidecar, MAX_REQUEST_BLOB_SIDECARS]
)
```

Requests blob sidecars in the slot range `[start_slot, start_slot + count)`, leading up to the current head block as selected by fork choice.

The response is unsigned, i.e. `BlobSidecarsByRange`, as the signature of the beacon block proposer may not be available beyond the initial distribution via gossip.

Before consuming the next response chunk, the response reader SHOULD verify the blob sidecar is well-formatted and correct w.r.t. the expected KZG commitments through `validate_blobs`.

`BlobSidecarsByRange` is primarily used to sync blobs that may have been missed on gossip and to sync within the `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` window.

The request MUST be encoded as an SSZ-container.

The response MUST consist of zero or more `response_chunk`.
Each _successful_ `response_chunk` MUST contain a single `BlobSidecar` payload.

Clients MUST keep a record of signed blobs sidecars seen on the epoch range
`[max(current_epoch - MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS, DENEB_FORK_EPOCH), current_epoch]`
where `current_epoch` is defined by the current wall-clock time,
and clients MUST support serving requests of blobs on this range.

Peers that are unable to reply to blob sidecar requests within the `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS`
epoch range SHOULD respond with error code `3: ResourceUnavailable`.
Such peers that are unable to successfully reply to this range of requests MAY get descored
or disconnected at any time.

*Note*: The above requirement implies that nodes that start from a recent weak subjectivity checkpoint
MUST backfill the local blobs database to at least epoch `current_epoch - MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS`
to be fully compliant with `BlobSidecarsByRange` requests.

*Note*: Although clients that bootstrap from a weak subjectivity checkpoint can begin
participating in the networking immediately, other peers MAY
disconnect and/or temporarily ban such an un-synced or semi-synced client.

Clients MUST respond with at least the blob sidecars of the first blob-carrying block that exists in the range, if they have it, and no more than `MAX_REQUEST_BLOB_SIDECARS` sidecars.

Clients MUST include all blob sidecars of each block from which they include blob sidecars.

The following blob sidecars, where they exist, MUST be sent in consecutive `(slot, index)` order.

Clients MAY limit the number of blob sidecars in the response.

The response MUST contain no more than `count * MAX_BLOBS_PER_BLOCK` blob sidecars.

Clients MUST respond with blob sidecars from their view of the current fork choice
-- that is, blob sidecars as included by blocks from the single chain defined by the current head.
Of note, blocks from slots before the finalization MUST lead to the finalized block reported in the `Status` handshake.

Clients MUST respond with blob sidecars that are consistent from a single chain within the context of the request.

After the initial blob sidecar, clients MAY stop in the process of responding if their fork choice changes the view of the chain in the context of the request.

## Design decision rationale

### Why are blobs relayed as a sidecar, separate from beacon blocks?

This "sidecar" design provides forward compatibility for further data increases by black-boxing `is_data_available()`:
with full sharding `is_data_available()` can be replaced by data-availability-sampling (DAS)
thus avoiding all blobs being downloaded by all beacon nodes on the network.

Such sharding design may introduce an updated `BlobSidecar` to identify the shard,
but does not affect the `BeaconBlock` structure.
