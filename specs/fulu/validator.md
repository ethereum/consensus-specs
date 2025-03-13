# Fulu -- Honest Validator

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the `DataColumnSidecar`s](#constructing-the-datacolumnsidecars)
      - [`get_data_column_sidecars`](#get_data_column_sidecars)
      - [`compute_subnet_for_data_column_sidecar`](#compute_subnet_for_data_column_sidecar)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement Fulu.

## Prerequisites

This document is an extension of the [Electra -- Honest Validator](../electra/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless
explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated [Beacon Chain
doc of Fulu](./beacon-chain.md) are requisite for this document and used throughout. Please see
related Beacon Chain doc before continuing and use them as a reference throughout.

### Block and sidecar proposal

#### Constructing the `DataColumnSidecar`s

*[New in Fulu:EIP7594]*

For a block proposal, blobs associated with a block are packaged into many `DataColumnSidecar`
objects for distribution to the associated sidecar topic, the `data_column_sidecar_{subnet_id}`
pubsub topic. A `DataColumnSidecar` can be viewed as vertical slice of all blobs stacked on top of
each other, with extra fields for the necessary context.

##### `get_data_column_sidecars`

The sequence of sidecars associated with a block and can be obtained by first computing
`cells_and_kzg_proofs = [compute_cells_and_kzg_proofs(blob) for blob in blobs]` and then calling
`get_data_column_sidecars(signed_block, cells_and_kzg_proofs)`.

```python
def get_data_column_sidecars(signed_block: SignedBeaconBlock,
                             cells_and_kzg_proofs: Sequence[Tuple[
        Vector[Cell, CELLS_PER_EXT_BLOB],
        Vector[KZGProof, CELLS_PER_EXT_BLOB]]]) -> Sequence[DataColumnSidecar]:
    """
    Given a signed block and the cells/proofs associated with each blob in the
    block, assemble the sidecars which can be distributed to peers.
    """
    blob_kzg_commitments = signed_block.message.body.blob_kzg_commitments
    assert len(cells_and_kzg_proofs) == len(blob_kzg_commitments)
    signed_block_header = compute_signed_block_header(signed_block)
    kzg_commitments_inclusion_proof = compute_merkle_proof(
        signed_block.message.body,
        get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments'),
    )

    sidecars = []
    for column_index in range(NUMBER_OF_COLUMNS):
        column_cells, column_proofs = [], []
        for cells, proofs in cells_and_kzg_proofs:
            column_cells.append(cells[column_index])
            column_proofs.append(proofs[column_index])
        sidecars.append(DataColumnSidecar(
            index=column_index,
            column=column_cells,
            kzg_commitments=blob_kzg_commitments,
            kzg_proofs=column_proofs,
            signed_block_header=signed_block_header,
            kzg_commitments_inclusion_proof=kzg_commitments_inclusion_proof,
        ))
    return sidecars
```

##### `compute_subnet_for_data_column_sidecar`

The `subnet_id` for the `data_column_sidecar` is calculated with:
- Let `column_index = data_column_sidecar.index`.
- Let `subnet_id = compute_subnet_for_data_column_sidecar(column_index)`.

```python
def compute_subnet_for_data_column_sidecar(column_index: ColumnIndex) -> SubnetID:
    return SubnetID(column_index % DATA_COLUMN_SIDECAR_SUBNET_COUNT)
```

After publishing, the peers on the network may request the sidecar through sync-requests, or a local
user may be interested.

The validator MUST hold on to sidecars for `MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` epochs and
serve when capable, to ensure the data-availability of these blobs throughout the network.

After `MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` nodes MAY prune the sidecars and/or stop
serving them.
