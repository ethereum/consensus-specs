# Fulu -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Fulu](#modifications-in-fulu)
  - [Preset](#preset)
  - [Configuration](#configuration)
  - [Containers](#containers)
    - [`DataColumnsByRootIdentifier`](#datacolumnsbyrootidentifier)
  - [Helpers](#helpers)
    - [`verify_data_column_sidecar`](#verify_data_column_sidecar)
    - [`verify_data_column_sidecar_kzg_proofs`](#verify_data_column_sidecar_kzg_proofs)
    - [`verify_data_column_sidecar_inclusion_proof`](#verify_data_column_sidecar_inclusion_proof)
    - [`compute_subnet_for_data_column_sidecar`](#compute_subnet_for_data_column_sidecar)
  - [MetaData](#metadata)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
      - [Blob subnets](#blob-subnets)
        - [Deprecated `blob_sidecar_{subnet_id}`](#deprecated-blob_sidecar_subnet_id)
        - [`data_column_sidecar_{subnet_id}`](#data_column_sidecar_subnet_id)
        - [Distributed Blob Publishing using blobs retrieved from local execution layer client](#distributed-blob-publishing-using-blobs-retrieved-from-local-execution-layer-client)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [Status v2](#status-v2)
      - [BlobSidecarsByRange v1](#blobsidecarsbyrange-v1)
      - [BlobSidecarsByRoot v1](#blobsidecarsbyroot-v1)
      - [DataColumnSidecarsByRange v1](#datacolumnsidecarsbyrange-v1)
      - [DataColumnSidecarsByRoot v1](#datacolumnsidecarsbyroot-v1)
      - [GetMetaData v3](#getmetadata-v3)
  - [The discovery domain: discv5](#the-discovery-domain-discv5)
    - [ENR structure](#enr-structure)
      - [Custody group count](#custody-group-count)
      - [Next fork digest](#next-fork-digest)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specification for Fulu.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modifications in Fulu

### Preset

| Name                                    | Value                                                                                     | Description                                                       |
| --------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH` | `uint64(floorlog2(get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments')))` (= 4) | <!-- predefined --> Merkle proof index for `blob_kzg_commitments` |

### Configuration

*[New in Fulu:EIP7594]*

| Name                                           | Value                                          | Description                                                               |
| ---------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------- |
| `DATA_COLUMN_SIDECAR_SUBNET_COUNT`             | `128`                                          | The number of data column sidecar subnets used in the gossipsub protocol  |
| `MAX_REQUEST_DATA_COLUMN_SIDECARS`             | `MAX_REQUEST_BLOCKS_DENEB * NUMBER_OF_COLUMNS` | Maximum number of data column sidecars in a single request                |
| `MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` | `2**12` (= 4096 epochs, ~18 days)              | The minimum epoch range over which a node must serve data column sidecars |

### Containers

#### `DataColumnsByRootIdentifier`

```python
class DataColumnsByRootIdentifier(Container):
    block_root: Root
    columns: List[ColumnIndex, NUMBER_OF_COLUMNS]
```

### Helpers

##### `verify_data_column_sidecar`

```python
def verify_data_column_sidecar(sidecar: DataColumnSidecar) -> bool:
    """
    Verify if the data column sidecar is valid.
    """
    # The sidecar index must be within the valid range
    if sidecar.index >= NUMBER_OF_COLUMNS:
        return False

    # A sidecar for zero blobs is invalid
    if len(sidecar.kzg_commitments) == 0:
        return False

    # The column length must be equal to the number of commitments/proofs
    if len(sidecar.column) != len(sidecar.kzg_commitments) or len(sidecar.column) != len(
        sidecar.kzg_proofs
    ):
        return False

    return True
```

##### `verify_data_column_sidecar_kzg_proofs`

```python
def verify_data_column_sidecar_kzg_proofs(sidecar: DataColumnSidecar) -> bool:
    """
    Verify if the KZG proofs are correct.
    """
    # The column index also represents the cell index
    cell_indices = [CellIndex(sidecar.index)] * len(sidecar.column)

    # Batch verify that the cells match the corresponding commitments and proofs
    return verify_cell_kzg_proof_batch(
        commitments_bytes=sidecar.kzg_commitments,
        cell_indices=cell_indices,
        cells=sidecar.column,
        proofs_bytes=sidecar.kzg_proofs,
    )
```

##### `verify_data_column_sidecar_inclusion_proof`

```python
def verify_data_column_sidecar_inclusion_proof(sidecar: DataColumnSidecar) -> bool:
    """
    Verify if the given KZG commitments included in the given beacon block.
    """
    gindex = get_subtree_index(get_generalized_index(BeaconBlockBody, "blob_kzg_commitments"))
    return is_valid_merkle_branch(
        leaf=hash_tree_root(sidecar.kzg_commitments),
        branch=sidecar.kzg_commitments_inclusion_proof,
        depth=KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH,
        index=gindex,
        root=sidecar.signed_block_header.message.body_root,
    )
```

##### `compute_subnet_for_data_column_sidecar`

```python
def compute_subnet_for_data_column_sidecar(column_index: ColumnIndex) -> SubnetID:
    return SubnetID(column_index % DATA_COLUMN_SIDECAR_SUBNET_COUNT)
```

### MetaData

The `MetaData` stored locally by clients is updated with an additional field to
communicate the custody subnet count.

```
(
  seq_number: uint64
  attnets: Bitvector[ATTESTATION_SUBNET_COUNT]
  syncnets: Bitvector[SYNC_COMMITTEE_SUBNET_COUNT]
  custody_group_count: uint64 # cgc
)
```

Where

- `seq_number`, `attnets`, and `syncnets` have the same meaning defined in the
  Altair document.
- `custody_group_count` represents the node's custody group count. Clients MAY
  reject peers with a value less than `CUSTODY_REQUIREMENT`.

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the Fulu fork to support upgraded types.

#### Topics and messages

##### Global topics

###### `beacon_block`

*Updated validation*

- _[REJECT]_ The length of KZG commitments is less than or equal to the
  limitation defined in Consensus Layer -- i.e. validate that
  `len(signed_beacon_block.message.body.blob_kzg_commitments) <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block`

##### Blob subnets

###### Deprecated `blob_sidecar_{subnet_id}`

`blob_sidecar_{subnet_id}` is deprecated.

###### `data_column_sidecar_{subnet_id}`

This topic is used to propagate column sidecars, where each column maps to some
`subnet_id`.

The *type* of the payload of this topic is `DataColumnSidecar`.

The following validations MUST pass before forwarding the
`sidecar: DataColumnSidecar` on the network, assuming the alias
`block_header = sidecar.signed_block_header.message`:

- _[REJECT]_ The sidecar is valid as verified by
  `verify_data_column_sidecar(sidecar)`.
- _[REJECT]_ The sidecar is for the correct subnet -- i.e.
  `compute_subnet_for_data_column_sidecar(sidecar.index) == subnet_id`.
- _[IGNORE]_ The sidecar is not from a future slot (with a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. validate that
  `block_header.slot <= current_slot` (a client MAY queue future sidecars for
  processing at the appropriate slot).
- _[IGNORE]_ The sidecar is from a slot greater than the latest finalized slot
  -- i.e. validate that
  `block_header.slot > compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)`
- _[REJECT]_ The proposer signature of `sidecar.signed_block_header`, is valid
  with respect to the `block_header.proposer_index` pubkey.
- _[IGNORE]_ The sidecar's block's parent (defined by
  `block_header.parent_root`) has been seen (via gossip or non-gossip sources)
  (a client MAY queue sidecars for processing once the parent block is
  retrieved).
- _[REJECT]_ The sidecar's block's parent (defined by
  `block_header.parent_root`) passes validation.
- _[REJECT]_ The sidecar is from a higher slot than the sidecar's block's parent
  (defined by `block_header.parent_root`).
- _[REJECT]_ The current finalized_checkpoint is an ancestor of the sidecar's
  block -- i.e.
  `get_checkpoint_block(store, block_header.parent_root, store.finalized_checkpoint.epoch) == store.finalized_checkpoint.root`.
- _[REJECT]_ The sidecar's `kzg_commitments` field inclusion proof is valid as
  verified by `verify_data_column_sidecar_inclusion_proof(sidecar)`.
- _[REJECT]_ The sidecar's column data is valid as verified by
  `verify_data_column_sidecar_kzg_proofs(sidecar)`.
- _[IGNORE]_ The sidecar is the first sidecar for the tuple
  `(block_header.slot, block_header.proposer_index, sidecar.index)` with valid
  header signature, sidecar inclusion proof, and kzg proof.
- _[REJECT]_ The sidecar is proposed by the expected `proposer_index` for the
  block's slot in the context of the current shuffling (defined by
  `block_header.parent_root`/`block_header.slot`). If the `proposer_index`
  cannot immediately be verified against the expected shuffling, the sidecar MAY
  be queued for later processing while proposers for the block's branch are
  calculated -- in such a case _do not_ `REJECT`, instead `IGNORE` this message.

*Note*: In the `verify_data_column_sidecar_inclusion_proof(sidecar)` check, for
all the sidecars of the same block, it verifies against the same set of
`kzg_commitments` of the given beacon block. Client can choose to cache the
result of the arguments tuple
`(sidecar.kzg_commitments, sidecar.kzg_commitments_inclusion_proof, sidecar.signed_block_header)`.

###### Distributed Blob Publishing using blobs retrieved from local execution layer client

Honest nodes SHOULD query `engine_getBlobsV2` as soon as they receive a valid
`beacon_block` or `data_column_sidecar` from gossip. If ALL blobs matching
`kzg_commitments` are retrieved, they should convert the response to data
columns, and import the result.

Implementers are encouraged to leverage this method to increase the likelihood
of incorporating and attesting to the last block when its proposer is not able
to publish data columns on time.

When clients use the local execution layer to retrieve blobs, they SHOULD skip
verification of those blobs. When subsequently importing the blobs as data
columns, they MUST behave as if the `data_column_sidecar` had been received via
gossip. In particular, clients MUST:

- Publish the corresponding `data_column_sidecar` on the
  `data_column_sidecar_{subnet_id}` topic **if and only if** they are
  **subscribed** to it, either due to custody requirements or additional
  sampling.
- Update gossip rule related data structures (i.e. update the anti-equivocation
  cache).

### The Req/Resp domain

#### Messages

##### Status v2

**Protocol ID:** `/eth2/beacon_chain/req/status/2/`

Request, Response Content:

```
(
  fork_digest: ForkDigest
  finalized_root: Root
  finalized_epoch: Epoch
  head_root: Root
  head_slot: Slot
  earliest_available_slot: Slot  # [New in Fulu:EIP7594]
)
```

The added fields are, as seen by the client at the time of sending the message:

- `earliest_available_slot`: The slot of earliest available block
  (`BeaconBlock`).

##### BlobSidecarsByRange v1

**Protocol ID:** `/eth2/beacon_chain/req/blob_sidecars_by_range/1/`

Deprecated as of `FULU_FORK_EPOCH + MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS`.

During the deprecation transition period:

- Clients MUST respond with a list of blob sidecars from the range
  `[min(current_epoch - MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS, FULU_FORK_EPOCH), FULU_FORK_EPOCH)`
  if the requested range includes any epochs in this interval.
- Clients MAY respond with an empty list if the requested range lies entirely at
  or after `FULU_FORK_EPOCH`.
- Clients SHOULD NOT penalize peers for requesting blob sidecars from
  `FULU_FORK_EPOCH`.

##### BlobSidecarsByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/blob_sidecars_by_root/1/`

Deprecated as of `FULU_FORK_EPOCH + MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS`.

During the deprecation transition period:

- Clients MUST respond with blob sidecars corresponding to block roots from the
  range
  `[min(current_epoch - MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS, FULU_FORK_EPOCH), FULU_FORK_EPOCH)`
  if any of the requested roots correspond to blocks in this interval.
- Clients MAY respond with an empty list if all requested roots correspond to
  blocks at or after `FULU_FORK_EPOCH`.
- Clients SHOULD NOT penalize peers for requesting blob sidecars from
  `FULU_FORK_EPOCH`.

##### DataColumnSidecarsByRange v1

**Protocol ID:** `/eth2/beacon_chain/req/data_column_sidecars_by_range/1/`

The `<context-bytes>` field is calculated as
`context = compute_fork_digest(genesis_validators_root, epoch)`:

<!-- eth2spec: skip -->

| `epoch`              | Chunk SSZ type           |
| -------------------- | ------------------------ |
| >= `FULU_FORK_EPOCH` | `fulu.DataColumnSidecar` |

Request Content:

```
(
  start_slot: Slot
  count: uint64
  columns: List[ColumnIndex, NUMBER_OF_COLUMNS]
)
```

Response Content:

```
(
  List[DataColumnSidecar, MAX_REQUEST_DATA_COLUMN_SIDECARS]
)
```

Requests data column sidecars in the slot range
`[start_slot, start_slot + count)` of the given `columns`, leading up to the
current head block as selected by fork choice.

Before consuming the next response chunk, the response reader SHOULD verify the
data column sidecar is well-formatted through `verify_data_column_sidecar`, has
valid inclusion proof through `verify_data_column_sidecar_inclusion_proof`, and
is correct w.r.t. the expected KZG commitments through
`verify_data_column_sidecar_kzg_proofs`.

`DataColumnSidecarsByRange` is primarily used to sync data columns that may have
been missed on gossip and to sync within the
`MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` window.

The request MUST be encoded as an SSZ-container.

The response MUST consist of zero or more `response_chunk`. Each _successful_
`response_chunk` MUST contain a single `DataColumnSidecar` payload.

Let `data_column_serve_range` be
`[max(current_epoch - MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS, FULU_FORK_EPOCH), current_epoch]`.
Clients MUST keep a record of data column sidecars seen on the epoch range
`data_column_serve_range` where `current_epoch` is defined by the current
wall-clock time, and clients MUST support serving requests of data columns on
this range.

Peers that are unable to reply to data column sidecar requests within the range
`data_column_serve_range` SHOULD respond with error code
`3: ResourceUnavailable`. Such peers that are unable to successfully reply to
this range of requests MAY get descored or disconnected at any time.

*Note*: The above requirement implies that nodes that start from a recent weak
subjectivity checkpoint MUST backfill the local data columns database to at
least the range `data_column_serve_range` to be fully compliant with
`DataColumnSidecarsByRange` requests.

*Note*: Although clients that bootstrap from a weak subjectivity checkpoint can
begin participating in the networking immediately, other peers MAY disconnect
and/or temporarily ban such an un-synced or semi-synced client.

Clients MUST respond with at least the data column sidecars of the first
blob-carrying block that exists in the range, if they have it, and no more than
`MAX_REQUEST_DATA_COLUMN_SIDECARS` sidecars.

Clients MUST include all data column sidecars of each block from which they
include data column sidecars.

The following data column sidecars, where they exist, MUST be sent in
`(slot, column_index)` order.

Slots that do not contain known data columns MUST be skipped, mimicking the
behaviour of the `BlocksByRange` request. Only response chunks with known data
columns should therefore be sent.

Clients MAY limit the number of data column sidecars in the response.

The response MUST contain no more than `count * NUMBER_OF_COLUMNS` data column
sidecars.

Clients MUST respond with data columns sidecars from their view of the current
fork choice -- that is, data column sidecars as included by blocks from the
single chain defined by the current head. Of note, blocks from slots before the
finalization MUST lead to the finalized block reported in the `Status`
handshake.

Clients MUST respond with data column sidecars that are consistent from a single
chain within the context of the request.

After the initial data column sidecar, clients MAY stop in the process of
responding if their fork choice changes the view of the chain in the context of
the request.

##### DataColumnSidecarsByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/data_column_sidecars_by_root/1/`

*[New in Fulu:EIP7594]*

The `<context-bytes>` field is calculated as
`context = compute_fork_digest(genesis_validators_root, epoch)`:

<!-- eth2spec: skip -->

| `epoch`              | Chunk SSZ type           |
| -------------------- | ------------------------ |
| >= `FULU_FORK_EPOCH` | `fulu.DataColumnSidecar` |

Request Content:

```
(
  List[DataColumnsByRootIdentifier, MAX_REQUEST_BLOCKS_DENEB]
)
```

Response Content:

```
(
  List[DataColumnSidecar, MAX_REQUEST_DATA_COLUMN_SIDECARS]
)
```

Requests data column sidecars by block root and column indices. The response is
a list of `DataColumnSidecar` whose length is less than or equal to
`requested_columns_count`, where
`requested_columns_count = sum(len(r.columns) for r in request)`. It may be less
in the case that the responding peer is missing blocks or sidecars.

Before consuming the next response chunk, the response reader SHOULD verify the
data column sidecar is well-formatted through `verify_data_column_sidecar`, has
valid inclusion proof through `verify_data_column_sidecar_inclusion_proof`, and
is correct w.r.t. the expected KZG commitments through
`verify_data_column_sidecar_kzg_proofs`.

No more than `MAX_REQUEST_DATA_COLUMN_SIDECARS` may be requested at a time.

The response MUST consist of zero or more `response_chunk`. Each _successful_
`response_chunk` MUST contain a single `DataColumnSidecar` payload.

Clients MUST support requesting sidecars since `minimum_request_epoch`, where
`minimum_request_epoch = max(finalized_epoch, current_epoch - MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS, FULU_FORK_EPOCH)`.
If any root in the request content references a block earlier than
`minimum_request_epoch`, peers MAY respond with error code
`3: ResourceUnavailable` or not include the data column sidecar in the response.

Clients MUST respond with at least one sidecar, if they have it. Clients MAY
limit the number of blocks and sidecars in the response.

Clients SHOULD include a sidecar in the response as soon as it passes the gossip
validation rules. Clients SHOULD NOT respond with sidecars related to blocks
that fail gossip validation rules. Clients SHOULD NOT respond with sidecars
related to blocks that fail the beacon chain state transition

##### GetMetaData v3

**Protocol ID:** `/eth2/beacon_chain/req/metadata/3/`

No Request Content.

Response Content:

```
(
  MetaData
)
```

Requests the MetaData of a peer, using the new `MetaData` definition given above
that is extended from Altair. Other conditions for the `GetMetaData` protocol
are unchanged from the Altair p2p networking document.

### The discovery domain: discv5

#### ENR structure

##### Custody group count

A new field is added to the ENR under the key `cgc` to facilitate custody data
column discovery. This new field MUST be added once `FULU_FORK_EPOCH` is
assigned any value other than `FAR_FUTURE_EPOCH`.

| Key   | Value                                                                                                             |
| ----- | ----------------------------------------------------------------------------------------------------------------- |
| `cgc` | Custody group count, `uint64` big endian integer with no leading zero bytes (`0` is encoded as empty byte string) |

##### Next fork digest

A new entry is added to the ENR under the key `nfd`, short for _next fork
digest_. This entry communicates the digest of the next scheduled fork,
regardless of whether it is a regular or a Blob-Parameters-Only fork.

If no next fork is scheduled, the `nfd` entry contains the default value for the
type (i.e., the SSZ representation of a zero-filled array).

| Key   | Value                   |
| :---- | :---------------------- |
| `nfd` | SSZ Bytes4 `ForkDigest` |

Furthermore, the existing `next_fork_epoch` field under the `eth2` entry MUST be
set to the epoch of the next fork, whether a regular fork, _or a BPO fork_.

When discovering and interfacing with peers, nodes MUST evaluate `nfd` alongside
their existing consideration of the `ENRForkID::next_*` fields under the `eth2`
key, to form a more accurate view of the peer's intended next fork for the
purposes of sustained peering. A mismatch indicates that the node MAY disconnect
from such peers at the fork boundary, but not sooner.

Nodes unprepared to follow the Fulu fork will be unaware of `nfd` entries.
However, their existing comparison of `eth2` entries (concretely
`next_fork_epoch`) is sufficient to detect upcoming divergence.
