# EIP-7594 -- Data Availability Sampling Core

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Constants](#constants)
  - [Misc](#misc)
- [Custom types](#custom-types)
- [Configuration](#configuration)
  - [Data size](#data-size)
  - [Networking](#networking)
  - [Custody setting](#custody-setting)
  - [Containers](#containers)
    - [`DataColumnSidecar`](#datacolumnsidecar)
    - [`MatrixEntry`](#matrixentry)
  - [Helper functions](#helper-functions)
    - [`get_custody_columns`](#get_custody_columns)
    - [`compute_extended_matrix`](#compute_extended_matrix)
    - [`recover_matrix`](#recover_matrix)
    - [`get_data_column_sidecars`](#get_data_column_sidecars)
    - [`get_extended_sample_count`](#get_extended_sample_count)
- [Custody](#custody)
  - [Custody requirement](#custody-requirement)
  - [Public, deterministic selection](#public-deterministic-selection)
- [Peer discovery](#peer-discovery)
- [Extended data](#extended-data)
- [Column gossip](#column-gossip)
  - [Parameters](#parameters)
- [Peer sampling](#peer-sampling)
  - [Sample selection](#sample-selection)
  - [Sample queries](#sample-queries)
- [Peer scoring](#peer-scoring)
- [Reconstruction and cross-seeding](#reconstruction-and-cross-seeding)
- [DAS providers](#das-providers)
- [A note on fork choice](#a-note-on-fork-choice)
- [FAQs](#faqs)
  - [Row (blob) custody](#row-blob-custody)
  - [Subnet stability](#subnet-stability)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Constants

The following values are (non-configurable) constants used throughout the specification.

### Misc

| Name | Value |
| - | - |
| `UINT256_MAX` | `uint256(2**256 - 1)` |

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `RowIndex` | `uint64` | Row identifier in the matrix of cells |
| `ColumnIndex` | `uint64` | Column identifier in the matrix of cells |

## Configuration

### Data size

| Name | Value | Description |
| - | - | - |
| `NUMBER_OF_COLUMNS` | `uint64(CELLS_PER_EXT_BLOB)` (= 128) | Number of columns in the extended data matrix |
| `MAX_CELLS_IN_EXTENDED_MATRIX` | `uint64(MAX_BLOBS_PER_BLOCK * NUMBER_OF_COLUMNS)` (= 768) | The data size of `ExtendedMatrix` |

### Networking

| Name | Value | Description |
| - | - | - |
| `DATA_COLUMN_SIDECAR_SUBNET_COUNT` | `32` | The number of data column sidecar subnets used in the gossipsub protocol |

### Custody setting

| Name | Value | Description |
| - | - | - |
| `SAMPLES_PER_SLOT` | `8` | Number of `DataColumnSidecar` random samples a node queries per slot |
| `CUSTODY_REQUIREMENT` | `1` | Minimum number of subnets an honest node custodies and serves samples from |
| `TARGET_NUMBER_OF_PEERS` | `70` | Suggested minimum peer count |

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

### Helper functions

#### `get_custody_columns`

```python
def get_custody_columns(node_id: NodeID, custody_subnet_count: uint64) -> Sequence[ColumnIndex]:
    assert custody_subnet_count <= DATA_COLUMN_SIDECAR_SUBNET_COUNT

    subnet_ids: List[uint64] = []
    current_id = uint256(node_id)
    while len(subnet_ids) < custody_subnet_count:
        subnet_id = (
            bytes_to_uint64(hash(uint_to_bytes(uint256(current_id)))[0:8])
            % DATA_COLUMN_SIDECAR_SUBNET_COUNT
        )
        if subnet_id not in subnet_ids:
            subnet_ids.append(subnet_id)
        if current_id == UINT256_MAX:
            # Overflow prevention
            current_id = NodeID(0)
        current_id += 1

    assert len(subnet_ids) == len(set(subnet_ids))

    columns_per_subnet = NUMBER_OF_COLUMNS // DATA_COLUMN_SIDECAR_SUBNET_COUNT
    return sorted([
        ColumnIndex(DATA_COLUMN_SIDECAR_SUBNET_COUNT * i + subnet_id)
        for i in range(columns_per_subnet)
        for subnet_id in subnet_ids
    ])
```

#### `compute_extended_matrix`

```python
def compute_extended_matrix(blobs: Sequence[Blob]) -> List[MatrixEntry, MAX_CELLS_IN_EXTENDED_MATRIX]:
    """
    Return the full ``ExtendedMatrix``.

    This helper demonstrates the relationship between blobs and ``ExtendedMatrix``.
    The data structure for storing cells is implementation-dependent.
    """
    extended_matrix = []
    for blob_index, blob in enumerate(blobs):
        cells, proofs = compute_cells_and_kzg_proofs(blob)
        for cell_index, (cell, proof) in enumerate(zip(cells, proofs)):
            extended_matrix.append(MatrixEntry(
                cell=cell,
                kzg_proof=proof,
                row_index=blob_index,
                column_index=cell_index,
            ))
    return extended_matrix
```

#### `recover_matrix`

```python
def recover_matrix(partial_matrix: Sequence[MatrixEntry],
                   blob_count: uint64) -> List[MatrixEntry, MAX_CELLS_IN_EXTENDED_MATRIX]:
    """
    Return the recovered extended matrix.

    This helper demonstrates how to apply ``recover_cells_and_kzg_proofs``.
    The data structure for storing cells is implementation-dependent.
    """
    extended_matrix = []
    for blob_index in range(blob_count):
        cell_indices = [e.column_index for e in partial_matrix if e.row_index == blob_index]
        cells = [e.cell for e in partial_matrix if e.row_index == blob_index]

        recovered_cells, recovered_proofs = recover_cells_and_kzg_proofs(cell_indices, cells)
        for cell_index, (cell, proof) in enumerate(zip(recovered_cells, recovered_proofs)):
            extended_matrix.append(MatrixEntry(
                cell=cell,
                kzg_proof=proof,
                row_index=blob_index,
                column_index=cell_index,
            ))
    return extended_matrix
```

#### `get_data_column_sidecars`

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

#### `get_extended_sample_count`

```python
def get_extended_sample_count(allowed_failures: uint64) -> uint64:
    assert 0 <= allowed_failures <= NUMBER_OF_COLUMNS // 2
    """
    Return the sample count if allowing failures.

    This helper demonstrates how to calculate the number of columns to query per slot when
    allowing given number of failures, assuming uniform random selection without replacement.
    Nested functions are direct replacements of Python library functions math.comb and
    scipy.stats.hypergeom.cdf, with the same signatures.
    """

    def math_comb(n: int, k: int) -> int:
        if not 0 <= k <= n:
            return 0
        r = 1
        for i in range(min(k, n - k)):
            r = r * (n - i) // (i + 1)
        return r

    def hypergeom_cdf(k: uint64, M: uint64, n: uint64, N: uint64) -> float:
        # NOTE: It contains float-point computations.
        # Convert uint64 to Python integers before computations.
        k = int(k)
        M = int(M)
        n = int(n)
        N = int(N)
        return sum([math_comb(n, i) * math_comb(M - n, N - i) / math_comb(M, N)
                    for i in range(k + 1)])

    worst_case_missing = NUMBER_OF_COLUMNS // 2 + 1
    false_positive_threshold = hypergeom_cdf(0, NUMBER_OF_COLUMNS,
                                             worst_case_missing, SAMPLES_PER_SLOT)
    for sample_count in range(SAMPLES_PER_SLOT, NUMBER_OF_COLUMNS + 1):
        if hypergeom_cdf(allowed_failures, NUMBER_OF_COLUMNS,
                         worst_case_missing, sample_count) <= false_positive_threshold:
            break
    return sample_count
```

## Custody

### Custody requirement

Each node downloads and custodies a minimum of `CUSTODY_REQUIREMENT` subnets per slot. The particular subnets that the node is required to custody are selected pseudo-randomly (more on this below).

A node *may* choose to custody and serve more than the minimum honesty requirement. Such a node explicitly advertises a number greater than `CUSTODY_REQUIREMENT` via the peer discovery mechanism -- for example, in their ENR (e.g. `custody_subnet_count: 4` if the node custodies `4` subnets each slot) -- up to a `DATA_COLUMN_SIDECAR_SUBNET_COUNT` (i.e. a super-full node).

A node stores the custodied columns for the duration of the pruning period and responds to peer requests for samples on those columns.

### Public, deterministic selection

The particular columns that a node custodies are selected pseudo-randomly as a function (`get_custody_columns`) of the node-id and custody size -- importantly this function can be run by any party as the inputs are all public.

*Note*: increasing the `custody_size` parameter for a given `node_id` extends the returned list (rather than being an entirely new shuffle) such that if `custody_size` is unknown, the default `CUSTODY_REQUIREMENT` will be correct for a subset of the node's custody.

## Peer discovery

At each slot, a node needs to be able to readily sample from *any* set of columns. To this end, a node SHOULD find and maintain a set of diverse and reliable peers that can regularly satisfy their sampling demands.

A node runs a background peer discovery process, maintaining at least `TARGET_NUMBER_OF_PEERS` of various custody distributions (both `custody_size` and column assignments). The combination of advertised `custody_size` size and public node-id make this readily and publicly accessible.

`TARGET_NUMBER_OF_PEERS` should be tuned upward in the event of failed sampling.

*Note*: while high-capacity and super-full nodes are high value with respect to satisfying sampling requirements, a node SHOULD maintain a distribution across node capacities as to not centralize the p2p graph too much (in the extreme becomes hub/spoke) and to distribute sampling load better across all nodes.

*Note*: A DHT-based peer discovery mechanism is expected to be utilized in the above. The beacon-chain network currently utilizes discv5 in a similar method as described for finding peers of particular distributions of attestation subnets. Additional peer discovery methods are valuable to integrate (e.g., latent peer discovery via libp2p gossipsub) to add a defense in breadth against one of the discovery methods being attacked.

## Extended data

In this construction, we extend the blobs using a one-dimensional erasure coding extension. The matrix comprises maximum `MAX_BLOBS_PER_BLOCK` rows and fixed `NUMBER_OF_COLUMNS` columns, with each row containing a `Blob` and its corresponding extension. `compute_extended_matrix` demonstrates the relationship between blobs and custom type `ExtendedMatrix`.

## Column gossip

### Parameters

For each column -- use `data_column_sidecar_{subnet_id}` subnets, where `subnet_id` can be computed with the `compute_subnet_for_data_column_sidecar(column_index: ColumnIndex)` helper. The sidecars can be computed with the `get_data_column_sidecars(signed_block: SignedBeaconBlock, blobs: Sequence[Blob])` helper.

Verifiable samples from their respective column are distributed on the assigned subnet. To custody a particular column, a node joins the respective gossipsub subnet. If a node fails to get a column on the column subnet, a node can also utilize the Req/Resp protocol to query the missing column from other peers.

## Peer sampling

### Sample selection

At each slot, a node SHOULD select at least `SAMPLES_PER_SLOT` column IDs for sampling. It is recommended to use uniform random selection without replacement based on local randomness. Sampling is considered successful if the node manages to retrieve all selected columns.

Alternatively, a node MAY use a method that selects more than `SAMPLES_PER_SLOT` columns while allowing some missing, respecting the same target false positive threshold (the probability of successful sampling of an unavailable block) as dictated by the `SAMPLES_PER_SLOT` parameter. If using uniform random selection without replacement, a node can use the `get_extended_sample_count(allowed_failures) -> sample_count` helper function to determine the sample count (number of unique column IDs) for any selected number of allowed failures. Sampling is then considered successful if any `sample_count - allowed_failures` columns are retrieved successfully.

For reference, the table below shows the number of samples and the number of allowed missing columns assuming `NUMBER_OF_COLUMNS = 128` and `SAMPLES_PER_SLOT = 16`.

| Allowed missing | 0| 1| 2| 3| 4| 5| 6| 7| 8|
|-----------------|--|--|--|--|--|--|--|--|--|
| Sample count    |16|20|24|27|29|32|35|37|40|

### Sample queries

A node SHOULD maintain a diverse set of peers for each column and each slot by verifying responsiveness to sample queries.

A node SHOULD query for samples from selected peers via `DataColumnSidecarsByRoot` request. A node utilizes `get_custody_columns` helper to determine which peer(s) it could request from, identifying a list of candidate peers for each selected column.

If more than one candidate peer is found for a given column, a node SHOULD randomize its peer selection to distribute sample query load in the network. Nodes MAY use peer scoring to tune this selection (for example, by using weighted selection or by using a cut-off threshold). If possible, it is also recommended to avoid requesting many columns from the same peer in order to avoid relying on and exposing the sample selection to a single peer.

If a node already has a column because of custody, it is not required to send out queries for that column.

If a node has enough good/honest peers across all columns, and the data is being made available, the above procedure has a high chance of success.

## Peer scoring

Due to the deterministic custody functions, a node knows exactly what a peer should be able to respond to. In the event that a peer does not respond to samples of their custodied rows/columns, a node may downscore or disconnect from a peer.

## Reconstruction and cross-seeding

If the node obtains 50%+ of all the columns, it SHOULD reconstruct the full data matrix via `recover_matrix` helper. Nodes MAY delay this reconstruction allowing time for other columns to arrive over the network. If delaying reconstruction, nodes may use a random delay in order to desynchronize reconstruction among nodes, thus reducing overall CPU load.

Once the node obtains a column through reconstruction, the node MUST expose the new column as if it had received it over the network. If the node is subscribed to the subnet corresponding to the column, it MUST send the reconstructed DataColumnSidecar to its topic mesh neighbors. If instead the node is not subscribed to the corresponding subnet, it SHOULD still expose the availability of the DataColumnSidecar as part of the gossip emission process.

*Note*: A node always maintains a matrix view of the rows and columns they are following, able to cross-reference and cross-seed in either direction.

*Note*: There are timing considerations to analyze -- at what point does a node consider samples missing and choose to reconstruct and cross-seed.

*Note*: There may be anti-DoS and quality-of-service considerations around how to send samples and consider samples -- is each individual sample a message or are they sent in aggregate forms.

## DAS providers

A DAS provider is a consistently-available-for-DAS-queries, super-full (or high capacity) node. To the p2p, these look just like other nodes but with high advertised capacity, and they should generally be able to be latently found via normal discovery.

DAS providers can also be found out-of-band and configured into a node to connect to directly and prioritize. Nodes can add some set of these to their local configuration for persistent connection to bolster their DAS quality of service.

Such direct peering utilizes a feature supported out of the box today on all nodes and can complement (and reduce attackability and increase quality-of-service) alternative peer discovery mechanisms.

## A note on fork choice

*Fork choice spec TBD, but it will just be a replacement of `is_data_available()` call in Deneb with column sampling instead of full download. Note the `is_data_available(slot_N)` will likely do a `-1` follow distance so that you just need to check the availability of slot `N-1` for slot `N` (starting with the block proposer of `N`).*

The fork choice rule (essentially a DA filter) is *orthogonal to a given DAS design*, other than the efficiency of a particular design impacting it.

In any DAS design, there are probably a few degrees of freedom around timing, acceptability of short-term re-orgs, etc. 

For example, the fork choice rule might require validators to do successful DAS on slot `N` to be able to include block of slot `N` in its fork choice. That's the tightest DA filter. But trailing filters are also probably acceptable, knowing that there might be some failures/short re-orgs but that they don't hurt the aggregate security. For example, the rule could be — DAS must be completed for slot N-1 for a child block in N to be included in the fork choice.

Such trailing techniques and their analysis will be valuable for any DAS construction. The question is — can you relax how quickly you need to do DA and in the worst case not confirm unavailable data via attestations/finality, and what impact does it have on short-term re-orgs and fast confirmation rules.

## FAQs

### Row (blob) custody

In the one-dimension construction, a node samples the peers by requesting the whole `DataColumnSidecar`. In reconstruction, a node can reconstruct all the blobs by 50% of the columns. Note that nodes can still download the row via `blob_sidecar_{subnet_id}` subnets.

The potential benefits of having row custody could include:

1. Allow for more "natural" distribution of data to consumers -- e.g., roll-ups -- but honestly, they won't know a priori which row their blob is going to be included in in the block, so they would either need to listen to all rows or download a particular row after seeing the block. The former looks just like listening to column [0, N)  and the latter is req/resp instead of gossiping.
2. Help with some sort of distributed reconstruction. Those with full rows can compute extensions and seed missing samples to the network. This would either need to be able to send individual points on the gossip or would need some sort of req/resp faculty, potentially similar to an `IHAVEPOINTBITFIELD` and `IWANTSAMPLE`.

However, for simplicity, we don't assign row custody assignments to nodes in the current design.

### Subnet stability

To start with a simple, stable backbone, for now, we don't shuffle the subnet assignments via the deterministic custody selection helper `get_custody_columns`. However, staggered rotation likely needs to happen on the order of the pruning period to ensure subnets can be utilized for recovery. For example, introducing an `epoch` argument allows the function to maintain stability over many epochs.
