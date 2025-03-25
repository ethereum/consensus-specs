# Deneb -- Honest Validator

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
  - [`BlobsBundle`](#blobsbundle)
  - [Modified `GetPayloadResponse`](#modified-getpayloadresponse)
- [Protocol](#protocol)
  - [`ExecutionEngine`](#executionengine)
    - [Modified `get_payload`](#modified-get_payload)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [ExecutionPayload](#executionpayload)
      - [Blob KZG commitments](#blob-kzg-commitments)
    - [Constructing the `BlobSidecar`s](#constructing-the-blobsidecars)
      - [Sidecar](#sidecar)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement Deneb.

## Prerequisites

This document is an extension of the [Capella -- Honest Validator](../capella/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated [Beacon Chain doc of Deneb](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Helpers

### `BlobsBundle`

*[New in Deneb:EIP4844]*

```python
@dataclass
class BlobsBundle(object):
    commitments: Sequence[KZGCommitment]
    proofs: Sequence[KZGProof]
    blobs: Sequence[Blob]
```

### Modified `GetPayloadResponse`

```python
@dataclass
class GetPayloadResponse(object):
    execution_payload: ExecutionPayload
    block_value: uint256
    blobs_bundle: BlobsBundle  # [New in Deneb:EIP4844]
```

```python
def compute_signed_block_header(
    signed_block: SignedBeaconBlock,
) -> SignedBeaconBlockHeader:
    block = signed_block.message
    block_header = BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=block.state_root,
        body_root=hash_tree_root(block.body),
    )
    return SignedBeaconBlockHeader(
        message=block_header, signature=signed_block.signature
    )
```

## Protocol

### `ExecutionEngine`

#### Modified `get_payload`

Given the `payload_id`, `get_payload` returns the most recent version of the execution payload that
has been built since the corresponding call to `notify_forkchoice_updated` method.

```python
def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
    """
    Return ExecutionPayload, uint256, BlobsBundle objects.
    """
    # pylint: disable=unused-argument
    ...
```

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Block and sidecar proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayload

`prepare_execution_payload` is updated from the Capella specs to provide the parent beacon block root.

*Note*: In this section, `state` is the state of the slot for the block proposal _without_ the block yet applied.
That is, `state` is the `previous_state` processed through any empty slots up to the assigned slot using `process_slots(previous_state, slot)`.

*Note*: The only change made to `prepare_execution_payload` is to add the parent beacon block root as an additional
parameter to the `PayloadAttributes`.

```python
def prepare_execution_payload(
    state: BeaconState,
    safe_block_hash: Hash32,
    finalized_block_hash: Hash32,
    suggested_fee_recipient: ExecutionAddress,
    execution_engine: ExecutionEngine,
) -> Optional[PayloadId]:
    # Verify consistency of the parent hash with respect to the previous execution payload header
    parent_hash = state.latest_execution_payload_header.block_hash

    # Set the forkchoice head and initiate the payload build process
    payload_attributes = PayloadAttributes(
        timestamp=compute_timestamp_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        withdrawals=get_expected_withdrawals(state),
        parent_beacon_block_root=hash_tree_root(
            state.latest_block_header
        ),  # [New in Deneb:EIP4788]
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=parent_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```

##### Blob KZG commitments

*[New in Deneb:EIP4844]*

1. The execution payload is obtained from the execution engine as defined above using `payload_id`. The response also includes a `blobs_bundle` entry containing the corresponding `blobs`, `commitments`, and `proofs`.
2. Set `block.body.blob_kzg_commitments = commitments`.

#### Constructing the `BlobSidecar`s

*[New in Deneb:EIP4844]*

To construct a `BlobSidecar`, a `blob_sidecar` is defined with the necessary context for block and sidecar proposal.

##### Sidecar

Blobs associated with a block are packaged into sidecar objects for distribution to the associated sidecar topic, the `blob_sidecar_{subnet_id}` pubsub topic.

Each `sidecar` is obtained from:

```python
def get_blob_sidecars(
    signed_block: SignedBeaconBlock,
    blobs: Sequence[Blob],
    blob_kzg_proofs: Sequence[KZGProof],
) -> Sequence[BlobSidecar]:
    block = signed_block.message
    signed_block_header = compute_signed_block_header(signed_block)
    return [
        BlobSidecar(
            index=index,
            blob=blob,
            kzg_commitment=block.body.blob_kzg_commitments[index],
            kzg_proof=blob_kzg_proofs[index],
            signed_block_header=signed_block_header,
            kzg_commitment_inclusion_proof=compute_merkle_proof(
                block.body,
                get_generalized_index(BeaconBlockBody, "blob_kzg_commitments", index),
            ),
        )
        for index, blob in enumerate(blobs)
    ]
```

The `subnet_id` for the `blob_sidecar` is calculated with:

- Let `blob_index = blob_sidecar.index`.
- Let `subnet_id = compute_subnet_for_blob_sidecar(blob_index)`.

```python
def compute_subnet_for_blob_sidecar(blob_index: BlobIndex) -> SubnetID:
    return SubnetID(blob_index % BLOB_SIDECAR_SUBNET_COUNT)
```

After publishing the peers on the network may request the sidecar through sync-requests, or a local user may be interested.

The validator MUST hold on to sidecars for `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` epochs and serve when capable,
to ensure the data-availability of these blobs throughout the network.

After `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` nodes MAY prune the sidecars and/or stop serving them.
