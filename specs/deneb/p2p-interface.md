# Deneb -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Deneb](#modifications-in-deneb)
  - [Constant](#constant)
  - [Preset](#preset)
  - [Configuration](#configuration)
  - [Containers](#containers)
    - [`BlobSidecar`](#blobsidecar)
    - [`BlobIdentifier`](#blobidentifier)
    - [Helpers](#helpers)
      - [`verify_blob_sidecar_inclusion_proof`](#verify_blob_sidecar_inclusion_proof)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
        - [`beacon_aggregate_and_proof`](#beacon_aggregate_and_proof)
      - [Blob subnets](#blob-subnets)
        - [`blob_sidecar_{subnet_id}`](#blob_sidecar_subnet_id)
        - [Blob retrieval via local execution layer client](#blob-retrieval-via-local-execution-layer-client)
      - [Attestation subnets](#attestation-subnets)
        - [`beacon_attestation_{subnet_id}`](#beacon_attestation_subnet_id)
    - [Transitioning the gossip](#transitioning-the-gossip)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
      - [BlobSidecarsByRange v1](#blobsidecarsbyrange-v1)
      - [BlobSidecarsByRoot v1](#blobsidecarsbyroot-v1)
- [Design decision rationale](#design-decision-rationale)
  - [Why are blobs relayed as a sidecar, separate from beacon blocks?](#why-are-blobs-relayed-as-a-sidecar-separate-from-beacon-blocks)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specification for Deneb.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Modifications in Deneb

### Constant

*[New in Deneb:EIP4844]*

### Preset

*[New in Deneb:EIP4844]*

| Name                                   | Value                                                                                                                                     | Description                                                                 |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `KZG_COMMITMENT_INCLUSION_PROOF_DEPTH` | `uint64(floorlog2(get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments')) + 1 + ceillog2(MAX_BLOB_COMMITMENTS_PER_BLOCK))` (= 17) | <!-- predefined --> Merkle proof depth for `blob_kzg_commitments` list item |

### Configuration

*[New in Deneb:EIP4844]*

| Name                                    | Value                                            | Description                                                        |
| --------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------ |
| `MAX_REQUEST_BLOCKS_DENEB`              | `2**7` (= 128)                                   | Maximum number of blocks in a single request                       |
| `MAX_REQUEST_BLOB_SIDECARS`             | `MAX_REQUEST_BLOCKS_DENEB * MAX_BLOBS_PER_BLOCK` | Maximum number of blob sidecars in a single request                |
| `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` | `2**12` (= 4096 epochs, ~18 days)                | The minimum epoch range over which a node must serve blob sidecars |
| `BLOB_SIDECAR_SUBNET_COUNT`             | `6`                                              | The number of blob sidecar subnets used in the gossipsub protocol. |

### Containers

#### `BlobSidecar`

*[New in Deneb:EIP4844]*

```python
class BlobSidecar(Container):
    index: BlobIndex  # Index of blob in block
    blob: Blob
    kzg_commitment: KZGCommitment
    kzg_proof: KZGProof  # Allows for quick verification of kzg_commitment
    signed_block_header: SignedBeaconBlockHeader
    kzg_commitment_inclusion_proof: Vector[Bytes32, KZG_COMMITMENT_INCLUSION_PROOF_DEPTH]
```

#### `BlobIdentifier`

*[New in Deneb:EIP4844]*

```python
class BlobIdentifier(Container):
    block_root: Root
    index: BlobIndex
```

#### Helpers

##### `verify_blob_sidecar_inclusion_proof`

```python
def verify_blob_sidecar_inclusion_proof(blob_sidecar: BlobSidecar) -> bool:
    gindex = get_subtree_index(get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments', blob_sidecar.index))
    return is_valid_merkle_branch(
        leaf=blob_sidecar.kzg_commitment.hash_tree_root(),
        branch=blob_sidecar.kzg_commitment_inclusion_proof,
        depth=KZG_COMMITMENT_INCLUSION_PROOF_DEPTH,
        index=gindex,
        root=blob_sidecar.signed_block_header.message.body_root,
    )
```

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of Deneb to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is modified to also support Deneb blocks and new topics are added per table below.

The `voluntary_exit` topic is implicitly modified despite the lock-in use of `CAPELLA_FORK_VERSION` for this message signature validation for EIP-7044.

The `beacon_aggregate_and_proof` and `beacon_attestation_{subnet_id}` topics are modified to support the gossip of attestations created in epoch `N` to be gossiped through the entire range of slots in epoch `N+1` rather than only through one epoch of slots for EIP-7045.

The specification around the creation, validation, and dissemination of messages has not changed from the Capella document unless explicitly noted here.

The derivation of the `message-id` remains stable.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name                       | Message Type                         |
| -------------------------- | ------------------------------------ |
| `blob_sidecar_{subnet_id}` | `BlobSidecar` [New in Deneb:EIP4844] |

##### Global topics

###### `beacon_block`

The *type* of the payload of this topic changes to the (modified) `SignedBeaconBlock` found in Deneb.

*[Modified in Deneb:EIP4844]*

New validation:

- _[REJECT]_ The length of KZG commitments is less than or equal to the limitation defined in Consensus Layer --
  i.e. validate that `len(signed_beacon_block.message.body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK`

###### `beacon_aggregate_and_proof`

*[Modified in Deneb:EIP7045]*

The following validation is removed:

- _[IGNORE]_ `aggregate.data.slot` is within the last `ATTESTATION_PROPAGATION_SLOT_RANGE` slots (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `aggregate.data.slot + ATTESTATION_PROPAGATION_SLOT_RANGE >= current_slot >= aggregate.data.slot`
  (a client MAY queue future aggregates for processing at the appropriate slot).

The following validations are added in its place:

- _[IGNORE]_ `aggregate.data.slot` is equal to or earlier than the `current_slot` (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `aggregate.data.slot <= current_slot`
  (a client MAY queue future aggregates for processing at the appropriate slot).
- _[IGNORE]_ the epoch of `aggregate.data.slot` is either the current or previous epoch
  (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `compute_epoch_at_slot(aggregate.data.slot) in (get_previous_epoch(state), get_current_epoch(state))`

##### Blob subnets

###### `blob_sidecar_{subnet_id}`

*[New in Deneb:EIP4844]*

This topic is used to propagate blob sidecars, where each blob index maps to some `subnet_id`.

The following validations MUST pass before forwarding the `blob_sidecar` on the network, assuming the alias `block_header = blob_sidecar.signed_block_header.message`:

- _[REJECT]_ The sidecar's index is consistent with `MAX_BLOBS_PER_BLOCK` -- i.e. `blob_sidecar.index < MAX_BLOBS_PER_BLOCK`.
- _[REJECT]_ The sidecar is for the correct subnet -- i.e. `compute_subnet_for_blob_sidecar(blob_sidecar.index) == subnet_id`.
- _[IGNORE]_ The sidecar is not from a future slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. validate that `block_header.slot <= current_slot` (a client MAY queue future sidecars for processing at the appropriate slot).
- _[IGNORE]_ The sidecar is from a slot greater than the latest finalized slot -- i.e. validate that `block_header.slot > compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)`
- _[REJECT]_ The proposer signature of `blob_sidecar.signed_block_header`, is valid with respect to the `block_header.proposer_index` pubkey.
- _[IGNORE]_ The sidecar's block's parent (defined by `block_header.parent_root`) has been seen (via gossip or non-gossip sources) (a client MAY queue sidecars for processing once the parent block is retrieved).
- _[REJECT]_ The sidecar's block's parent (defined by `block_header.parent_root`) passes validation.
- _[REJECT]_ The sidecar is from a higher slot than the sidecar's block's parent (defined by `block_header.parent_root`).
- _[REJECT]_ The current finalized_checkpoint is an ancestor of the sidecar's block -- i.e. `get_checkpoint_block(store, block_header.parent_root, store.finalized_checkpoint.epoch) == store.finalized_checkpoint.root`.
- _[REJECT]_ The sidecar's inclusion proof is valid as verified by `verify_blob_sidecar_inclusion_proof(blob_sidecar)`.
- _[REJECT]_ The sidecar's blob is valid as verified by `verify_blob_kzg_proof(blob_sidecar.blob, blob_sidecar.kzg_commitment, blob_sidecar.kzg_proof)`.
- _[IGNORE]_ The sidecar is the first sidecar for the tuple `(block_header.slot, block_header.proposer_index, blob_sidecar.index)` with valid header signature, sidecar inclusion proof, and kzg proof.
- _[REJECT]_ The sidecar is proposed by the expected `proposer_index` for the block's slot in the context of the current shuffling (defined by `block_header.parent_root`/`block_header.slot`).
  If the `proposer_index` cannot immediately be verified against the expected shuffling, the sidecar MAY be queued for later processing while proposers for the block's branch are calculated -- in such a case _do not_ `REJECT`, instead `IGNORE` this message.

The gossip `ForkDigestValue` is determined based on `compute_fork_version(compute_epoch_at_slot(blob_sidecar.signed_block_header.message.slot))`.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`                 | Chunk SSZ type      |
| ------------------------------ | ------------------- |
| `DENEB_FORK_VERSION` and later | `deneb.BlobSidecar` |

###### Blob retrieval via local execution layer client

In addition to `BlobSidecarsByRoot` requests, recent blobs MAY be retrieved by querying the Execution Layer (i.e. via `engine_getBlobsV1`).
Honest nodes SHOULD query `engine_getBlobsV1` as soon as they receive a valid gossip block that contains data, and import the returned blobs.

When clients use the local execution layer to retrieve blobs, they MUST behave as if the corresponding `blob_sidecar` had been received via gossip. In particular they MUST:

- Publish the corresponding `blob_sidecar` on the `blob_sidecar_{subnet_id}` subnet.
- Update gossip rule related data structures (i.e. update the anti-equivocation cache).

##### Attestation subnets

###### `beacon_attestation_{subnet_id}`

*[Modified in Deneb:EIP7045]*

The following validation is removed:

- _[IGNORE]_ `attestation.data.slot` is within the last `ATTESTATION_PROPAGATION_SLOT_RANGE` slots (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `attestation.data.slot + ATTESTATION_PROPAGATION_SLOT_RANGE >= current_slot >= attestation.data.slot`
  (a client MAY queue future attestations for processing at the appropriate slot).

The following validations are added in its place:

- _[IGNORE]_ `attestation.data.slot` is equal to or earlier than the `current_slot` (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `attestation.data.slot <= current_slot`
  (a client MAY queue future attestation for processing at the appropriate slot).
- _[IGNORE]_ the epoch of `attestation.data.slot` is either the current or previous epoch
  (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `compute_epoch_at_slot(attestation.data.slot) in (get_previous_epoch(state), get_current_epoch(state))`

#### Transitioning the gossip

See gossip transition details found in the [Altair document](../altair/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for this upgrade.

### The Req/Resp domain

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The Deneb fork-digest is introduced to the `context` enum to specify Deneb beacon block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |

No more than `MAX_REQUEST_BLOCKS_DENEB` may be requested at a time.

##### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |

No more than `MAX_REQUEST_BLOCKS_DENEB` may be requested at a time.

*[Modified in Deneb:EIP4844]*
Clients SHOULD include a block in the response as soon as it passes the gossip validation rules.
Clients SHOULD NOT respond with blocks that fail the beacon chain state transition.

##### BlobSidecarsByRange v1

**Protocol ID:** `/eth2/beacon_chain/req/blob_sidecars_by_range/1/`

*[New in Deneb:EIP4844]*

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

Before consuming the next response chunk, the response reader SHOULD verify the blob sidecar is well-formatted, has valid inclusion proof, and is correct w.r.t. the expected KZG commitments through `verify_blob_kzg_proof`.

`BlobSidecarsByRange` is primarily used to sync blobs that may have been missed on gossip and to sync within the `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` window.

The request MUST be encoded as an SSZ-container.

The response MUST consist of zero or more `response_chunk`.
Each _successful_ `response_chunk` MUST contain a single `BlobSidecar` payload.

Let `blob_serve_range` be `[max(current_epoch - MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS, DENEB_FORK_EPOCH), current_epoch]`.
Clients MUST keep a record of blob sidecars seen on the epoch range `blob_serve_range`
where `current_epoch` is defined by the current wall-clock time,
and clients MUST support serving requests of blobs on this range.

Peers that are unable to reply to blob sidecar requests within the
range `blob_serve_range` SHOULD respond with error code `3: ResourceUnavailable`.
Such peers that are unable to successfully reply to this range of requests MAY get descored
or disconnected at any time.

*Note*: The above requirement implies that nodes that start from a recent weak subjectivity checkpoint
MUST backfill the local blobs database to at least the range `blob_serve_range`
to be fully compliant with `BlobSidecarsByRange` requests.

*Note*: Although clients that bootstrap from a weak subjectivity checkpoint can begin
participating in the networking immediately, other peers MAY
disconnect and/or temporarily ban such an un-synced or semi-synced client.

Clients MUST respond with at least the blob sidecars of the first blob-carrying block that exists in the range, if they have it, and no more than `MAX_REQUEST_BLOB_SIDECARS` sidecars.

Clients MUST include all blob sidecars of each block from which they include blob sidecars.

The following blob sidecars, where they exist, MUST be sent in consecutive `(slot, index)` order.

Slots that do not contain known blobs MUST be skipped, mimicking the behaviour
of the `BlocksByRange` request. Only response chunks with known blobs should
therefore be sent.

Clients MAY limit the number of blob sidecars in the response.

The response MUST contain no more than `count * MAX_BLOBS_PER_BLOCK` blob sidecars.

Clients MUST respond with blob sidecars from their view of the current fork choice
-- that is, blob sidecars as included by blocks from the single chain defined by the current head.
Of note, blocks from slots before the finalization MUST lead to the finalized block reported in the `Status` handshake.

Clients MUST respond with blob sidecars that are consistent from a single chain within the context of the request.

After the initial blob sidecar, clients MAY stop in the process of responding if their fork choice changes the view of the chain in the context of the request.

For each `response_chunk`, a `ForkDigest`-context based on `compute_fork_version(compute_epoch_at_slot(blob_sidecar.signed_block_header.message.slot))` is used to select the fork namespace of the Response type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`                 | Chunk SSZ type      |
| ------------------------------ | ------------------- |
| `DENEB_FORK_VERSION` and later | `deneb.BlobSidecar` |

##### BlobSidecarsByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/blob_sidecars_by_root/1/`

*[New in Deneb:EIP4844]*

Request Content:

```
(
  List[BlobIdentifier, MAX_REQUEST_BLOB_SIDECARS]
)
```

Response Content:

```
(
  List[BlobSidecar, MAX_REQUEST_BLOB_SIDECARS]
)
```

Requests sidecars by block root and index.
The response is a list of `BlobSidecar` whose length is less than or equal to the number of requests.
It may be less in the case that the responding peer is missing blocks or sidecars.

Before consuming the next response chunk, the response reader SHOULD verify the blob sidecar is well-formatted, has valid inclusion proof, and is correct w.r.t. the expected KZG commitments through `verify_blob_kzg_proof`.

No more than `MAX_REQUEST_BLOB_SIDECARS` may be requested at a time.

`BlobSidecarsByRoot` is primarily used to recover recent blobs (e.g. when receiving a block with a transaction whose corresponding blob is missing).

The response MUST consist of zero or more `response_chunk`.
Each _successful_ `response_chunk` MUST contain a single `BlobSidecar` payload.

Clients MUST support requesting sidecars since `minimum_request_epoch`, where `minimum_request_epoch = max(finalized_epoch, current_epoch - MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS, DENEB_FORK_EPOCH)`. If any root in the request content references a block earlier than `minimum_request_epoch`, peers MAY respond with error code `3: ResourceUnavailable` or not include the blob sidecar in the response.

Clients MUST respond with at least one sidecar, if they have it.
Clients MAY limit the number of blocks and sidecars in the response.

Clients SHOULD include a sidecar in the response as soon as it passes the gossip validation rules.
Clients SHOULD NOT respond with sidecars related to blocks that fail gossip validation rules.
Clients SHOULD NOT respond with sidecars related to blocks that fail the beacon chain state transition

For each `response_chunk`, a `ForkDigest`-context based on `compute_fork_version(compute_epoch_at_slot(blob_sidecar.signed_block_header.message.slot))` is used to select the fork namespace of the Response type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`                 | Chunk SSZ type      |
| ------------------------------ | ------------------- |
| `DENEB_FORK_VERSION` and later | `deneb.BlobSidecar` |

## Design decision rationale

### Why are blobs relayed as a sidecar, separate from beacon blocks?

This "sidecar" design provides forward compatibility for further data increases by black-boxing `is_data_available()`:
with full sharding `is_data_available()` can be replaced by data-availability-sampling (DAS)
thus avoiding all blobs being downloaded by all beacon nodes on the network.

Such sharding design may introduce an updated `BlobSidecar` to identify the shard,
but does not affect the `BeaconBlock` structure.
