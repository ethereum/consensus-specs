# EIP-7594 -- Networking

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Modifications in EIP-7594](#modifications-in-eip-7594)
  - [Preset](#preset)
  - [Configuration](#configuration)
  - [Containers](#containers)
    - [`DataColumnSidecar`](#datacolumnsidecar)
    - [`DataColumnIndexentifier`](#dataColumnIndexentifier)
  - [Helpers](#helpers)
      - [`verify_data_column_sidecar_kzg_proof`](#verify_data_column_sidecar_kzg_proof)
      - [`verify_data_column_sidecar_inclusion_proof`](#verify_data_column_sidecar_inclusion_proof)
      - [`compute_subnet_for_data_column_sidecar`](#compute_subnet_for_data_column_sidecar)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Samples subnets](#samples-subnets)
        - [`data_column_sidecar_{subnet_id}`](#data_column_sidecar_subnet_id)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [DataColumnSidecarByRoot v1](#datacolumnsidecarbyroot-v1)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Modifications in EIP-7594

### Preset

| Name                                     | Value                             | Description                                                         |
|------------------------------------------|-----------------------------------|---------------------------------------------------------------------|
| `KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH`   | `uint64(floorlog2(get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments')))` (= 4) | <!-- predefined --> Merkle proof index for `blob_kzg_commitments` |

### Configuration

| Name                                     | Value                             | Description                                                         |
|------------------------------------------|-----------------------------------|---------------------------------------------------------------------|
| `DATA_COLUMN_SIDECAR_SUBNET_COUNT`              | `32`                               | The number of data column sidecar subnets used in the gossipsub protocol.  |

### Containers

#### `DataColumnSidecar`

```python
class DataColumnSidecar(Container):
    index: ColumnIndex  # Index of column in extended matrix
    column: DataColumn
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_proofs: List[KZGProof, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    signed_block_header: SignedBeaconBlockHeader
    kzg_commitments_inclusion_proof: Vector[Bytes32, KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH]
```

#### `DataColumnIndexentifier`

```python
class DataColumnIndexentifier(Container):
    block_root: Root
    index: ColumnIndex
```

### Helpers

##### `verify_data_column_sidecar_kzg_proof`

```python
def verify_data_column_sidecar_kzg_proof(sidecar: DataColumnSidecar) -> bool:
    """
    Verify if the proofs are correct
    """
    row_ids = [RowIndex(i) for i in range(len(sidecar.column))]
    assert len(sidecar.column) == len(sidecar.kzg_commitments) == len(sidecar.kzg_proofs)

    # KZG batch verifies that the cells match the corresponding commitments and proofs
    return verify_cell_proof_batch(
        row_commitments=sidecar.kzg_commitments,
        row_indices=row_ids,  # all rows
        column_indices=[sidecar.index],
        datas=sidecar.column,
        proofs=sidecar.kzg_proofs,
    )
```

##### `verify_data_column_sidecar_inclusion_proof`

```python
def verify_data_column_sidecar_inclusion_proof(sidecar: DataColumnSidecar) -> bool:
    """
    Verify if the given KZG commitments included in the given beacon block.
    """
    gindex = get_subtree_index(get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments'))
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


### The gossip domain: gossipsub

Some gossip meshes are upgraded in the EIP-7594 fork to support upgraded types.

#### Topics and messages

##### Samples subnets

###### `data_column_sidecar_{subnet_id}`

This topic is used to propagate column sidecars, where each column maps to some `subnet_id`.

The *type* of the payload of this topic is `DataColumnSidecar`.

The following validations MUST pass before forwarding the `sidecar: DataColumnSidecar` on the network, assuming the alias `block_header = sidecar.signed_block_header.message`:

- _[REJECT]_ The sidecar's index is consistent with `NUMBER_OF_COLUMNS` -- i.e. `sidecar.index < NUMBER_OF_COLUMNS`.
- _[REJECT]_ The sidecar is for the correct subnet -- i.e. `compute_subnet_for_data_column_sidecar(sidecar.index) == subnet_id`.
- _[IGNORE]_ The sidecar is not from a future slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. validate that `block_header.slot <= current_slot` (a client MAY queue future sidecars for processing at the appropriate slot).
- _[IGNORE]_ The sidecar is from a slot greater than the latest finalized slot -- i.e. validate that `block_header.slot > compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)`
- _[REJECT]_ The proposer signature of `sidecar.signed_block_header`, is valid with respect to the `block_header.proposer_index` pubkey.
- _[IGNORE]_ The sidecar's block's parent (defined by `block_header.parent_root`) has been seen (via both gossip and non-gossip sources) (a client MAY queue sidecars for processing once the parent block is retrieved).
- _[REJECT]_ The sidecar's block's parent (defined by `block_header.parent_root`) passes validation.
- _[REJECT]_ The sidecar is from a higher slot than the sidecar's block's parent (defined by `block_header.parent_root`).
- _[REJECT]_ The current finalized_checkpoint is an ancestor of the sidecar's block -- i.e. `get_checkpoint_block(store, block_header.parent_root, store.finalized_checkpoint.epoch) == store.finalized_checkpoint.root`.
- _[REJECT]_ The sidecar's `kzg_commitments` field inclusion proof is valid as verified by `verify_data_column_sidecar_inclusion_proof(sidecar)`.
- _[REJECT]_ The sidecar's column data is valid as verified by `verify_data_column_sidecar_kzg_proof(sidecar)`.
- _[IGNORE]_ The sidecar is the first sidecar for the tuple `(block_header.slot, block_header.proposer_index, sidecar.index)` with valid header signature, sidecar inclusion proof, and kzg proof.
- _[REJECT]_ The sidecar is proposed by the expected `proposer_index` for the block's slot in the context of the current shuffling (defined by `block_header.parent_root`/`block_header.slot`).
  If the `proposer_index` cannot immediately be verified against the expected shuffling, the sidecar MAY be queued for later processing while proposers for the block's branch are calculated -- in such a case _do not_ `REJECT`, instead `IGNORE` this message.

*Note:* In the `verify_data_column_sidecar_inclusion_proof(sidecar)` check, for all the sidecars of the same block, it verifies against the same set of `kzg_commitments` of the given beacon beacon. Client can choose to cache the result of the arguments tuple `(sidecar.kzg_commitments, sidecar.kzg_commitments_inclusion_proof, sidecar.signed_block_header)`.

### The Req/Resp domain

#### Messages

##### DataColumnSidecarByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/data_column_sidecar_by_root/1/`

*[New in Deneb:EIP4844]*

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `EIP7594_FORK_VERSION`     | `eip7594.DataColumnSidecar`           |

Request Content:

```
(
  DataColumnIndexentifier
)
```

Response Content:

```
(
  DataColumnSidecar
)
```
