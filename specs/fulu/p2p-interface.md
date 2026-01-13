# Fulu -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Fulu](#modifications-in-fulu)
  - [Preset](#preset)
  - [Configuration](#configuration)
  - [Containers](#containers)
    - [`DataColumnsByRootIdentifier`](#datacolumnsbyrootidentifier)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
    - [`verify_data_column_sidecar`](#verify_data_column_sidecar)
    - [`verify_data_column_sidecar_kzg_proofs`](#verify_data_column_sidecar_kzg_proofs)
    - [`verify_data_column_sidecar_inclusion_proof`](#verify_data_column_sidecar_inclusion_proof)
    - [`verify_partial_data_column_header_inclusion_proof`](#verify_partial_data_column_header_inclusion_proof)
    - [`verify_partial_data_column_sidecar_kzg_proofs`](#verify_partial_data_column_sidecar_kzg_proofs)
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
    - [Partial columns](#partial-columns)
      - [Partial message group ID](#partial-message-group-id)
      - [`PartialDataColumnSidecar`](#partialdatacolumnsidecar)
      - [`PartialDataColumnHeader`](#partialdatacolumnheader)
      - [Parts metadata](#parts-metadata)
      - [Encoding and decoding responses](#encoding-and-decoding-responses)
      - [Validation](#validation)
      - [Eager pushing](#eager-pushing)
      - [Interaction with standard gossipsub](#interaction-with-standard-gossipsub)
        - [Requesting partial messages](#requesting-partial-messages)
        - [Mesh](#mesh)
        - [Fanout](#fanout)
        - [Scoring](#scoring)
        - [Forwarding](#forwarding)
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
      - [`eth2` field](#eth2-field)
      - [Custody group count](#custody-group-count)
      - [Next fork digest](#next-fork-digest)
- [Peer Scoring](#peer-scoring)
- [Supernodes](#supernodes)

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

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
    if epoch >= DENEB_FORK_EPOCH:
        return DENEB_FORK_VERSION
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

#### `verify_data_column_sidecar`

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

    # Check that the sidecar respects the blob limit
    epoch = compute_epoch_at_slot(sidecar.signed_block_header.message.slot)
    if len(sidecar.kzg_commitments) > get_blob_parameters(epoch).max_blobs_per_block:
        return False

    # The column length must be equal to the number of commitments/proofs
    if len(sidecar.column) != len(sidecar.kzg_commitments) or len(sidecar.column) != len(
        sidecar.kzg_proofs
    ):
        return False

    return True
```

#### `verify_data_column_sidecar_kzg_proofs`

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

#### `verify_data_column_sidecar_inclusion_proof`

```python
def verify_data_column_sidecar_inclusion_proof(sidecar: DataColumnSidecar) -> bool:
    """
    Verify if the given KZG commitments included in the given beacon block.
    """
    return is_valid_merkle_branch(
        leaf=hash_tree_root(sidecar.kzg_commitments),
        branch=sidecar.kzg_commitments_inclusion_proof,
        depth=KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH,
        index=get_subtree_index(get_generalized_index(BeaconBlockBody, "blob_kzg_commitments")),
        root=sidecar.signed_block_header.message.body_root,
    )
```

#### `verify_partial_data_column_header_inclusion_proof`

```python
def verify_partial_data_column_header_inclusion_proof(header: PartialDataColumnHeader) -> bool:
    """
    Verify if the given KZG commitments are included in the given beacon block.
    """
    return is_valid_merkle_branch(
        leaf=hash_tree_root(header.kzg_commitments),
        branch=header.kzg_commitments_inclusion_proof,
        depth=KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH,
        index=get_subtree_index(get_generalized_index(BeaconBlockBody, "blob_kzg_commitments")),
        root=header.signed_block_header.message.body_root,
    )
```

#### `verify_partial_data_column_sidecar_kzg_proofs`

```python
def verify_partial_data_column_sidecar_kzg_proofs(
    sidecar: PartialDataColumnSidecar,
    all_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK],
    column_index: ColumnIndex,
) -> bool:
    """
    Verify the KZG proofs.
    """
    # Get the blob indices from the bitmap
    blob_indices = [i for i, b in enumerate(sidecar.cells_present_bitmap) if b]

    # The cell index is the column index for all cells in this column
    cell_indices = [CellIndex(column_index)] * len(blob_indices)

    # Batch verify that the cells match the corresponding commitments and proofs
    return verify_cell_kzg_proof_batch(
        commitments_bytes=[all_commitments[i] for i in blob_indices],
        cell_indices=cell_indices,
        cells=sidecar.partial_column,
        proofs_bytes=sidecar.kzg_proofs,
    )
```

#### `compute_subnet_for_data_column_sidecar`

```python
def compute_subnet_for_data_column_sidecar(column_index: ColumnIndex) -> SubnetID:
    return SubnetID(column_index % DATA_COLUMN_SIDECAR_SUBNET_COUNT)
```

### MetaData

The `MetaData` stored locally by clients is updated with an additional field to
communicate the custody group count.

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

#### Partial columns

Gossipsub's
[Partial Message Extension](https://github.com/libp2p/specs/pull/685) enables
exchanging selective parts of a message rather than the whole. The specification
here describes how consensus-layer clients use Partial Messages to disseminate
cells.

##### Partial message group ID

When sending a partial message, the gossipsub group ID MUST be the block root.

##### `PartialDataColumnSidecar`

The `PartialDataColumnSidecar` is similar to the `DataColumnSidecar` container,
except that only the cells and proofs identified by the bitmap are present.

*Note*: The column index is inferred from the gossipsub topic subnet.

```python
class PartialDataColumnSidecar(Container):
    cells_present_bitmap: Bitlist[MAX_BLOB_COMMITMENTS_PER_BLOCK]
    partial_column: List[Cell, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_proofs: List[KZGProof, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    # Optional header, only sent on eager pushes
    header: List[PartialDataColumnHeader, 1]
```

##### `PartialDataColumnHeader`

The `PartialDataColumnHeader` is the header that is common to all columns for a
given block. It lets a peer identify which blobs are included in a block, as
well as validating cells and proofs. This header is only sent on eager pushes
because a peer can only make a request after having the data in this header.
This header can be derived from a beacon block or a `DataColumnSidecar`.

```python
class PartialDataColumnHeader(Container):
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    signed_block_header: SignedBeaconBlockHeader
    kzg_commitments_inclusion_proof: Vector[Bytes32, KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH]
```

##### Parts metadata

Peers communicate the cells available with a bitmap. A set bit (`1`) at index
`i` means that the peer has the cell at index `i`. The bitmap is encoded as a
`Bitlist`.

##### Encoding and decoding responses

All responses MUST be encoded and decoded with the `PartialDataColumnSidecar`
container.

##### Validation

Validating partial messages happens in two parts. First, the
`PartialDataColumnHeader` needs to be validated, then the cell and proof data.

Once a `PartialDataColumnHeader` is validated for a corresponding block on any
subnet (gossipsub topic), it can be used for all subnets.

Due to the nature of partial messages, it is possible to get the
`PartialDataColumnHeader` with no cells, and get cells in a future response.

For all partial messages:

- _[IGNORE]_ If the received partial message contains only cell data, the node
  has seen the corresponding `PartialDataColumnHeader`.

For verifying the `PartialDataColumnHeader` in a partial message:

- _[IGNORE]_ The header is the first valid header for the given block root.
- _[REJECT]_ The header's `kzg_commitments` list is non-empty.
- _[IGNORE]_ The header is not from a future slot (with a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. validate that
  `block_header.slot <= current_slot` (a client MAY queue future headers for
  processing at the appropriate slot).
- _[IGNORE]_ The header is from a slot greater than the latest finalized slot --
  i.e. validate that
  `block_header.slot > compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)`
- _[REJECT]_ The proposer signature of `signed_block_header` is valid with
  respect to the `block_header.proposer_index` pubkey.
- _[IGNORE]_ The header's block's parent (defined by `block_header.parent_root`)
  has been seen (via gossip or non-gossip sources) (a client MAY queue header
  for processing once the parent block is retrieved).
- _[REJECT]_ The header's block's parent (defined by `block_header.parent_root`)
  passes validation.
- _[REJECT]_ The header is from a higher slot than the header's block's parent
  (defined by `block_header.parent_root`).
- _[REJECT]_ The current `finalized_checkpoint` is an ancestor of the header's
  block -- i.e.
  `get_checkpoint_block(store, block_header.parent_root, store.finalized_checkpoint.epoch) == store.finalized_checkpoint.root`.
- _[REJECT]_ The header's `kzg_commitments` field inclusion proof is valid as
  verified by `verify_partial_data_column_header_inclusion_proof`.
- _[REJECT]_ The header is proposed by the expected `proposer_index` for the
  block's slot in the context of the current shuffling (defined by
  `block_header.parent_root`/`block_header.slot`). If the `proposer_index`
  cannot immediately be verified against the expected shuffling, the header MAY
  be queued for later processing while proposers for the block's branch are
  calculated -- in such a case _do not_ `REJECT`, instead `IGNORE` this message.

For verifying the cells in a partial message:

- _[REJECT]_ The cells present bitmap length is equal to the number of KZG
  commitments in the `PartialDataColumnHeader`.
- _[REJECT]_ The sidecar's cell and proof data is valid as verified by
  `verify_partial_data_column_sidecar_kzg_proofs(sidecar, header.kzg_commitments, column_index)`.

##### Eager pushing

In contrast to standard gossipsub, a client explicitly requests missing parts
from a peer. A client can send its request before receiving a peer's parts
metadata. This registers interest in certain parts, even if the peer does not
have these parts yet.

This request can introduce extra latency compared to a peer unconditionally
pushing messages, especially in the first hop of dissemination.

To address this tradeoff, a client MAY choose to eagerly push some (or all) of
the cells it has. Clients SHOULD only do this when they are reasonably confident
that a peer does not have the provided cells. For example, a proposer including
private blobs SHOULD eagerly push the cells corresponding to the private blobs.

Clients SHOULD eagerly push the `PartialDataColumnHeader` to inform peers as to
which blobs are included in this block, and therefore which cells they are
missing. Clients SHOULD NOT send a `PartialDataColumnHeader` non-eagerly, as
this is wasted bandwidth.

Clients MAY choose to not eagerly push the `PartialDataColumnHeader` if it has
previously sent the header to the peer on another topic.

Clients SHOULD request cell data from peers after validating a
`PartialDataColumnHeader`, even if the corresponding block has not been seen
yet.

##### Interaction with standard gossipsub

###### Requesting partial messages

A peer requests partial messages for a topic by setting the `partial` field in
gossipsub's `SubOpts` RPC message to `true`.

###### Mesh

The Partial Message Extension uses the same mesh peers for a given topic as the
standard gossipsub topics for `DataColumnSidecar`s.

###### Fanout

The Partial Message Extension uses the same fanout peers for a given topic as
the standard gossipsub topics for `DataColumnSidecar`s.

###### Scoring

On receiving useful novel data from a peer, the client should report to
gossipsub a positive first message delivery.

On receiving invalid data, the client should report to gossipsub an invalid
message delivery.

###### Forwarding

Once clients can construct the full `DataColumnSidecar` after receiving missing
cells, they should forward the full `DataColumnSidecar` over standard gossipsub
to peers that do not support partial messages. This provides backwards
compatibility with nodes that do not yet support partial messages.

Avoid forwarding the full `DataColumnSidecar` message to peers that requested
partial messages for that given topic. It is purely redundant information.

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
  # [New in Fulu:EIP7594]
  earliest_available_slot: Slot
)
```

As seen by the client at the time of sending the message:

- `earliest_available_slot`: The slot of earliest available block
  (`SignedBeaconBlock`).

*Note*: According the the definition of `earliest_available_slot`:

- If the node is able to serve all blocks throughout the entire sidecars
  retention period (as defined by both `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS`
  and `MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS`), but is NOT able to serve
  all sidecars during this period, it should advertise the earliest slot from
  which it can serve all sidecars.
- If the node is able to serve all sidecars throughout the entire sidecars
  retention period (as defined by both `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS`
  and `MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS`), it should advertise the
  earliest slot from which it can serve all blocks.

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

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by
`compute_epoch_at_slot(data_column_sidecar.signed_block_header.message.slot)`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth2spec: skip -->

| `epoch`                     | Chunk SSZ type           |
| --------------------------- | ------------------------ |
| `FULU_FORK_EPOCH` and later | `fulu.DataColumnSidecar` |

##### DataColumnSidecarsByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/data_column_sidecars_by_root/1/`

*[New in Fulu:EIP7594]*

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
`minimum_request_epoch = max(current_epoch - MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS, FULU_FORK_EPOCH)`.
If any root in the request content references a block earlier than
`minimum_request_epoch`, peers MAY respond with error code
`3: ResourceUnavailable` or not include the data column sidecar in the response.

Clients MUST respond with at least one sidecar, if they have it. Clients MAY
limit the number of blocks and sidecars in the response.

Clients SHOULD include a sidecar in the response as soon as it passes the gossip
validation rules. Clients SHOULD NOT respond with sidecars related to blocks
that fail gossip validation rules. Clients SHOULD NOT respond with sidecars
related to blocks that fail the beacon chain state transition

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by
`compute_epoch_at_slot(data_column_sidecar.signed_block_header.message.slot)`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth2spec: skip -->

| `epoch`                     | Chunk SSZ type           |
| --------------------------- | ------------------------ |
| `FULU_FORK_EPOCH` and later | `fulu.DataColumnSidecar` |

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

##### `eth2` field

*[Modified in Fulu:EIP7892]*

*Note*: The structure of `ENRForkID` has not changed but the field value
computations have changed. Unless explicitly mentioned here, all specifications
from [phase0/p2p-interface.md#eth2-field](../phase0/p2p-interface.md#eth2-field)
carry over.

ENRs MUST carry a generic `eth2` key with an 16-byte value of the node's current
fork digest, next fork version, and next fork epoch to ensure connections are
made with peers on the intended Ethereum network.

| Key    | Value           |
| :----- | :-------------- |
| `eth2` | SSZ `ENRForkID` |

Specifically, the value of the `eth2` key MUST be the following SSZ encoded
object (`ENRForkID`):

```
(
  fork_digest: ForkDigest
  next_fork_version: Version
  next_fork_epoch: Epoch
)
```

The fields of `ENRForkID` are defined as:

- `fork_digest` is `compute_fork_digest(genesis_validators_root, epoch)` where:
  - `genesis_validators_root` is the static `Root` found in
    `state.genesis_validators_root`.
  - `epoch` is the node's current epoch defined by the wall-clock time (not
    necessarily the epoch to which the node is sync).
- `next_fork_version` is the fork version corresponding to the next planned fork
  at a future epoch. The fork version will only change for regular forks, _not
  BPO forks_. Note that it is possible for the blob schedule to define a change
  at the same epoch as a regular fork; this situation would be considered a
  regular fork. If no future fork is planned, set
  `next_fork_version = current_fork_version` to signal this fact.
- `next_fork_epoch` is the epoch at which the next fork (whether a regular fork
  _or a BPO fork_) is planned. If no future fork is planned, set
  `next_fork_epoch = FAR_FUTURE_EPOCH` to signal this fact.

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
regardless of whether it is a regular or a Blob-Parameters-Only fork. This new
entry MUST be added once `FULU_FORK_EPOCH` is assigned any value other than
`FAR_FUTURE_EPOCH`. Adding this entry prior to the Fulu fork will not impact
peering as nodes will ignore unknown ENR entries and `nfd` mismatches do not
cause disconnects.

If no next fork is scheduled, the `nfd` entry contains the default value for the
type (i.e., the SSZ representation of a zero-filled array).

| Key   | Value                   |
| :---- | :---------------------- |
| `nfd` | SSZ Bytes4 `ForkDigest` |

When discovering and interfacing with peers, nodes MUST evaluate `nfd` alongside
their existing consideration of the `ENRForkID::next_*` fields under the `eth2`
key, to form a more accurate view of the peer's intended next fork for the
purposes of sustained peering. If there is a mismatch, the node MUST NOT
disconnect before the fork boundary, but it MAY disconnect at/after the fork
boundary.

Nodes unprepared to follow the Fulu fork will be unaware of `nfd` entries.
However, their existing comparison of `eth2` entries (concretely
`next_fork_epoch`) is sufficient to detect upcoming divergence.

## Peer Scoring

Due to the deterministic custody functions, a node knows exactly what a peer
should be able to respond to. In the event that a peer does not respond to
samples of their custodied rows/columns, a node may downscore or disconnect from
a peer.

## Supernodes

A supernode is a node which subscribes to all data column sidecar subnets,
custodies all data column sidecars, and performs
[reconstruction and cross-seeding](./das-core.md#reconstruction-and-cross-seeding).
Being a supernode requires considerably higher bandwidth, storage, and
computation resources. In order to reconstruct missing data, there must be at
least one supernode on the network. Due to
[validator custody requirements](./validator.md#validator-custody), a node which
is connected to validator(s) with a combined balance greater than or equal to
4096 ETH must be a supernode. Moreover, any node with the necessary resources
may altruistically be a supernode. Therefore, there are expected to be many
(hundreds) of supernodes on mainnet and it is likely (though not necessary) for
a node to be connected to several of these by chance.
