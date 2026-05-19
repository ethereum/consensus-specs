# Gloas Partial Columns -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modification in Gloas](#modification-in-gloas)
  - [Containers](#containers)
    - [Modified `PartialDataColumnSidecar`](#modified-partialdatacolumnsidecar)
    - [New `PartialDataColumnGroupID`](#new-partialdatacolumngroupid)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Partial Messages on `data_column_sidecar_{subnet_id}`](#partial-messages-on-data_column_sidecar_subnet_id)

<!-- mdformat-toc end -->

## Introduction

This document specifies the Gloas modifications to partial column dissemination
via gossipsub's Partial Message Extension.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite. In
particular, this document builds on the
[Fulu partial columns networking specification](../../fulu/partial-columns/p2p-interface.md)
and the [Gloas networking specification](../p2p-interface.md).

## Modification in Gloas

### Containers

#### Modified `PartialDataColumnSidecar`

```python
class PartialDataColumnSidecar(Container):
    cells_present_bitmap: Bitlist[MAX_BLOB_COMMITMENTS_PER_BLOCK]
    partial_column: List[Cell, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_proofs: List[KZGProof, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    # [Modified in Gloas:EIP7732]
    # Removed `header`
```

#### New `PartialDataColumnGroupID`

```python
class PartialDataColumnGroupID(Container):
    slot: Slot
    beacon_block_root: Root
```

### The gossip domain: gossipsub

#### Partial Messages on `data_column_sidecar_{subnet_id}`

*[Modified in Gloas:EIP7732]*

*Note*: The Partial Message Group ID is the SSZ encoded
`PartialDataColumnGroupID` prefixed with the version byte `0x01`.
Implementations MUST ignore unknown versions.

**Added in Gloas:**

*Note*: The added rules are similar to the changes in validation rules for full
messages on `data_column_sidecar_{subnet_id}` as defined above.

- _[IGNORE]_ A valid block for the Group ID's `slot` has been seen (via gossip
  or non-gossip sources). If not yet seen, a client SHOULD queue the sidecar for
  deferred validation and possible processing once the block is received or
  retrieved. A client SHOULD queue at least 1 sidecar per peer per subnet.
- _[REJECT]_ The Group ID's `slot` matches the slot of the block with root
  `beacon_block_root`. The `beacon_block_root` is also identified by the Group
  ID.

**Modified in Gloas:**

*Note*: These modifications only replace the mention of the header with the bid,
as the bid contains the KZG commitments.

- _[REJECT]_ The cells present bitmap length is equal to the number of KZG
  commitments in `bid.blob_kzg_commitments`.
- _[REJECT]_ The sidecar's cell and proof data is valid as verified by
  `verify_partial_data_column_sidecar_kzg_proofs(sidecar, bid.blob_kzg_commitments, column_index)`.

**Removed from Fulu:**

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
- _[IGNORE]_ If the received partial message contains only cell and proof data,
  the node has seen a valid corresponding `PartialDataColumnHeader`.
- _[IGNORE]_ The corresponding header is not from a future slot. See related
  header check above for more details.
- _[IGNORE]_ The corresponding header is from a slot greater than the latest
  finalized slot. See related header check above for more details.
