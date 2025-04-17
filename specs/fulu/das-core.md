# Fulu -- Data Availability Sampling Core

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Constants](#constants)
  - [Misc](#misc)
- [Custom types](#custom-types)
- [Configuration](#configuration)
  - [Data size](#data-size)
  - [Custody setting](#custody-setting)
  - [Blob schedule](#blob-schedule)
  - [Containers](#containers)
    - [`DataColumnSidecar`](#datacolumnsidecar)
    - [`MatrixEntry`](#matrixentry)
- [Helper functions](#helper-functions)
  - [`get_custody_groups`](#get_custody_groups)
  - [`get_max_blobs_per_block`](#get_max_blobs_per_block)
  - [`compute_columns_for_custody_group`](#compute_columns_for_custody_group)
  - [`compute_matrix`](#compute_matrix)
  - [`recover_matrix`](#recover_matrix)
- [Custody](#custody)
  - [Custody requirement](#custody-requirement)
  - [Public, deterministic selection](#public-deterministic-selection)
- [Custody sampling](#custody-sampling)
- [Extended data](#extended-data)
- [Column gossip](#column-gossip)
  - [Parameters](#parameters)
- [Reconstruction and cross-seeding](#reconstruction-and-cross-seeding)
- [FAQs](#faqs)
  - [Why don't nodes custody rows?](#why-dont-nodes-custody-rows)
  - [Why don't we rotate custody over time?](#why-dont-we-rotate-custody-over-time)
  - [Does having a lot of column subnets make the network unstable?](#does-having-a-lot-of-column-subnets-make-the-network-unstable)

<!-- mdformat-toc end -->

## Constants

The following values are (non-configurable) constants used throughout the specification.

### Misc

| Name          | Value                 |
| ------------- | --------------------- |
| `UINT256_MAX` | `uint256(2**256 - 1)` |

## Custom types

| Name           | SSZ equivalent | Description                                           |
| -------------- | -------------- | ----------------------------------------------------- |
| `RowIndex`     | `uint64`       | Row identifier in the matrix of cells                 |
| `ColumnIndex`  | `uint64`       | Column identifier in the matrix of cells              |
| `CustodyIndex` | `uint64`       | Custody group identifier in the set of custody groups |

## Configuration

### Data size

| Name                | Value                                | Description                                   |
| ------------------- | ------------------------------------ | --------------------------------------------- |
| `NUMBER_OF_COLUMNS` | `uint64(CELLS_PER_EXT_BLOB)` (= 128) | Number of columns in the extended data matrix |

### Custody setting

| Name                       | Value | Description                                                                       |
| -------------------------- | ----- | --------------------------------------------------------------------------------- |
| `SAMPLES_PER_SLOT`         | `8`   | Number of `DataColumnSidecar` random samples a node queries per slot              |
| `NUMBER_OF_CUSTODY_GROUPS` | `128` | Number of custody groups available for nodes to custody                           |
| `CUSTODY_REQUIREMENT`      | `4`   | Minimum number of custody groups an honest node custodies and serves samples from |

### Blob schedule

*[New in EIP7594]* This schedule defines the maximum blobs per block limit for a given epoch.

<!-- list-of-records:blob_schedule -->

| Epoch                                  | Max Blobs Per Block | Description                                                               |
| -------------------------------------- | ------------------- | ------------------------------------------------------------------------- |
| `Epoch(269568)` **Deneb**              | `uint64(6)`         | Starting at epoch `269568`, the limit is `6` blobs                        |
| `Epoch(364032)` **Electra**            | `uint64(9)`         | Starting at epoch `364032`, the limit is `9` blobs                        |
| `Epoch(18446744073709551615)` **BPO1** | `uint64(18)`        | Starting at epoch `18446744073709551615` **TBD**, the limit is `18` blobs |
| `Epoch(18446744073709551615)` **BPO2** | `uint64(36)`        | Starting at epoch `18446744073709551615` **TBD**, the limit is `36` blobs |
| `Epoch(18446744073709551615)` **BPO3** | `uint64(72)`        | Starting at epoch `18446744073709551615` **TBD**, the limit is `72` blobs |

### Containers

#### `DataColumnSidecar`

```python
class DataColumnSidecar(Container):
    index: ColumnIndex  # Index of column in extended matrix
    column: List[Cell, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_proofs: List[KZGProof, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    signed_block_header: SignedBeaconBlockHeader
    kzg_commitments_inclusion_proof: Vector[Bytes32, KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH]
```

#### `MatrixEntry`

```python
class MatrixEntry(Container):
    cell: Cell
    kzg_proof: KZGProof
    column_index: ColumnIndex
    row_index: RowIndex
```

## Helper functions

### `get_custody_groups`

```python
def get_custody_groups(node_id: NodeID, custody_group_count: uint64) -> Sequence[CustodyIndex]:
    assert custody_group_count <= NUMBER_OF_CUSTODY_GROUPS

    current_id = uint256(node_id)
    custody_groups: List[CustodyIndex] = []
    while len(custody_groups) < custody_group_count:
        custody_group = CustodyIndex(
            bytes_to_uint64(hash(uint_to_bytes(current_id))[0:8])
            % NUMBER_OF_CUSTODY_GROUPS
        )
        if custody_group not in custody_groups:
            custody_groups.append(custody_group)
        if current_id == UINT256_MAX:
            # Overflow prevention
            current_id = uint256(0)
        else:
            current_id += 1

    assert len(custody_groups) == len(set(custody_groups))
    return sorted(custody_groups)
```

### `get_max_blobs_per_block`

```python
def get_max_blobs_per_block(epoch: Epoch) -> int:
    assert epoch >= DENEB_FORK_EPOCH
    for entry in reversed(sorted(BLOB_SCHEDULE, key=lambda e: e["EPOCH"])):        
        if entry["EPOCH"] < epoch:
            return entry["MAX_BLOBS_PER_BLOCK"]
    return 0
```

### `compute_columns_for_custody_group`

```python
def compute_columns_for_custody_group(custody_group: CustodyIndex) -> Sequence[ColumnIndex]:
    assert custody_group < NUMBER_OF_CUSTODY_GROUPS
    columns_per_group = NUMBER_OF_COLUMNS // NUMBER_OF_CUSTODY_GROUPS
    return sorted([
        ColumnIndex(NUMBER_OF_CUSTODY_GROUPS * i + custody_group)
        for i in range(columns_per_group)
    ])
```

### `compute_matrix`

```python
def compute_matrix(blobs: Sequence[Blob]) -> Sequence[MatrixEntry]:
    """
    Return the full, flattened sequence of matrix entries.

    This helper demonstrates the relationship between blobs and the matrix of cells/proofs.
    The data structure for storing cells/proofs is implementation-dependent.
    """
    matrix = []
    for blob_index, blob in enumerate(blobs):
        cells, proofs = compute_cells_and_kzg_proofs(blob)
        for cell_index, (cell, proof) in enumerate(zip(cells, proofs)):
            matrix.append(MatrixEntry(
                cell=cell,
                kzg_proof=proof,
                row_index=blob_index,
                column_index=cell_index,
            ))
    return matrix
```

### `recover_matrix`

```python
def recover_matrix(partial_matrix: Sequence[MatrixEntry], blob_count: uint64) -> Sequence[MatrixEntry]:
    """
    Recover the full, flattened sequence of matrix entries.

    This helper demonstrates how to apply ``recover_cells_and_kzg_proofs``.
    The data structure for storing cells/proofs is implementation-dependent.
    """
    matrix = []
    for blob_index in range(blob_count):
        cell_indices = [e.column_index for e in partial_matrix if e.row_index == blob_index]
        cells = [e.cell for e in partial_matrix if e.row_index == blob_index]
        recovered_cells, recovered_proofs = recover_cells_and_kzg_proofs(cell_indices, cells)
        for cell_index, (cell, proof) in enumerate(zip(recovered_cells, recovered_proofs)):
            matrix.append(MatrixEntry(
                cell=cell,
                kzg_proof=proof,
                row_index=blob_index,
                column_index=cell_index,
            ))
    return matrix
```

## Custody

### Custody requirement

Columns are grouped into custody groups. Nodes custodying a custody group MUST custody all the columns in that group. When syncing, a node MUST backfill columns from all of its custody groups.

A node *may* choose to custody and serve more than the minimum honesty requirement. Such a node explicitly advertises a number greater than `CUSTODY_REQUIREMENT` through the peer discovery mechanism, specifically by setting a higher value in the `custody_group_count` field within its ENR. This value can be increased up to `NUMBER_OF_CUSTODY_GROUPS`, indicating a super-full node.

A node stores the custodied columns for the duration of the pruning period and responds to peer requests for samples on those columns.

### Public, deterministic selection

The particular columns/groups that a node custodies are selected pseudo-randomly as a function (`get_custody_groups`) of the node-id and custody size -- importantly this function can be run by any party as the inputs are all public.

*Note*: increasing the `custody_size` parameter for a given `node_id` extends the returned list (rather than being an entirely new shuffle) such that if `custody_size` is unknown, the default `CUSTODY_REQUIREMENT` will be correct for a subset of the node's custody.

## Custody sampling

At each slot, a node advertising `custody_group_count` downloads a minimum of `sampling_size = max(SAMPLES_PER_SLOT, custody_group_count * columns_per_group)` total columns, where `columns_per_group = NUMBER_OF_COLUMNS // NUMBER_OF_CUSTODY_GROUPS`. The corresponding set of columns is selected by `groups = get_custody_groups(node_id, sampling_size)` and `compute_columns_for_custody_group(group) for group in groups`, so that in particular the subset of columns to custody is consistent with the output of `get_custody_groups(node_id, custody_group_count)`. Sampling is considered successful if the node manages to retrieve all selected columns.

## Extended data

In this construction, we extend the blobs using a one-dimensional erasure coding extension. The matrix comprises maximum `MAX_BLOBS_PER_BLOCK` rows and fixed `NUMBER_OF_COLUMNS` columns, with each row containing a `Blob` and its corresponding extension. `compute_matrix` demonstrates the relationship between blobs and the matrix, a potential method of storing cells/proofs.

## Column gossip

### Parameters

Verifiable samples from their respective column are distributed on the assigned subnet. To custody columns in a particular custody group, a node joins the respective gossipsub subnets. If a node fails to get columns on the column subnets, a node can also utilize the Req/Resp protocol to query the missing columns from other peers.

## Reconstruction and cross-seeding

If the node obtains 50%+ of all the columns, it SHOULD reconstruct the full data matrix via `recover_matrix` helper. Nodes MAY delay this reconstruction allowing time for other columns to arrive over the network. If delaying reconstruction, nodes may use a random delay in order to desynchronize reconstruction among nodes, thus reducing overall CPU load.

Once the node obtains a column through reconstruction, the node MUST expose the new column as if it had received it over the network. If the node is subscribed to the subnet corresponding to the column, it MUST send the reconstructed DataColumnSidecar to its topic mesh neighbors. If instead the node is not subscribed to the corresponding subnet, it SHOULD still expose the availability of the DataColumnSidecar as part of the gossip emission process.

*Note*: A node always maintains a matrix view of the rows and columns they are following, able to cross-reference and cross-seed in either direction.

*Note*: There are timing considerations to analyze -- at what point does a node consider samples missing and choose to reconstruct and cross-seed.

*Note*: There may be anti-DoS and quality-of-service considerations around how to send samples and consider samples -- is each individual sample a message or are they sent in aggregate forms.

## FAQs

### Why don't nodes custody rows?

In the one-dimension construction, a node samples the peers by requesting the whole `DataColumnSidecar`. In reconstruction, a node can reconstruct all the blobs by 50% of the columns. Note that nodes can still download the row via `blob_sidecar_{subnet_id}` subnets.

The potential benefits of having row custody could include:

1. Allow for more "natural" distribution of data to consumers -- e.g., roll-ups -- but honestly, they won't know a priori which row their blob is going to be included in in the block, so they would either need to listen to all rows or download a particular row after seeing the block. The former looks just like listening to column \[0, N) and the latter is req/resp instead of gossiping.
2. Help with some sort of distributed reconstruction. Those with full rows can compute extensions and seed missing samples to the network. This would either need to be able to send individual points on the gossip or would need some sort of req/resp faculty, potentially similar to an `IHAVEPOINTBITFIELD` and `IWANTSAMPLE`.

However, for simplicity, we don't assign row custody assignments to nodes in the current design.

### Why don't we rotate custody over time?

To start with a simple, stable backbone, for now, we don't shuffle the custody assignments via the deterministic custody selection helper `get_custody_groups`. However, staggered rotation likely needs to happen on the order of the pruning period to ensure subnets can be utilized for recovery. For example, introducing an `epoch` argument allows the function to maintain stability over many epochs.

### Does having a lot of column subnets make the network unstable?

No, the number of subnets doesn't really matter. What matters to the network stability is the number of nodes and the churn rate in the network. If the number of the nodes is too low, it's likely to have a network partition when some nodes are down. For the churn rate, if the churn rate is high, we even need to have a higher number of nodes, since nodes are likely to be turned off more often.
