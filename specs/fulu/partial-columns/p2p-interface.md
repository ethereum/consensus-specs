# Fulu Partial Columns -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Containers](#containers)
  - [`PartialDataColumnSidecar`](#partialdatacolumnsidecar)
  - [`PartialDataColumnPartsMetadata`](#partialdatacolumnpartsmetadata)
  - [`PartialDataColumnHeader`](#partialdatacolumnheader)
- [Helpers](#helpers)
  - [`verify_partial_data_column_header_inclusion_proof`](#verify_partial_data_column_header_inclusion_proof)
  - [`verify_partial_data_column_sidecar_kzg_proofs`](#verify_partial_data_column_sidecar_kzg_proofs)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Partial Messages on `data_column_sidecar_{subnet_id}`](#partial-messages-on-data_column_sidecar_subnet_id)
  - [Partial columns for Cell Dissemination](#partial-columns-for-cell-dissemination)
    - [Partial message group ID](#partial-message-group-id)
    - [Parts metadata](#parts-metadata)
    - [Encoding and decoding responses](#encoding-and-decoding-responses)
    - [Eager pushing](#eager-pushing)
    - [Interaction with standard gossipsub](#interaction-with-standard-gossipsub)
      - [Requesting partial messages](#requesting-partial-messages)
      - [Mesh](#mesh)
      - [Fanout](#fanout)
      - [Scoring](#scoring)
      - [Forwarding](#forwarding)

<!-- mdformat-toc end -->

## Introduction

This document specifies how data columns are disseminated as partial columns in
Fulu, using gossipsub's
[Partial Message Extension](https://github.com/libp2p/specs/pull/685) to
exchange individual cells and their proofs.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite. In
particular, this document builds on the
[Fulu networking specification](../p2p-interface.md).

## Containers

### `PartialDataColumnSidecar`

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

### `PartialDataColumnPartsMetadata`

Peers communicate the cells available with a bitmap. A set bit (`1`) at index
`i` means that the peer has the cell at index `i`. Peers explicitly request
cells with a second request bitmap of the same length that is set to `1` if the
peer would like to receive or provide this cell.

If a cell is available, its corresponding proof MUST be available.

This is encoded as the following SSZ container:

```python
class PartialDataColumnPartsMetadata(Container):
    available: Bitlist[MAX_BLOB_COMMITMENTS_PER_BLOCK]
    requests: Bitlist[MAX_BLOB_COMMITMENTS_PER_BLOCK]
```

This means that for each cell there are two bits of state. Where the first bit
represents the bit from the available bitlist, and the second bit represents the
bit from the requests bit.

| Bits | Description                                          |
| :--: | ---------------------------------------------------- |
|  00  | The peer does not have the cell and does not want it |
|  01  | The peer does not have the cell and does want it     |
|  1X  | The peer has the cell and is willing to provide it   |

Having a cell but not willing to provide it is functionally the same as not
having the cell and not wanting it, so it does not need a separate state.

### `PartialDataColumnHeader`

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

## Helpers

### `verify_partial_data_column_header_inclusion_proof`

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

### `verify_partial_data_column_sidecar_kzg_proofs`

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

## The gossip domain: gossipsub

### Partial Messages on `data_column_sidecar_{subnet_id}`

Validating partial messages happens in two parts. First, the
`PartialDataColumnHeader` needs to be validated, then the cell and proof data.

Once a `PartialDataColumnHeader` is validated for a corresponding block on any
subnet (gossipsub topic), it can be used for all subnets.

Due to the nature of partial messages, it is possible to get the
`PartialDataColumnHeader` with no cells, and get cells in a future response.

For all partial messages:

- _[REJECT]_ A header and/or cells are present in the message (it is not
  semantically empty).
- _[REJECT]_ There are the same number of cells and proofs in the message and
  this number is equal the number of 1s in the cells_present_bitmap.

For verifying the `PartialDataColumnHeader` in a partial message:

- _[REJECT]_ If a valid header was previously received, the received header MUST
  equal the previously valid header.
- _[REJECT]_ The hash of the block header in `signed_block_header` MUST be the
  same one identified by the partial message's group id.
- _[REJECT]_ The header's `kzg_commitments` list is non-empty.
- _[IGNORE]_ The header is not from a future slot (with a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. validate that
  `block_header.slot <= current_slot` (a client MAY queue future headers for
  processing at the appropriate slot).
- _[IGNORE]_ The header is from a slot greater than the latest finalized slot --
  i.e. validate that
  `block_header.slot > compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)`.j
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

- _[IGNORE]_ If the received partial message contains only cell and proof data,
  the node has seen a valid corresponding `PartialDataColumnHeader`.
- _[IGNORE]_ The corresponding header is not from a future slot. See related
  header check above for more details.
- _[IGNORE]_ The corresponding header is from a slot greater than the latest
  finalized slot. See related header check above for more details.
- _[REJECT]_ The cells present bitmap length is equal to the number of KZG
  commitments in the `PartialDataColumnHeader`.
- _[REJECT]_ For cells the receiver already has, The sidecar's cell and proof
  data are equal to the local copy. This an optional check for the receiver, but
  the sender MUST always send valid cell and proof data.
- _[REJECT]_ The sidecar's cell and proof data is valid as verified by
  `verify_partial_data_column_sidecar_kzg_proofs(sidecar, header.kzg_commitments, column_index)`.

### Partial columns for Cell Dissemination

Gossipsub's
[Partial Message Extension](https://github.com/libp2p/specs/pull/685) enables
exchanging selective parts of a message rather than the whole. The specification
here describes how consensus-layer clients use Partial Messages to disseminate
cells along with their proofs.

#### Partial message group ID

When sending a partial message, the gossipsub group ID MUST be the block root
prefixed by a single byte used for versioning. The version byte MUST be zero.
Other versions may be defined later.

#### Parts metadata

The parts metadata is encoded with the `PartialDataColumnPartsMetadata`
container.

#### Encoding and decoding responses

All responses MUST be encoded and decoded with the `PartialDataColumnSidecar`
container.

#### Eager pushing

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

Clients, by default, SHOULD NOT eagerly push cells when proposing a block.
Clients SHOULD expose a flag to opt-in to eagerly pushing all cells when
proposing a block.

Clients SHOULD eagerly push the `PartialDataColumnHeader` to inform peers as to
which blobs are included in this block, and therefore which cells they are
missing. Clients SHOULD NOT send a `PartialDataColumnHeader` to a peer that has
already sent the client a message, as that peer already has the header (it is a
prerequisite to sending a message).

Clients MAY choose to not eagerly push the `PartialDataColumnHeader` if it has
previously sent the header to the peer on another topic.

Clients SHOULD request cells from peers after validating a
`PartialDataColumnHeader`, even if the corresponding block has not been seen
yet.

#### Interaction with standard gossipsub

##### Requesting partial messages

A peer requests partial messages for a topic by setting the `partial` field in
gossipsub's `SubOpts` RPC message to `true`.

##### Mesh

The Partial Message Extension uses the same mesh peers for a given topic as the
standard gossipsub topics for `DataColumnSidecar`s.

##### Fanout

The Partial Message Extension uses the same fanout peers for a given topic as
the standard gossipsub topics for `DataColumnSidecar`s.

##### Scoring

On receiving useful novel data from a peer, the client should report to
gossipsub a positive first message delivery.

Clients SHOULD limit the rate at which a peer gets the first message delivery
reward to prevent a peer from scoring better by providing cells one at a time
rather than many cells at once.

On receiving invalid data, the client should report to gossipsub an invalid
message delivery.

##### Forwarding

Once clients can construct the full `DataColumnSidecar` after receiving missing
cells, they should forward the full `DataColumnSidecar` over standard gossipsub
to peers that do not support partial messages. This provides backwards
compatibility with nodes that do not yet support partial messages.

Avoid forwarding the full `DataColumnSidecar` message to peers that requested
partial messages for that given topic. It is purely redundant information.
