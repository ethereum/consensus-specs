# Deneb -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
  - [`get_blobs_and_kzg_commitments`](#get_blobs_and_kzg_commitments)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Blob KZG commitments](#blob-kzg-commitments)
    - [Constructing the `SignedBlobSidecar`s](#constructing-the-signedblobsidecars)
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

### `get_blobs_and_kzg_commitments`

The interface to retrieve blobs and corresponding kzg commitments.

Note: This API is *unstable*. `get_blobs_and_kzg_commitments` and `get_payload` may be unified.
Implementers may also retrieve blobs individually per transaction.

```python
def get_blobs_and_kzg_commitments(payload_id: PayloadId) -> Tuple[Sequence[BLSFieldElement], Sequence[KZGCommitment]]:
    # pylint: disable=unused-argument
    ...
```

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.
Namely, the blob handling and the addition of `SignedBeaconBlockAndBlobsSidecar`.

### Block and sidecar proposal

#### Constructing the `BeaconBlockBody`

##### Blob KZG commitments

1. After retrieving the execution payload from the execution engine as specified in Capella,
use the `payload_id` to retrieve `blobs` and `blob_kzg_commitments` via `get_blobs_and_kzg_commitments(payload_id)`.
2. Validate `blobs` and `blob_kzg_commitments`:

```python
def validate_blobs_and_kzg_commitments(execution_payload: ExecutionPayload,
                                       blobs: Sequence[Blob],
                                       blob_kzg_commitments: Sequence[KZGCommitment]) -> None:
    # Optionally sanity-check that the KZG commitments match the versioned hashes in the transactions
    assert verify_kzg_commitments_against_transactions(execution_payload.transactions, blob_kzg_commitments)

    # Optionally sanity-check that the KZG commitments match the blobs (as produced by the execution engine)
    assert len(blob_kzg_commitments) == len(blobs)
    assert [blob_to_kzg_commitment(blob) == commitment for blob, commitment in zip(blobs, blob_kzg_commitments)]
```

3. If valid, set `block.body.blob_kzg_commitments = blob_kzg_commitments`.

#### Constructing the `SignedBlobSidecar`s

To construct a `SignedBlobSidecar`, a `signed_blob_sidecar` is defined with the necessary context for block and sidecar proposal.

##### Sidecar

Blobs associated with a block are packaged into sidecar objects for distribution to the network.

Each `sidecar` is obtained from:
```python
def get_blob_sidecars(block: BeaconBlock, blobs: Sequence[Blob]) -> Sequence[BlobSidecar]:
    return [
        BlobSidecar(
            block_root=hash_tree_root(block),
            index=index,
            slot=block.slot,
            block_parent_root=block.parent_root,
            blob=blob,
            kzg_commitment=block.body.blob_kzg_commitments[idx],
            kzg_proof=compute_kzg_proof(blob),
        )
        for index, blob in enumerate(blobs)
    ]

```

Then `signed_sidecar = SignedBlobSidecar(message=sidecar, signature=signature)` is constructed and to the global `blob_sidecar_{index}` topics according to its index.

`signature` is obtained from:

```python
def get_blob_sidecar_signature(state: BeaconState,
                               sidecar: BlobSidecar,
                               privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(sidecar.slot))
    signing_root = compute_signing_root(sidecar, domain)
    return bls.Sign(privkey, signing_root)
```

After publishing the peers on the network may request the sidecar through sync-requests, or a local user may be interested.

The validator MUST hold on to sidecars for `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS` epochs and serve when capable,
to ensure the data-availability of these blobs throughout the network.

After `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS` nodes MAY prune the sidecars and/or stop serving them.
