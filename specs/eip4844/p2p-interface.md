# EIP-4844 -- Networking

This document contains the consensus-layer networking specification for EIP-4844.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

  - [Configuration](#configuration)
  - [Containers](#containers)
    - [`BlobsSidecar`](#blobssidecar)
    - [`SignedBlobsSidecar`](#signedblobssidecar)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
        - [`blobs_sidecar`](#blobs_sidecar)
    - [Transitioning the gossip](#transitioning-the-gossip)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
      - [BlobsSidecarsByRange v1](#blobssidecarsbyrange-v1)
- [Design decision rationale](#design-decision-rationale)
  - [Why are blobs relayed as a sidecar, separate from beacon blocks?](#why-are-blobs-relayed-as-a-sidecar-separate-from-beacon-blocks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Configuration

| Name                                     | Value                         | Description                                                         |
|------------------------------------------|-------------------------------|---------------------------------------------------------------------|
| `MAX_REQUEST_BLOBS_SIDECARS`             | `2**7` (= 128)                | Maximum number of blobs sidecars in a single request                |
| `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS` | `2**13` (= 8192, ~1.2 months) | The minimum epoch range over which a node must serve blobs sidecars |

## Containers

### `BlobsSidecar`

```python
class BlobsSidecar(Container):
    beacon_block_root: Root
    beacon_block_slot: Slot
    blobs: List[Blob, MAX_BLOBS_PER_BLOCK]
    kzg_aggregated_proof: KZGProof
```

### `SignedBlobsSidecar`

```python
class SignedBlobsSidecar(Container):
    message: BlobsSidecar
    signature: BLSSignature
```

## The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of EIP4844 to support upgraded types.

### Topics and messages

Topics follow the same specification as in prior upgrades.
All topics remain stable except the beacon block topic which is updated with the modified type.

The specification around the creation, validation, and dissemination of messages has not changed from the Bellatrix document unless explicitly noted here.

The derivation of the `message-id` remains stable.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `beacon_block` | `SignedBeaconBlock` (modified) |
| `blobs_sidecar` | `SignedBlobsSidecar` (new) |

Note that the `ForkDigestValue` path segment of the topic separates the old and the new `beacon_block` topics.

#### Global topics

EIP4844 changes the type of the global beacon block topic and introduces a new global topic for blobs-sidecars.

##### `beacon_block`

The *type* of the payload of this topic changes to the (modified) `SignedBeaconBlock` found in EIP4844.

In addition to the gossip validations for this topic from prior specifications,
the following validations MUST pass before forwarding the `signed_beacon_block` on the network.
Alias `block = signed_beacon_block.message`, `execution_payload = block.body.execution_payload`.
- _[REJECT]_ The KZG commitments of the blobs are all correctly encoded compressed BLS G1 Points.
  -- i.e. `all(bls.KeyValidate(commitment) for commitment in block.body.blob_kzg_commitments)`
- _[REJECT]_ The KZG commitments correspond to the versioned hashes in the transactions list.
  -- i.e. `verify_kzg_commitments_against_transactions(block.body.execution_payload.transactions, block.body.blob_kzg_commitments)`

##### `blobs_sidecar`

This topic is used to propagate data blobs included in any given beacon block.

The following validations MUST pass before forwarding the `signed_blobs_sidecar` on the network;
Alias `sidecar = signed_blobs_sidecar.message`.
- _[IGNORE]_ the `sidecar.beacon_block_slot` is for the current slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. `sidecar.beacon_block_slot == current_slot`.
- _[REJECT]_ the `sidecar.blobs` are all well formatted, i.e. the `BLSFieldElement` in valid range (`x < BLS_MODULUS`).
- _[REJECT]_ The KZG proof is a correctly encoded compressed BLS G1 Point -- i.e. `bls.KeyValidate(blobs_sidecar.kzg_aggregated_proof)`
- _[REJECT]_ the beacon proposer signature, `signed_blobs_sidecar.signature`, is valid -- i.e.
    - Let `domain = get_domain(state, DOMAIN_BLOBS_SIDECAR, sidecar.beacon_block_slot // SLOTS_PER_EPOCH)`
    - Let `signing_root = compute_signing_root(sidecar, domain)`
    - Verify `bls.Verify(proposer_pubkey, signing_root, signed_blob_header.signature) is True`,   
      where `proposer_pubkey` is the pubkey of the beacon block proposer of `sidecar.beacon_block_slot`
- _[IGNORE]_ The sidecar is the first sidecar with valid signature received for the `(proposer_index, sidecar.beacon_block_slot)` combination,
  where `proposer_index` is the validator index of the beacon block proposer of `sidecar.beacon_block_slot`

Note that a sidecar may be propagated before or after the corresponding beacon block.

Once both sidecar and beacon block are received, `validate_blobs_sidecar` can unlock the data-availability fork-choice dependency.

### Transitioning the gossip

See gossip transition details found in the [Altair document](../altair/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for this upgrade.

## The Req/Resp domain

### Messages

#### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The EIP-4844 fork-digest is introduced to the `context` enum to specify EIP-4844 beacon block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[0]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `EIP4844_FORK_VERSION`   | `eip4844.SignedBeaconBlock`   |

#### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

The EIP-4844 fork-digest is introduced to the `context` enum to specify EIP-4844 beacon block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type             |
| ------------------------ | -------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock` |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `EIP4844_FORK_VERSION`   | `eip4844.SignedBeaconBlock`   |

#### BlobsSidecarsByRange v1

**Protocol ID:** `/eth2/beacon_chain/req/blobs_sidecars_by_range/1/`

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
  List[BlobsSidecar, MAX_REQUEST_BLOBS_SIDECARS]
)
```

Requests blobs sidecars in the slot range `[start_slot, start_slot + count)`,
leading up to the current head block as selected by fork choice.

The response is unsigned, i.e. `BlobsSidecarsByRange`, as the signature of the beacon block proposer
may not be available beyond the initial distribution via gossip.

Before consuming the next response chunk, the response reader SHOULD verify the blobs sidecar is well-formatted and
correct w.r.t. the expected KZG commitments through `validate_blobs_sidecar`.

`BlobsSidecarsByRange` is primarily used to sync blobs that may have been missed on gossip.

The request MUST be encoded as an SSZ-container.

The response MUST consist of zero or more `response_chunk`.
Each _successful_ `response_chunk` MUST contain a single `BlobsSidecar` payload.

Clients MUST keep a record of signed blobs sidecars seen on the epoch range
`[max(GENESIS_EPOCH, current_epoch - MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS), current_epoch]`
where `current_epoch` is defined by the current wall-clock time,
and clients MUST support serving requests of blocks on this range.

Peers that are unable to reply to block requests within the `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS`
epoch range SHOULD respond with error code `3: ResourceUnavailable`.
Such peers that are unable to successfully reply to this range of requests MAY get descored
or disconnected at any time.

*Note*: The above requirement implies that nodes that start from a recent weak subjectivity checkpoint
MUST backfill the local blobs database to at least epoch `current_epoch - MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS`
to be fully compliant with `BlobsSidecarsByRange` requests. To safely perform such a
backfill of blocks to the recent state, the node MUST validate both (1) the
proposer signatures and (2) that the blocks form a valid chain up to the most
recent block referenced in the weak subjectivity state.

*Note*: Although clients that bootstrap from a weak subjectivity checkpoint can begin
participating in the networking immediately, other peers MAY
disconnect and/or temporarily ban such an un-synced or semi-synced client.

Clients MUST respond with at least the first blobs sidecar that exists in the range, if they have it,
and no more than `MAX_REQUEST_BLOBS_SIDECARS` sidecars.

The following blobs sidecars, where they exist, MUST be sent in consecutive order.

Clients MAY limit the number of blobs sidecars in the response.

The response MUST contain no more than `count` blobs sidecars.

Clients MUST respond with blobs sidecars from their view of the current fork choice
-- that is, blobs sidecars as included by blocks from the single chain defined by the current head.
Of note, blocks from slots before the finalization MUST lead to the finalized block reported in the `Status` handshake.

Clients MUST respond with blobs sidecars that are consistent from a single chain within the context of the request.

After the initial blobs sidecar, clients MAY stop in the process of responding
if their fork choice changes the view of the chain in the context of the request.

# Design decision rationale

## Why are blobs relayed as a sidecar, separate from beacon blocks?

This "sidecar" design provides forward compatibility for further data increases by black-boxing `is_data_available()`:
with full sharding `is_data_available()` can be replaced by data-availability-sampling (DAS)
thus avoiding all blobs being downloaded by all beacon nodes on the network.

Such sharding design may introduce an updated `BlobsSidecar` to identify the shard,
but does not affect the `BeaconBlock` structure.
