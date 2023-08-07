# Deneb -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Constants](#constants)
- [Helpers](#helpers)
  - [`BlobsBundle`](#blobsbundle)
  - [Modified `GetPayloadResponse`](#modified-getpayloadresponse)
- [Protocol](#protocol)
  - [`ExecutionEngine`](#executionengine)
    - [Modified `get_payload`](#modified-get_payload)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Blob KZG commitments](#blob-kzg-commitments)
    - [Constructing the `SignedBlobSidecar`s](#constructing-the-signedblobsidecars)
      - [Sidecar](#sidecar)
  - [Validator duties](#validator-duties)
    - [Attestations](#attestations)
    - [Aggregates](#aggregates)
    - [Sync committee messages](#sync-committee-messages)
    - [Sync committee contributions](#sync-committee-contributions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement Deneb.

## Prerequisites

This document is an extension of the [Capella -- Honest Validator](../capella/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated [Beacon Chain doc of Deneb](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Constants

| Name                  | Value       |
| --------------------- | ----------- |
| `ATTESTATION_DUE_MS`  | `6000`      |
| `AGGREGATE_DUE_MS`    | `9000`      |
| `SYNC_MESSAGE_DUE_MS` | `6000`      |
| `CONTRIBUTION_DUE_MS` | `9000`      |

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

##### Blob KZG commitments

*[New in Deneb:EIP4844]*

1. After retrieving the execution payload from the execution engine as specified in Capella,
use the `payload_id` to retrieve `blobs`, `blob_kzg_commitments`, and `blob_kzg_proofs`
via `get_payload(payload_id).blobs_bundle`.
2. Set `block.body.blob_kzg_commitments = blob_kzg_commitments`.

#### Constructing the `SignedBlobSidecar`s

*[New in Deneb:EIP4844]*

To construct a `SignedBlobSidecar`, a `signed_blob_sidecar` is defined with the necessary context for block and sidecar proposal.

##### Sidecar

Blobs associated with a block are packaged into sidecar objects for distribution to the network.

Each `sidecar` is obtained from:
```python
def get_blob_sidecars(block: BeaconBlock,
                      blobs: Sequence[Blob],
                      blob_kzg_proofs: Sequence[KZGProof]) -> Sequence[BlobSidecar]:
    return [
        BlobSidecar(
            block_root=hash_tree_root(block),
            index=index,
            slot=block.slot,
            block_parent_root=block.parent_root,
            blob=blob,
            kzg_commitment=block.body.blob_kzg_commitments[index],
            kzg_proof=blob_kzg_proofs[index],
        )
        for index, blob in enumerate(blobs)
    ]

```

Then for each sidecar, `signed_sidecar = SignedBlobSidecar(message=sidecar, signature=signature)` is constructed and published to the associated sidecar topic, the `blob_sidecar_{subnet_id}` pubsub topic.

`signature` is obtained from:

```python
def get_blob_sidecar_signature(state: BeaconState,
                               sidecar: BlobSidecar,
                               privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BLOB_SIDECAR, compute_epoch_at_slot(sidecar.slot))
    signing_root = compute_signing_root(sidecar, domain)
    return bls.Sign(privkey, signing_root)
```

The `subnet_id` for the `signed_sidecar` is calculated with:
- Let `blob_index = signed_sidecar.message.index`.
- Let `subnet_id = compute_subnet_for_blob_sidecar(blob_index)`.

```python
def compute_subnet_for_blob_sidecar(blob_index: BlobIndex) -> SubnetID:
    return SubnetID(blob_index % BLOB_SIDECAR_SUBNET_COUNT)
```

After publishing the peers on the network may request the sidecar through sync-requests, or a local user may be interested.

The validator MUST hold on to sidecars for `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` epochs and serve when capable,
to ensure the data-availability of these blobs throughout the network.

After `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` nodes MAY prune the sidecars and/or stop serving them.

### Validator duties

The timing for sending attestation, aggregate, sync committee messages and contributions change.

#### Attestations

A validator must create and broadcast the `attestation` to the associated attestation subnet as soon as the validator has received a valid block from the expected block proposer for the assigned `slot`.

If the block has not been observed at `ATTESTATION_DUE_MS` milliseconds into the slot, the validator should send the attestation voting for its current head as selected by fork choice.

Within each slot, clients must be prepared to receive attestations out of order with respect to the block that it's voting for.

#### Aggregates

If the validator is selected to aggregate (`is_aggregator`), then they broadcast their best aggregate as a `SignedAggregateAndProof` to the global aggregate channel (`beacon_aggregate_and_proof`) `AGGREGATE_DUE_MS` milliseconds after the start of the slot.

Within each slot, clients must be prepared to receive aggregates out of order with respect to the block that it's voting for.

#### Sync committee messages

This logic is triggered upon the same conditions as when producing an attestation, using `SYNC_MESSAGE_DUE_MS` as cutoff time.

#### Sync committee contributions

This logic is triggered upon the same conditions as when producing an aggregate, , using `CONTRIBUTION_DUE_MS` as cutoff time.
