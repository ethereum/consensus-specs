# EIP-4844 -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Custom types](#custom-types)
- [Containers](#containers)
  - [`BlobsAndCommitments`](#blobsandcommitments)
  - [`PolynomialAndCommitment`](#polynomialandcommitment)
- [Helpers](#helpers)
  - [`is_data_available`](#is_data_available)
  - [`hash_to_bls_field`](#hash_to_bls_field)
  - [`compute_powers`](#compute_powers)
  - [`compute_aggregated_poly_and_commitment`](#compute_aggregated_poly_and_commitment)
  - [`validate_blobs_sidecar`](#validate_blobs_sidecar)
  - [`compute_proof_from_blobs`](#compute_proof_from_blobs)
  - [`get_blobs_and_kzg_commitments`](#get_blobs_and_kzg_commitments)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Blob KZG commitments](#blob-kzg-commitments)
  - [Beacon Block publishing time](#beacon-block-publishing-time)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement EIP-4844.

## Prerequisites

This document is an extension of the [Bellatrix -- Honest Validator](../bellatrix/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated [Beacon Chain doc of EIP4844](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `Polynomial` | `List[BLSFieldElement, FIELD_ELEMENTS_PER_BLOB]` | a polynomial in evaluation form |

## Containers

### `BlobsAndCommitments`

```python
class BlobsAndCommitments(Container):
    blobs: List[Blob, MAX_BLOBS_PER_BLOCK]
    kzg_commitments: List[KZGCommitment, MAX_BLOBS_PER_BLOCK]
```

### `PolynomialAndCommitment`

```python
class PolynomialAndCommitment(Container):
    polynomial: Polynomial
    kzg_commitment: KZGCommitment
```


## Helpers

### `is_data_available`

The implementation of `is_data_available` is meant to change with later sharding upgrades.
Initially, it requires every verifying actor to retrieve the matching `BlobsSidecar`,
and validate the sidecar with `validate_blobs_sidecar`.

Without the sidecar the block may be processed further optimistically,
but MUST NOT be considered valid until a valid `BlobsSidecar` has been downloaded.

```python
def is_data_available(slot: Slot, beacon_block_root: Root, blob_kzg_commitments: Sequence[KZGCommitment]) -> bool:
    # `retrieve_blobs_sidecar` is implementation dependent, raises an exception if not available.
    sidecar = retrieve_blobs_sidecar(slot, beacon_block_root)
    validate_blobs_sidecar(slot, beacon_block_root, blob_kzg_commitments, sidecar)

    return True
```

### `hash_to_bls_field`

```python
def hash_to_bls_field(x: Container) -> BLSFieldElement:
    """
    Compute 32-byte hash of serialized container and convert it to BLS field.
    The output is not uniform over the BLS field.
    """
    return bytes_to_bls_field(hash(ssz_serialize(x)))
```

### `compute_powers`
```python
def compute_powers(x: BLSFieldElement, n: uint64) -> Sequence[BLSFieldElement]:
    """
    Return ``x`` to power of [0, n-1].
    """
    current_power = 1
    powers = []
    for _ in range(n):
        powers.append(BLSFieldElement(current_power))
        current_power = current_power * int(x) % BLS_MODULUS
    return powers
```

### `compute_aggregated_poly_and_commitment`

```python
def compute_aggregated_poly_and_commitment(
        blobs: Sequence[Blob],
        kzg_commitments: Sequence[KZGCommitment]) -> Tuple[Polynomial, KZGCommitment]:
    """
    Return the aggregated polynomial and aggregated KZG commitment.
    """
    # Generate random linear combination challenges
    r = hash_to_bls_field(BlobsAndCommitments(blobs=blobs, kzg_commitments=kzg_commitments))
    r_powers = compute_powers(r, len(kzg_commitments))

    # Create aggregated polynomial in evaluation form
    aggregated_poly = Polynomial(vector_lincomb(blobs, r_powers))

    # Compute commitment to aggregated polynomial
    aggregated_poly_commitment = KZGCommitment(g1_lincomb(kzg_commitments, r_powers))

    return aggregated_poly, aggregated_poly_commitment
```

### `validate_blobs_sidecar`

```python
def validate_blobs_sidecar(slot: Slot,
                           beacon_block_root: Root,
                           expected_kzg_commitments: Sequence[KZGCommitment],
                           blobs_sidecar: BlobsSidecar) -> None:
    assert slot == blobs_sidecar.beacon_block_slot
    assert beacon_block_root == blobs_sidecar.beacon_block_root
    blobs = blobs_sidecar.blobs
    kzg_aggregated_proof = blobs_sidecar.kzg_aggregated_proof
    assert len(expected_kzg_commitments) == len(blobs)

    aggregated_poly, aggregated_poly_commitment = compute_aggregated_poly_and_commitment(
        blobs,
        expected_kzg_commitments,
    )

    # Generate challenge `x` and evaluate the aggregated polynomial at `x`
    x = hash_to_bls_field(
        PolynomialAndCommitment(polynomial=aggregated_poly, kzg_commitment=aggregated_poly_commitment)
    )
    # Evaluate aggregated polynomial at `x` (evaluation function checks for div-by-zero)
    y = evaluate_polynomial_in_evaluation_form(aggregated_poly, x)

    # Verify aggregated proof
    assert verify_kzg_proof(aggregated_poly_commitment, x, y, kzg_aggregated_proof)
```

### `compute_proof_from_blobs`

```python
def compute_proof_from_blobs(blobs: Sequence[Blob]) -> KZGProof:
    commitments = [blob_to_kzg_commitment(blob) for blob in blobs]
    aggregated_poly, aggregated_poly_commitment = compute_aggregated_poly_and_commitment(blobs, commitments)
    x = hash_to_bls_field(PolynomialAndCommitment(
        polynomial=aggregated_poly,
        kzg_commitment=aggregated_poly_commitment,
    ))
    return compute_kzg_proof(aggregated_poly, x)
```

### `get_blobs_and_kzg_commitments`

The interface to retrieve blobs and corresponding kzg commitments.

Note: This API is *unstable*. `get_blobs_and_kzg_commitments` and `get_payload` may be unified.
Implementers may also retrieve blobs individually per transaction.

```python
def get_blobs_and_kzg_commitments(payload_id: PayloadId) -> Tuple[Sequence[BLSFieldElement], Sequence[KZGCommitment]]:
    ...
```

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.
Namely, the blob handling and the addition of `BlobsSidecar`.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### Blob KZG commitments

1. After retrieving the execution payload from the execution engine as specified in Bellatrix,
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

Note that the `blobs` should be held with the block in preparation of publishing.
Without the `blobs`, the published block will effectively be ignored by honest validators.

### Beacon Block publishing time

Before publishing a prepared beacon block proposal, the corresponding blobs are packaged into a sidecar object for distribution to the network:

```python
def get_blobs_sidecar(block: BeaconBlock, blobs: Sequence[Blob]) -> BlobsSidecar:
    return BlobsSidecar(
        beacon_block_root=hash_tree_root(block),
        beacon_block_slot=block.slot,
        blobs=blobs,
        kzg_aggregated_proof=compute_proof_from_blobs(blobs),
    )
```

And then signed:

```python
def get_signed_blobs_sidecar(state: BeaconState, blobs_sidecar: BlobsSidecar, privkey: int) -> SignedBlobsSidecar:
    domain = get_domain(state, DOMAIN_BLOBS_SIDECAR, blobs_sidecar.beacon_block_slot // SLOTS_PER_EPOCH)
    signing_root = compute_signing_root(blobs_sidecar, domain)
    signature = bls.Sign(privkey, signing_root)
    return SignedBlobsSidecar(message=blobs_sidecar, signature=signature)
```

This `signed_blobs_sidecar` is then published to the global `blobs_sidecar` topic as soon as the `signed_beacon_block` is published.

After publishing the sidecar peers on the network may request the sidecar through sync-requests, or a local user may be interested.
The validator MUST hold on to blobs for `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS` epochs and serve when capable,
to ensure the data-availability of these blobs throughout the network.

After `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS` nodes MAY prune the blobs and/or stop serving them.
