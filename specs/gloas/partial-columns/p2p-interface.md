# Gloas Partial Columns -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Containers](#containers)
  - [Modified `PartialDataColumnSidecar`](#modified-partialdatacolumnsidecar)
  - [Modified `PartialDataColumnGroupID`](#modified-partialdatacolumngroupid)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Blob subnets](#blob-subnets)
    - [Modified `data_column_sidecar_{subnet_id}` (partial messages)](#modified-data_column_sidecar_subnet_id-partial-messages)

<!-- mdformat-toc end -->

## Introduction

This document specifies the Gloas modifications to partial column dissemination
via gossipsub's Partial Message Extension.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite. In
particular, this document builds on the
[Fulu partial columns networking specification](../../fulu/partial-columns/p2p-interface.md)
and the [Gloas networking specification](../p2p-interface.md).

## Containers

### Modified `PartialDataColumnSidecar`

```python
class PartialDataColumnSidecar(Container):
    cells_present_bitmap: Bitlist[MAX_BLOB_COMMITMENTS_PER_BLOCK]
    partial_column: List[Cell, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_proofs: List[KZGProof, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    # [Modified in Gloas:EIP7732]
    # Removed `header`
```

### Modified `PartialDataColumnGroupID`

```python
class PartialDataColumnGroupID(Container):
    beacon_block_root: Root
    # [New in Gloas:EIP7732]
    slot: Slot
```

## The gossip domain: gossipsub

### Blob subnets

#### Modified `data_column_sidecar_{subnet_id}` (partial messages)

*Note*: The KZG commitments needed to verify a partial sidecar are now carried
by the bid at
`block.body.signed_execution_payload_bid.message.blob_kzg_commitments`, where
`block` is the `BeaconBlock` with root `group_id.beacon_block_root`. All
header-related validations from Fulu are removed; their role is taken over by
the bid commitments and the corresponding block validation.

```python
def validate_partial_data_column_sidecar_gossip(
    # [Modified in Gloas:EIP7732]
    # Removed `seen`
    store: Store,
    # [Modified in Gloas:EIP7732]
    # Removed `state`
    sidecar: PartialDataColumnSidecar,
    # [Modified in Gloas:EIP7732]
    # Removed `current_time_ms`
    group_id: PartialDataColumnGroupID,
    column_index: ColumnIndex,
) -> None:
    """
    Validate a PartialDataColumnSidecar for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    num_cells_present = sum(1 for b in sidecar.cells_present_bitmap if b)

    # [Modified in Gloas]
    # [REJECT] The message contains at least one cell
    if num_cells_present == 0:
        raise GossipReject("partial message is semantically empty")

    # [REJECT] The cell count equals the number of set bits in the bitmap
    if len(sidecar.partial_column) != num_cells_present:
        raise GossipReject("number of cells does not match number of set bits")

    # [REJECT] The proof count equals the number of set bits in the bitmap
    if len(sidecar.kzg_proofs) != num_cells_present:
        raise GossipReject("number of proofs does not match number of set bits")

    # [New in Gloas]
    # [IGNORE] The group ID's block has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    # (SHOULD queue at least one sidecar per peer per subnet)
    if group_id.beacon_block_root not in store.blocks:
        raise GossipIgnore("group id's beacon block has not been seen")

    block = store.blocks[group_id.beacon_block_root]

    # [New in Gloas]
    # [REJECT] The group ID's slot matches the slot of the block
    if group_id.slot != block.slot:
        raise GossipReject("group id's slot does not match the block's slot")

    bid = block.body.signed_execution_payload_bid.message

    # [REJECT] The cells present bitmap length equals the number of bid commitments
    if len(sidecar.cells_present_bitmap) != len(bid.blob_kzg_commitments):
        raise GossipReject("bitmap length does not match the number of bid commitments")

    # [REJECT] The sidecar's cell and proof data passes KZG verification
    if not verify_partial_data_column_sidecar_kzg_proofs(
        sidecar, bid.blob_kzg_commitments, column_index
    ):
        raise GossipReject("invalid sidecar kzg proofs")
```
