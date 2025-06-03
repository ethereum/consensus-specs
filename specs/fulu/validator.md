# Fulu -- Honest Validator

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
  - [Custody setting](#custody-setting)
- [Helpers](#helpers)
  - [`BlobsBundle`](#blobsbundle)
  - [Modified `GetPayloadResponse`](#modified-getpayloadresponse)
- [Protocol](#protocol)
  - [`ExecutionEngine`](#executionengine)
    - [Modified `get_payload`](#modified-get_payload)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Validator custody](#validator-custody)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the sidecars](#constructing-the-sidecars)
      - [`get_data_column_sidecars`](#get_data_column_sidecars)
      - [`get_data_column_sidecars_from_block`](#get_data_column_sidecars_from_block)
      - [`get_data_column_sidecars_from_column_sidecar`](#get_data_column_sidecars_from_column_sidecar)
    - [Sidecar publishing](#sidecar-publishing)
    - [Sidecar retention](#sidecar-retention)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement Fulu.

## Prerequisites

This document is an extension of the
[Electra -- Honest Validator](../electra/validator.md) guide. All behaviors and
definitions defined in this document, and documents it extends, carry over
unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in
[Fulu -- Beacon Chain](./beacon-chain.md) and
[Fulu -- Data Availability Sampling Core](./das-core.md) are requisite for this
document and used throughout.

## Configuration

### Custody setting

| Name                                   | Value              | Description                                                                                                |
| -------------------------------------- | ------------------ | ---------------------------------------------------------------------------------------------------------- |
| `VALIDATOR_CUSTODY_REQUIREMENT`        | `8`                | Minimum number of custody groups an honest node with validators attached custodies and serves samples from |
| `BALANCE_PER_ADDITIONAL_CUSTODY_GROUP` | `Gwei(32 * 10**9)` | Effective balance increment corresponding to one additional group to custody                               |

## Helpers

### `BlobsBundle`

*[Modified in Fulu:EIP7594]*

The `BlobsBundle` object is modified to include cell KZG proofs instead of blob
KZG proofs.

```python
@dataclass
class BlobsBundle(object):
    commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    # [Modified in Fulu:EIP7594]
    proofs: List[KZGProof, FIELD_ELEMENTS_PER_EXT_BLOB * MAX_BLOB_COMMITMENTS_PER_BLOCK]
    blobs: List[Blob, MAX_BLOB_COMMITMENTS_PER_BLOCK]
```

### Modified `GetPayloadResponse`

*[Modified in Fulu:EIP7594]*

The `GetPayloadResponse` object is modified to use the updated `BlobsBundle`
object.

```python
@dataclass
class GetPayloadResponse(object):
    execution_payload: ExecutionPayload
    block_value: uint256
    blobs_bundle: BlobsBundle  # [Modified in Fulu:EIP7594]
```

## Protocol

### `ExecutionEngine`

#### Modified `get_payload`

The `get_payload` method is modified to return the updated `GetPayloadResponse`
object.

```python
def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
    """
    Return ExecutionPayload, uint256, BlobsBundle objects.
    """
    # pylint: disable=unused-argument
    ...
```

## Beacon chain responsibilities

### Validator custody

*[New in Fulu:EIP7594]*

A node with validators attached downloads and custodies a higher minimum of
custody groups per slot, determined by
`get_validators_custody_requirement(state, validator_indices)`. Here, `state` is
the latest finalized `BeaconState` and `validator_indices` is the list of
indices corresponding to validators attached to the node. Any node with at least
one validator attached, and with the sum of the effective balances of all
attached validators being `total_node_balance`, downloads and custodies
`total_node_balance // BALANCE_PER_ADDITIONAL_CUSTODY_GROUP` custody groups per
slot, with a minimum of `VALIDATOR_CUSTODY_REQUIREMENT` and of course a maximum
of `NUMBER_OF_CUSTODY_GROUPS`.

```python
def get_validators_custody_requirement(state: BeaconState, validator_indices: Sequence[ValidatorIndex]) -> uint64:
    total_node_balance = sum(state.validators[index].effective_balance for index in validator_indices)
    count = total_node_balance // BALANCE_PER_ADDITIONAL_CUSTODY_GROUP
    return min(max(count, VALIDATOR_CUSTODY_REQUIREMENT), NUMBER_OF_CUSTODY_GROUPS)
```

This higher custody is advertised in the node's Metadata by setting a higher
`custody_group_count` and in the node's ENR by setting a higher
`custody_group_count`. As with the regular custody requirement, a node with
validators MAY still choose to custody, advertise and serve more than this
minimum. As with the regular custody requirement, a node MUST backfill columns
when syncing.

A node SHOULD dynamically adjust its custody groups (without any input from the
user) following any changes to the total effective balances of attached
validators.

If the node's custody requirements are increased, it MAY backfill custody groups
as a result of this change. In such cases, it SHOULD delay advertising the
updated `custody_group_count` until the backfill is complete. If the node opts
not to perform a backfill, it SHOULD only advertise the updated
`custody_group_count` after `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` epochs.
After `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` epochs, the node will be able to
respond to any `DataColumnSidecar` request within the retention period. The
updated `custody_group_count` SHOULD persist across node restarts.

If a node's custody requirements decrease, it SHOULD NOT update the
`custody_group_count` to reflect this reduction. The node SHOULD continue to
custody and advertise the previous (highest) `custody_group_count`. The node
SHOULD continue to respond to any `DataColumnSidecar` request corresponding to
the previous (highest) `custody_group_count`. The previous (highest)
`custody_group_count` SHOULD persist across node restarts.

Nodes SHOULD be capable of handling multiple changes to custody requirements
within the same retention period (e.g., an increase in one epoch followed by a
decrease in the next).

### Block and sidecar proposal

#### Constructing the sidecars

*[New in Fulu:EIP7594]*

For a block proposal, blobs associated with a block are packaged into many
`DataColumnSidecar` objects for distribution to the associated sidecar topic,
the `data_column_sidecar_{subnet_id}` pubsub topic. A `DataColumnSidecar` can be
viewed as vertical slice of all blobs stacked on top of each other, with extra
fields for the necessary context.

##### `get_data_column_sidecars`

The sequence of sidecars associated with a block and can be obtained by first
computing
`cells_and_kzg_proofs = [compute_cells_and_kzg_proofs(blob) for blob in blobs]`
and then calling
`get_data_column_sidecars_from_block(signed_block, cells_and_kzg_proofs)`.

Moreover, the full sequence of sidecars can also be computed from
`cells_and_kzg_proofs` and any single `sidecar`, by calling
`get_data_column_sidecars_from_column_sidecar(sidecar, cells_and_kzg_proofs)`.
This can be used in distributed blob publishing, to reconstruct all sidecars
from any sidecar received on the wire, assuming all cells and kzg proofs could
be retrieved from the local execution layer client.

```python
def get_data_column_sidecars(
    signed_block_header: SignedBeaconBlockHeader,
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK],
    kzg_commitments_inclusion_proof: Vector[Bytes32, KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH],
    cells_and_kzg_proofs: Sequence[Tuple[
        Vector[Cell, CELLS_PER_EXT_BLOB],
        Vector[KZGProof, CELLS_PER_EXT_BLOB]
    ]]
) -> Sequence[DataColumnSidecar]:
    """
    Given a signed block header and the commitments, inclusion proof, cells/proofs associated with
    each blob in the block, assemble the sidecars which can be distributed to peers.
    """
    assert len(cells_and_kzg_proofs) == len(kzg_commitments)

    sidecars = []
    for column_index in range(NUMBER_OF_COLUMNS):
        column_cells, column_proofs = [], []
        for cells, proofs in cells_and_kzg_proofs:
            column_cells.append(cells[column_index])
            column_proofs.append(proofs[column_index])
        sidecars.append(DataColumnSidecar(
            index=column_index,
            column=column_cells,
            kzg_commitments=kzg_commitments,
            kzg_proofs=column_proofs,
            signed_block_header=signed_block_header,
            kzg_commitments_inclusion_proof=kzg_commitments_inclusion_proof,
        ))
    return sidecars
```

##### `get_data_column_sidecars_from_block`

```python
def get_data_column_sidecars_from_block(
    signed_block: SignedBeaconBlock,
    cells_and_kzg_proofs: Sequence[Tuple[
        Vector[Cell, CELLS_PER_EXT_BLOB],
        Vector[KZGProof, CELLS_PER_EXT_BLOB]
    ]]
) -> Sequence[DataColumnSidecar]:
    """
    Given a signed block and the cells/proofs associated with each blob in the
    block, assemble the sidecars which can be distributed to peers.
    """
    blob_kzg_commitments = signed_block.message.body.blob_kzg_commitments
    signed_block_header = compute_signed_block_header(signed_block)
    kzg_commitments_inclusion_proof = compute_merkle_proof(
        signed_block.message.body,
        get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments'),
    )
    return get_data_column_sidecars(
        signed_block_header,
        blob_kzg_commitments,
        kzg_commitments_inclusion_proof,
        cells_and_kzg_proofs
    )
```

##### `get_data_column_sidecars_from_column_sidecar`

```python
def get_data_column_sidecars_from_column_sidecar(
    sidecar: DataColumnSidecar,
    cells_and_kzg_proofs: Sequence[Tuple[
        Vector[Cell, CELLS_PER_EXT_BLOB],
        Vector[KZGProof, CELLS_PER_EXT_BLOB]
    ]]
) -> Sequence[DataColumnSidecar]:
    """
    Given a DataColumnSidecar and the cells/proofs associated with each blob corresponding
    to the commitments it contains, assemble all sidecars for distribution to peers.
    """
    assert len(cells_and_kzg_proofs) == len(sidecar.kzg_commitments)

    return get_data_column_sidecars(
        sidecar.signed_block_header,
        sidecar.kzg_commitments,
        sidecar.kzg_commitments_inclusion_proof,
        cells_and_kzg_proofs
    )
```

#### Sidecar publishing

The `subnet_id` for the `data_column_sidecar` is calculated with:

- Let `column_index = data_column_sidecar.index`.
- Let `subnet_id = compute_subnet_for_data_column_sidecar(column_index)`.

After publishing all columns to their respective subnets, peers on the network
may request the sidecar through sync-requests, or a local user may be
interested.

#### Sidecar retention

The validator MUST hold on to sidecars for
`MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` epochs and serve when capable, to
ensure the data-availability of these blobs throughout the network.

After `MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` nodes MAY prune the
sidecars and/or stop serving them.
